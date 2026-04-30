"""Per-question orchestrator: snapshot dedup avoids the second VLM call."""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pytest

from shared.dsl import (
    AlertChannel,
    AlertsBlock,
    Camera,
    Deployment,
    DSL,
    OutputSchema,
    Question,
    Rule,
    RuleAction,
    RuleOn,
)

from runtime.config import Settings
from runtime.engine.orchestrator import build_deployment, per_question_task


def _dsl(sample_every: str = "0s") -> DSL:
    return DSL(
        deployment=Deployment(id="dep_x", customer_id="c", inspection_id="i"),
        cameras=[Camera(id="cam_a", rtsp_url="rtsp://a", sample_every=sample_every)],
        questions=[Question(
            id="q_a", camera="cam_a", prompt="?",
            output_schema=OutputSchema(
                type="object",
                properties={"violation_present": {"type": "boolean"}, "confidence": {"type": "number"}},
                required=["violation_present", "confidence"],
            ),
        )],
        rules=[Rule(
            id="r1", on=RuleOn(camera="cam_a", question="q_a"),
            when={"violation_present": True}, sustained_for="30s", sustained_threshold=0.7,
            severity="high", cooldown="5m",
            actions=[RuleAction(type="alert", channel_ref="ch1", message="m")],
        )],
        alerts=AlertsBlock(channels=[
            AlertChannel(id="ch1", type="slack_webhook", url="https://example.test/x")
        ]),
    )


class _StaticSampler:
    """Returns the same frame on demand. `sample()` waits on a queue so we can
    drive iterations one at a time."""

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.frame = np.full((480, 640, 3), 128, dtype=np.uint8)
        self.calls = 0

    async def sample(self):
        self.calls += 1
        return self.frame

    async def open(self):
        return None

    async def close(self):
        return None


async def test_dedup_prevents_second_vlm_call(stub_vlm, fake_pool):
    settings = Settings()
    deployment = build_deployment(_dsl(sample_every="0s"), settings=settings, vlm=stub_vlm, pool=fake_pool)
    cam = deployment.dsl.cameras[0]
    q = deployment.dsl.questions[0]

    static = _StaticSampler(cam.id)
    deployment.samplers[cam.id] = static
    deployment.health.mark_frame(cam.id)

    task = asyncio.create_task(per_question_task(deployment, cam, q))
    # 0s base sleep + cadence floor will still produce a 0-or-3s sleep per loop.
    # Let the task run for a short window of real time, then cancel.
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # First sample → cache miss → VLM call. All subsequent identical frames hit the cache.
    assert stub_vlm.calls == 1
    assert static.calls >= 1


async def test_vlm_failure_records_gap(stub_vlm, fake_pool):
    settings = Settings()
    deployment = build_deployment(_dsl(sample_every="0s"), settings=settings, vlm=stub_vlm, pool=fake_pool)
    cam = deployment.dsl.cameras[0]
    q = deployment.dsl.questions[0]

    static = _StaticSampler(cam.id)
    deployment.samplers[cam.id] = static
    stub_vlm.raise_n = 5  # every call within the test window will fail

    task = asyncio.create_task(per_question_task(deployment, cam, q))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # At least one gap recorded for the question
    assert deployment.health.gap_count_per_question.get(q.id, 0) >= 1
