"""Aggregated health for the read-only API."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from runtime.clock import utcnow


@dataclass
class CameraHealth:
    camera_id: str
    last_frame_at: datetime | None = None
    consecutive_failures: int = 0
    retry_count_total: int = 0
    rtsp_open: bool = False


@dataclass
class HealthMonitor:
    cameras: dict[str, CameraHealth] = field(default_factory=dict)
    gap_count_per_question: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    started_at: datetime = field(default_factory=utcnow)

    def init_camera(self, camera_id: str) -> None:
        self.cameras.setdefault(camera_id, CameraHealth(camera_id=camera_id))

    def mark_frame(self, camera_id: str) -> None:
        c = self.cameras.setdefault(camera_id, CameraHealth(camera_id=camera_id))
        c.last_frame_at = utcnow()
        c.rtsp_open = True

    def mark_camera_failure(self, camera_id: str) -> None:
        c = self.cameras.setdefault(camera_id, CameraHealth(camera_id=camera_id))
        c.consecutive_failures += 1
        c.retry_count_total += 1
        c.rtsp_open = False

    def mark_camera_reconnect(self, camera_id: str) -> None:
        c = self.cameras.setdefault(camera_id, CameraHealth(camera_id=camera_id))
        c.consecutive_failures = 0
        c.rtsp_open = True

    def mark_gap(self, question_id: str) -> None:
        self.gap_count_per_question[question_id] += 1

    def snapshot(self, vlm_client=None) -> dict[str, Any]:
        cams = []
        for c in self.cameras.values():
            cams.append({
                "camera_id": c.camera_id,
                "rtsp_open": c.rtsp_open,
                "last_frame_at": c.last_frame_at.isoformat() if c.last_frame_at else None,
                "consecutive_failures": c.consecutive_failures,
                "retry_count_total": c.retry_count_total,
            })

        coercion = []
        if vlm_client is not None:
            calls = getattr(vlm_client, "call_counts", {})
            errs = getattr(vlm_client, "coercion_error_counts", {})
            for key, n_calls in calls.items():
                err_n = errs.get(key, 0)
                qid, provider = key
                coercion.append({
                    "question_id": qid,
                    "provider": provider,
                    "calls": n_calls,
                    "coercion_errors": err_n,
                    "rate": (err_n / n_calls) if n_calls else 0.0,
                })

        return {
            "started_at": self.started_at.isoformat(),
            "cameras": cams,
            "vlm_coercion": coercion,
            "gaps_per_question": dict(self.gap_count_per_question),
        }
