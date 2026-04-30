"""Boot sequence: load DSL, run gates G3–G7, hand off to the orchestrator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.dsl import DSL, load_dsl_file, validate_g1, validate_g2

from runtime.config import Settings
from runtime.exceptions import BootFailure
from runtime.gates import (
    GateResult,
    gate_g3_vlm_access,
    gate_g4_cost_estimate,
    gate_g5_rtsp_reachability,
    gate_g6_notification_ping,
    gate_g7_dry_run,
)

log = logging.getLogger(__name__)


@dataclass
class BootReport:
    dsl: DSL | None
    gate_results: list[GateResult] = field(default_factory=list)
    failed_cameras: list[str] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "failed_cameras": self.failed_cameras,
            "gates": [
                {"name": g.name, "ok": g.ok, "detail": g.detail, "message": g.message}
                for g in self.gate_results
            ],
        }


def load_dsl(
    dsl_path: str | None,
    customer_id: str | None = None,
    inspection_id: str | None = None,
    version: int | None = None,
) -> DSL:
    """Load DSL from a file path. Registry loading is out of scope here (Issue 2)."""
    if dsl_path:
        return load_dsl_file(dsl_path)
    raise BootFailure(
        "no DSL source provided — registry loading is implemented by the compiler "
        "service (Issue 2); pass --dsl <path> for local development"
    )


async def run_preflight(
    dsl: DSL,
    *,
    settings: Settings,
    vlm_client,
    rtsp_probe=None,
    dispatcher=None,
) -> BootReport:
    """Re-validate DSL and run gates G3-G7 in order. Returns a populated BootReport.

    Caller (CLI's `run` vs `preflight`) decides whether to abort or proceed based on
    the report. `BootFailure` is raised here only on schema/cross-ref errors and
    abort-gate failures (G3, G7).
    """
    report = BootReport(dsl=dsl)

    # Defense-in-depth re-validation
    raw = dsl.model_dump()
    errors = validate_g1(raw) + validate_g2(dsl)
    if errors:
        report.aborted = True
        report.abort_reason = f"DSL validation failed: {errors}"
        raise BootFailure(report.abort_reason)

    # G3 — VLM access (abort)
    g3 = await gate_g3_vlm_access(vlm_client)
    report.gate_results.append(g3)
    if not g3.ok:
        report.aborted = True
        report.abort_reason = f"G3 failed: {g3.message}"
        raise BootFailure(report.abort_reason)

    # G4 — cost estimate (advisory)
    g4 = await gate_g4_cost_estimate(dsl)
    report.gate_results.append(g4)
    log.info("g4_cost_estimate", extra={"detail": g4.detail})

    # G5 — RTSP reachability (partial)
    g5 = await gate_g5_rtsp_reachability(dsl.cameras, probe=rtsp_probe)
    report.gate_results.append(g5)
    cam_results = g5.detail.get("cameras", {})
    report.failed_cameras = [cid for cid, r in cam_results.items() if not r.get("ok")]
    if not g5.ok:
        report.aborted = True
        report.abort_reason = "G5 failed: no cameras reachable"
        raise BootFailure(report.abort_reason)

    # G6 — notification ping (advisory)
    g6 = await gate_g6_notification_ping(dsl.alerts.channels, dispatcher=dispatcher)
    report.gate_results.append(g6)

    # G7 — dry run (abort)
    g7 = await gate_g7_dry_run(dsl, vlm_client)
    report.gate_results.append(g7)
    if not g7.ok:
        report.aborted = True
        report.abort_reason = f"G7 failed: {g7.message}"
        raise BootFailure(report.abort_reason)

    return report
