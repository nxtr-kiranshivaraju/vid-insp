"""Adaptive cadence with severity floor (ARCH-9).

When recent answers are stable, slow down sampling (up to 3x base, capped at 30s).
Severity floor caps the slowdown so safety-critical rules never sample too slowly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any


@dataclass
class AdaptiveCadence:
    """Compute the next sample interval given base, severity, and recent answer stability."""

    SEVERITY_FLOORS: dict[str, timedelta | None] = None  # set in __post_init__
    stable_window: int = 5
    slow_factor: float = 3.0
    absolute_max: timedelta = timedelta(seconds=30)

    def __post_init__(self):
        if self.SEVERITY_FLOORS is None:
            self.SEVERITY_FLOORS = {
                "medium": None,
                "high": timedelta(seconds=10),
                "critical": timedelta(seconds=5),
                "safety_critical": timedelta(seconds=3),
            }

    def compute_interval(
        self, base: timedelta, severity: str, recent_answers: list[dict[str, Any] | None]
    ) -> timedelta:
        if self._is_stable(recent_answers):
            interval = min(base * self.slow_factor, self.absolute_max)
        else:
            interval = base

        floor = self.SEVERITY_FLOORS.get(severity)
        if floor is not None and interval > floor:
            interval = floor
        return interval

    def _is_stable(self, recent: list[dict[str, Any] | None]) -> bool:
        recent = [a for a in recent if a is not None]
        if len(recent) < self.stable_window:
            return False
        sample = recent[-self.stable_window :]
        first = sample[0]
        return all(a == first for a in sample)
