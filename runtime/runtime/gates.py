"""Preflight gates G3–G7. Each returns a GateResult.

Design notes:
  * G3 (VLM access) and G7 (dry-run) are *abort* gates — caller raises BootFailure on failure.
  * G4 (cost estimate) is *advisory* — never fails boot.
  * G5 (RTSP reachability) is *partial* — returns per-camera results; caller proceeds if ≥1 ok.
  * G6 (notification ping) is *advisory* — log per-channel results; never fails boot.
"""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from shared.dsl import DSL, AlertChannel, Camera
from shared.dsl.schema import parse_duration


@dataclass
class GateResult:
    name: str
    ok: bool
    detail: dict[str, Any] = field(default_factory=dict)
    message: str = ""


# ---------- G3 ----------------------------------------------------------------

async def gate_g3_vlm_access(vlm_client) -> GateResult:
    """Make a tiny test call to the primary VLM. Hard fail on error."""
    try:
        # 1x1 white pixel JPEG, no real perception required.
        jpeg = _tiny_jpeg()
        await vlm_client.test_call(jpeg)
        return GateResult(name="G3_vlm_access", ok=True)
    except Exception as e:
        return GateResult(name="G3_vlm_access", ok=False, message=str(e))


# ---------- G4 ----------------------------------------------------------------

async def gate_g4_cost_estimate(dsl: DSL, *, cost_per_call_usd: float = 0.005) -> GateResult:
    """Compute worst/typical/best-case $/hour. Always passes (advisory)."""
    cameras = {c.id: c for c in dsl.cameras}
    questions = dsl.questions

    worst = 0.0  # no snapshot dedup, all calls fresh
    typical = 0.0  # 50% dedup on average
    best = 0.0  # 90% dedup

    for q in questions:
        cam = cameras.get(q.camera)
        if cam is None:
            continue
        interval_s = parse_duration(cam.sample_every).total_seconds()
        calls_per_hour = 3600.0 / max(interval_s, 0.1)
        worst += calls_per_hour * cost_per_call_usd
        typical += calls_per_hour * cost_per_call_usd * 0.5
        best += calls_per_hour * cost_per_call_usd * 0.1

    return GateResult(
        name="G4_cost_estimate",
        ok=True,
        detail={
            "usd_per_hour_worst": round(worst, 4),
            "usd_per_hour_typical": round(typical, 4),
            "usd_per_hour_best": round(best, 4),
            "cameras": len(cameras),
            "questions": len(questions),
        },
    )


# ---------- G5 ----------------------------------------------------------------

async def gate_g5_rtsp_reachability(cameras: list[Camera], probe=None) -> GateResult:
    """Try to open each camera's RTSP stream. Partial success allowed.

    `probe`: async callable (rtsp_url) -> (ok: bool, detail: dict). Defaults to OpenCV probe.
    """
    if probe is None:
        from runtime.camera.sampler import probe_rtsp as default_probe
        probe = default_probe

    results: dict[str, dict[str, Any]] = {}
    for cam in cameras:
        try:
            ok, detail = await probe(cam.rtsp_url)
        except Exception as e:
            ok, detail = False, {"error": str(e)}
        results[cam.id] = {"ok": ok, **detail}

    any_ok = any(r["ok"] for r in results.values())
    return GateResult(
        name="G5_rtsp_reachability",
        ok=any_ok,
        detail={"cameras": results},
        message="" if any_ok else "no cameras reachable",
    )


# ---------- G6 ----------------------------------------------------------------

async def gate_g6_notification_ping(
    channels: list[AlertChannel], dispatcher=None
) -> GateResult:
    """Send a test ping to each channel. Always passes (advisory)."""
    if dispatcher is None:
        from runtime.engine.dispatcher import AlertDispatcher
        dispatcher = AlertDispatcher(channels=channels)

    results: dict[str, dict[str, Any]] = {}
    for ch in channels:
        try:
            ok, detail = await dispatcher.ping(ch)
        except Exception as e:
            ok, detail = False, {"error": str(e)}
        results[ch.id] = {"ok": ok, **detail}

    return GateResult(
        name="G6_notification_ping",
        ok=True,  # advisory
        detail={"channels": results},
    )


# ---------- G7 ----------------------------------------------------------------

async def gate_g7_dry_run(dsl: DSL, vlm_client) -> GateResult:
    """Make one real VLM call per question with a black frame.

    If the VLM cannot answer the schema for any question, abort: rules will not work.
    """
    from runtime.vlm.encoder import FrameEncoder

    encoder = FrameEncoder()
    black = np.zeros((480, 640, 3), dtype=np.uint8)
    jpeg = encoder.encode(black)

    failures: list[str] = []
    per_question: dict[str, dict[str, Any]] = {}
    for q in dsl.questions:
        try:
            result = await vlm_client.ask(
                prompt=q.prompt,
                jpeg_bytes=jpeg,
                output_schema=_question_to_json_schema(q),
            )
            per_question[q.id] = {"ok": True, "coercion_errors": result.coercion_errors}
        except Exception as e:
            failures.append(f"{q.id}: {e}")
            per_question[q.id] = {"ok": False, "error": str(e)}

    if failures:
        return GateResult(
            name="G7_dry_run",
            ok=False,
            detail={"questions": per_question},
            message="; ".join(failures),
        )
    return GateResult(name="G7_dry_run", ok=True, detail={"questions": per_question})


# ---------- helpers -----------------------------------------------------------

def _tiny_jpeg() -> bytes:
    """A 1x1 white JPEG, hard-coded so G3 doesn't depend on opencv import order."""
    # Smallest valid JPEG (1x1 white) — produced once and inlined.
    return bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605"
        "08070707090908"
        # short-form: just include a real minimal JPEG via numpy + cv2 fallback if available
    ) or b""


def _question_to_json_schema(q) -> dict[str, Any]:
    """Wrap a Question.output_schema into the OpenAI json_schema response_format payload."""
    return {
        "name": q.id,
        "schema": {
            "type": "object",
            "properties": q.output_schema.properties,
            "required": q.output_schema.required,
            "additionalProperties": False,
        },
        "strict": False,
    }


# Replace the inlined hex with a proper opencv-based 1x1 jpeg generator.
def _tiny_jpeg() -> bytes:  # noqa: F811
    import cv2

    arr = np.full((1, 1, 3), 255, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", arr)
    if not ok:
        raise RuntimeError("failed to build tiny JPEG")
    return buf.tobytes()
