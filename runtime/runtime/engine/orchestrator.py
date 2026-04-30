"""Per (camera, question) asyncio task plus per-camera heartbeat task.

This is where the pieces actually wire together: sample → dedup → VLM → coerce →
buffer → rules → dispatch.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from shared.dsl import DSL, Camera, Question, Rule
from shared.dsl.schema import parse_duration

from runtime.camera.failure import CameraFailureHandler
from runtime.camera.sampler import FrameSampler
from runtime.camera.snapshot_cache import SnapshotCache
from runtime.clock import utcnow
from runtime.engine.buffer import Observation, TemporalBuffer
from runtime.engine.cadence import AdaptiveCadence
from runtime.engine.dispatcher import AlertDispatcher
from runtime.engine.rules import RuleEvaluator
from runtime.observability.alerts import AlertHistory
from runtime.observability.cost import CostMeter
from runtime.observability.health import HealthMonitor
from runtime.observability.log import ObservationLog
from runtime.vlm.client import VLMClient
from runtime.vlm.encoder import FrameEncoder

log = logging.getLogger(__name__)


@dataclass
class Deployment:
    """Top-level handle returned by the boot sequence."""

    dsl: DSL
    deployment_id: str
    tasks: list[asyncio.Task] = field(default_factory=list)
    samplers: dict[str, FrameSampler] = field(default_factory=dict)
    buffers: dict[tuple[str, str], TemporalBuffer] = field(default_factory=dict)
    snapshot_caches: dict[tuple[str, str], SnapshotCache] = field(default_factory=dict)
    failure_handler: CameraFailureHandler | None = None
    rule_evaluator: RuleEvaluator | None = None
    cadence: AdaptiveCadence | None = None
    dispatcher: AlertDispatcher | None = None
    vlm: VLMClient | None = None
    encoder: FrameEncoder | None = None
    obs_log: ObservationLog | None = None
    cost: CostMeter | None = None
    health: HealthMonitor | None = None
    alerts: AlertHistory | None = None
    failed_cameras: set[str] = field(default_factory=set)
    _stopping: bool = False

    async def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        for t in self.tasks:
            t.cancel()
        # Use gather(return_exceptions=True) so a hanging task can't block shutdown
        # and so cancellation/error reporting stays observable per-task.
        results = await asyncio.gather(*self.tasks, return_exceptions=True)
        for t, res in zip(self.tasks, results):
            if isinstance(res, asyncio.CancelledError):
                continue
            if isinstance(res, Exception):
                log.warning(
                    "task_exit_error", extra={"task": t.get_name(), "error": str(res)}
                )
        for s in self.samplers.values():
            try:
                await s.close()
            except Exception as e:
                log.warning(
                    "sampler_close_error", extra={"camera": s.camera_id, "error": str(e)}
                )
        if self.dispatcher is not None:
            await self.dispatcher.aclose()


def build_deployment(
    dsl: DSL,
    *,
    settings,
    vlm: VLMClient,
    pool: Any | None,
    failed_cameras: list[str] | None = None,
) -> Deployment:
    """Construct a Deployment with all collaborators wired but no tasks running yet."""

    deployment_id = dsl.deployment.id
    failed = set(failed_cameras or [])

    health = HealthMonitor()
    cost = CostMeter(
        deployment_id=deployment_id,
        cost_per_mtok_input=settings.vlm_cost_per_mtok_input,
        cost_per_mtok_output=settings.vlm_cost_per_mtok_output,
        pool=pool,
    )
    alerts_hist = AlertHistory(pool=pool, deployment_id=deployment_id)
    dispatcher = AlertDispatcher(
        channels=dsl.alerts.channels,
        history_sink=alerts_hist.record,
        allow_private_webhooks=getattr(settings, "allow_private_webhooks", False),
    )
    rule_evaluator = RuleEvaluator()
    cadence = AdaptiveCadence()
    encoder = FrameEncoder(
        max_dimension=settings.image_max_dimension, jpeg_quality=settings.jpeg_quality
    )
    obs_log = ObservationLog(pool=pool, deployment_id=deployment_id) if pool is not None else None

    async def emit_starved(camera_id: str) -> None:
        # Synthetic alert for observation-starved cameras. dispatch_synthetic
        # handles channel fan-out + history recording in one place.
        await dispatcher.dispatch_synthetic(
            rule_id=f"observation_starved:{camera_id}",
            camera_id=camera_id,
            message=f"Camera {camera_id} has produced no observations recently",
            severity="high",
        )

    failure_handler = CameraFailureHandler(
        starved_threshold=settings.camera_starved_threshold,
        max_retries=settings.camera_max_retries,
        base_delay=settings.camera_base_delay,
        max_delay=settings.camera_max_delay,
        on_starved=emit_starved,
    )

    samplers: dict[str, FrameSampler] = {}
    for cam in dsl.cameras:
        if cam.id in failed:
            continue
        samplers[cam.id] = FrameSampler(
            rtsp_url=cam.rtsp_url,
            camera_id=cam.id,
            failure_handler=failure_handler,
            heartbeat_interval=settings.camera_heartbeat_interval,
        )
        health.init_camera(cam.id)

    buffers: dict[tuple[str, str], TemporalBuffer] = {}
    snapshot_caches: dict[tuple[str, str], SnapshotCache] = {}
    for q in dsl.questions:
        if q.camera in failed:
            continue
        buffers[(q.camera, q.id)] = TemporalBuffer()
        snapshot_caches[(q.camera, q.id)] = SnapshotCache(
            threshold=settings.snapshot_diff_threshold
        )

    # When a camera reconnects, clear all buffers + caches for that camera so the
    # sustained_for window can't span the gap (ARCH-6).
    def _on_reconnect(camera_id: str) -> None:
        for (cam_id, q_id), buf in buffers.items():
            if cam_id == camera_id:
                buf.clear()
                snapshot_caches[(cam_id, q_id)].clear()
        health.mark_camera_reconnect(camera_id)

    for cam in dsl.cameras:
        if cam.id in failed:
            continue
        failure_handler.register_reset_callback(cam.id, _on_reconnect)

    return Deployment(
        dsl=dsl,
        deployment_id=deployment_id,
        samplers=samplers,
        buffers=buffers,
        snapshot_caches=snapshot_caches,
        failure_handler=failure_handler,
        rule_evaluator=rule_evaluator,
        cadence=cadence,
        dispatcher=dispatcher,
        vlm=vlm,
        encoder=encoder,
        obs_log=obs_log,
        cost=cost,
        health=health,
        alerts=alerts_hist,
        failed_cameras=failed,
    )


async def heartbeat_task(sampler: FrameSampler, health: HealthMonitor, interval: float) -> None:
    while True:
        try:
            await asyncio.sleep(interval)
            ok = await sampler.heartbeat()
            if not ok:
                health.mark_camera_failure(sampler.camera_id)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("heartbeat_task_error", extra={"error": str(e)})


async def per_question_task(
    deployment: Deployment, camera: Camera, question: Question
) -> None:
    """Sample → dedup → VLM → coerce → buffer → rules → dispatch loop."""

    sampler = deployment.samplers.get(camera.id)
    if sampler is None:
        return
    cache = deployment.snapshot_caches[(camera.id, question.id)]
    buf = deployment.buffers[(camera.id, question.id)]
    cadence = deployment.cadence
    encoder = deployment.encoder
    vlm = deployment.vlm
    rule_evaluator = deployment.rule_evaluator
    dispatcher = deployment.dispatcher
    obs_log = deployment.obs_log
    cost = deployment.cost
    health = deployment.health
    rules_for_q: list[Rule] = [
        r for r in deployment.dsl.rules
        if r.on.camera == camera.id and r.on.question == question.id
    ]
    base_interval = parse_duration(camera.sample_every)
    severity = max(
        (r.severity for r in rules_for_q),
        key=lambda s: ["medium", "high", "critical", "safety_critical"].index(s),
        default="medium",
    )
    schema_payload = {
        "name": question.id,
        "schema": {
            "type": "object",
            "properties": question.output_schema.properties,
            "required": question.output_schema.required,
            "additionalProperties": False,
        },
        "strict": False,
    }

    while True:
        try:
            frame = await sampler.sample()
            if frame is None:
                buf.append_gap()
                health.mark_gap(question.id)
                if obs_log is not None:
                    try:
                        await obs_log.record(camera.id, question.id, buf.latest())
                    except Exception as e:
                        log.exception("obs_log_failed", extra={"error": str(e)})
                await asyncio.sleep(base_interval.total_seconds())
                continue

            health.mark_frame(camera.id)

            if cache.is_scene_equivalent(frame) and cache.last_answer is not None:
                # Reuse the cached answer; record an observation, no VLM call.
                obs = Observation(
                    timestamp=utcnow(),
                    answer=cache.last_answer,
                    confidence=float(cache.last_answer.get("confidence", 0.0) or 0.0),
                )
            else:
                jpeg = encoder.encode(frame)
                try:
                    coerced = await vlm.ask(
                        prompt=question.prompt,
                        jpeg_bytes=jpeg,
                        output_schema=schema_payload,
                        question_id=question.id,
                    )
                    answer = coerced.data
                    confidence = float(answer.get("confidence", 0.0) or 0.0)
                    if cost is not None and coerced.usage is not None:
                        cost.record(camera.id, question.id, coerced.usage)
                    cache.update(frame, answer)
                    obs = Observation(timestamp=utcnow(), answer=answer, confidence=confidence)
                except Exception as e:
                    log.warning(
                        "vlm_call_failed",
                        extra={"camera": camera.id, "question": question.id, "error": str(e)},
                    )
                    buf.append_gap()
                    health.mark_gap(question.id)
                    if obs_log is not None:
                        try:
                            await obs_log.record(camera.id, question.id, buf.latest())
                        except Exception as ee:
                            log.exception("obs_log_failed", extra={"error": str(ee)})
                    await asyncio.sleep(base_interval.total_seconds())
                    continue

            buf.append(obs)
            if obs_log is not None:
                try:
                    await obs_log.record(camera.id, question.id, obs)
                except Exception as e:
                    log.exception("obs_log_failed", extra={"error": str(e)})

            # Evaluate rules. Encode the snapshot at most once per tick, only if a
            # rule actually fires AND wants `attach=true` (no rules → no encode).
            attach_jpeg: bytes | None = None
            for rule in rules_for_q:
                result = rule_evaluator.evaluate(rule, buf)
                if result is None or not result.matched:
                    continue
                if attach_jpeg is None and any(
                    a.type == "alert" and a.attach for a in rule.actions
                ):
                    attach_jpeg = encoder.encode(frame)
                try:
                    await dispatcher.dispatch(result, rule, obs, frame_jpeg=attach_jpeg)
                except Exception as e:
                    log.exception("dispatch_failed", extra={"rule": rule.id, "error": str(e)})

            # Adaptive cadence
            recent = [o.answer for o in list(buf.buffer)[-cadence.stable_window :]]
            interval = cadence.compute_interval(base_interval, severity, recent)
            await asyncio.sleep(interval.total_seconds())

        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception(
                "per_question_task_error",
                extra={"camera": camera.id, "question": question.id, "error": str(e)},
            )
            await asyncio.sleep(min(base_interval.total_seconds(), 5.0))


async def start_deployment(deployment: Deployment, settings) -> None:
    """Open all sampler connections and start tasks. Idempotent on re-call."""
    # Open RTSP for each non-failed camera; mark failures (don't abort here — boot
    # already validated G5).
    for cam_id, sampler in list(deployment.samplers.items()):
        try:
            await sampler.open()
            deployment.health.mark_frame(cam_id)
        except Exception as e:
            log.warning("sampler_open_failed", extra={"camera": cam_id, "error": str(e)})
            deployment.failed_cameras.add(cam_id)
            await deployment.failure_handler.on_failure(cam_id, e)

    cams_by_id = {c.id: c for c in deployment.dsl.cameras}
    questions_by_camera: dict[str, list[Question]] = defaultdict(list)
    for q in deployment.dsl.questions:
        questions_by_camera[q.camera].append(q)

    for cam_id, sampler in deployment.samplers.items():
        if cam_id in deployment.failed_cameras:
            continue
        deployment.tasks.append(
            asyncio.create_task(
                heartbeat_task(sampler, deployment.health, settings.camera_heartbeat_interval),
                name=f"heartbeat:{cam_id}",
            )
        )
        for q in questions_by_camera.get(cam_id, []):
            deployment.tasks.append(
                asyncio.create_task(
                    per_question_task(deployment, cams_by_id[cam_id], q),
                    name=f"task:{cam_id}:{q.id}",
                )
            )

    # Background: cost persist, retention
    if deployment.cost is not None and deployment.cost.pool is not None:
        deployment.tasks.append(
            asyncio.create_task(deployment.cost.run_persist_loop(), name="cost_persist")
        )
    if deployment.obs_log is not None:
        from runtime.observability.retention import RetentionJob

        retention = RetentionJob(
            pool=deployment.obs_log.pool,
            retention_days=settings.observation_retention_days,
        )
        deployment.tasks.append(
            asyncio.create_task(retention.run_forever(), name="retention")
        )
