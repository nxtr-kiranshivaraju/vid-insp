"""Gate-level tests: G3, G5, G7, plus full preflight orchestration."""

from __future__ import annotations

from typing import Any

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

from runtime.boot import run_preflight
from runtime.config import Settings
from runtime.exceptions import BootFailure
from runtime.gates import (
    gate_g3_vlm_access,
    gate_g5_rtsp_reachability,
    gate_g7_dry_run,
)


def _dsl() -> DSL:
    return DSL(
        deployment=Deployment(id="d1", customer_id="c1", inspection_id="i1"),
        cameras=[
            Camera(id="cam_a", rtsp_url="rtsp://a"),
            Camera(id="cam_b", rtsp_url="rtsp://b"),
        ],
        questions=[
            Question(
                id="q_a",
                camera="cam_a",
                prompt="?",
                output_schema=OutputSchema(
                    type="object",
                    properties={
                        "violation_present": {"type": "boolean"},
                        "confidence": {"type": "number"},
                    },
                    required=["violation_present", "confidence"],
                ),
            )
        ],
        rules=[Rule(
            id="r1",
            on=RuleOn(camera="cam_a", question="q_a"),
            when={"violation_present": True},
            sustained_for="30s",
            sustained_threshold=0.7,
            severity="high",
            cooldown="5m",
            actions=[RuleAction(type="alert", channel_ref="ch1", message="m")],
        )],
        alerts=AlertsBlock(channels=[
            AlertChannel(id="ch1", type="slack_webhook", url="https://example.test/x")
        ]),
    )


class _GoodVLM:
    """Minimal VLM stub that satisfies G3 + G7."""

    def __init__(self):
        self.coercion_error_counts = {}
        self.call_counts = {}

    async def test_call(self, jpeg_bytes: bytes) -> bool:
        return True

    async def ask(self, prompt: str, jpeg_bytes: bytes, output_schema: dict, *, question_id: str = "unknown"):
        from runtime.vlm.coercion import CoercedResponse
        return CoercedResponse(
            data={"violation_present": False, "confidence": 0.9},
            coercion_errors=[],
            raw={"violation_present": False, "confidence": 0.9},
        )


class _BadVLM(_GoodVLM):
    async def test_call(self, jpeg_bytes: bytes) -> bool:
        raise RuntimeError("vlm endpoint unreachable")


class _BrokenVLM(_GoodVLM):
    async def ask(self, prompt: str, jpeg_bytes: bytes, output_schema: dict, *, question_id: str = "unknown"):
        raise RuntimeError("schema-violation explosion")


async def _probe_all_ok(rtsp_url: str):
    return True, {"resolution": "1280x720", "fps_estimate": 25.0}


async def _probe_first_fails(rtsp_url: str):
    if "a" in rtsp_url:
        return False, {"error": "timeout"}
    return True, {"resolution": "1280x720", "fps_estimate": 25.0}


async def _probe_all_fail(rtsp_url: str):
    return False, {"error": "timeout"}


# ---------------------------------------------------------------------------


async def test_g3_pass():
    r = await gate_g3_vlm_access(_GoodVLM())
    assert r.ok


async def test_g3_fail_aborts_preflight():
    with pytest.raises(BootFailure, match="G3"):
        await run_preflight(_dsl(), settings=Settings(), vlm_client=_BadVLM(),
                            rtsp_probe=_probe_all_ok)


async def test_g5_partial_one_camera_failed():
    dsl = _dsl()
    r = await gate_g5_rtsp_reachability(dsl.cameras, probe=_probe_first_fails)
    assert r.ok  # partial pass — at least one camera works
    cam_results = r.detail["cameras"]
    assert cam_results["cam_a"]["ok"] is False
    assert cam_results["cam_b"]["ok"] is True


async def test_g5_all_fail_aborts():
    dsl = _dsl()
    with pytest.raises(BootFailure, match="G5"):
        await run_preflight(dsl, settings=Settings(), vlm_client=_GoodVLM(),
                            rtsp_probe=_probe_all_fail)


async def test_g7_fail_aborts():
    dsl = _dsl()
    with pytest.raises(BootFailure, match="G7"):
        await run_preflight(dsl, settings=Settings(), vlm_client=_BrokenVLM(),
                            rtsp_probe=_probe_all_ok)


async def test_full_preflight_pass_records_failed_cameras():
    dsl = _dsl()
    report = await run_preflight(
        dsl, settings=Settings(), vlm_client=_GoodVLM(), rtsp_probe=_probe_first_fails
    )
    assert not report.aborted
    assert report.failed_cameras == ["cam_a"]
    assert all(g.name for g in report.gate_results)
