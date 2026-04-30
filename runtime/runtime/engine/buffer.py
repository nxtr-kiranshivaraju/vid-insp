"""Temporal ring buffer with `no_observation` sentinel (ARCH-7)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from runtime.clock import utcnow


@dataclass
class Observation:
    timestamp: datetime
    answer: dict | None  # None = no_observation sentinel
    confidence: float
    is_gap: bool = False  # True when answer is None


class TemporalBuffer:
    """Per (camera, question) ring buffer."""

    def __init__(self, max_size: int = 1000):
        self.buffer: deque[Observation] = deque(maxlen=max_size)

    def append(self, obs: Observation) -> None:
        self.buffer.append(obs)

    def append_gap(self, timestamp: datetime | None = None) -> None:
        ts = timestamp or utcnow()
        self.buffer.append(
            Observation(timestamp=ts, answer=None, confidence=0.0, is_gap=True)
        )

    def latest(self) -> Observation | None:
        return self.buffer[-1] if self.buffer else None

    def window_observations(self, window: timedelta) -> list[Observation]:
        cutoff = utcnow() - window
        return [o for o in self.buffer if o.timestamp >= cutoff]

    def clear(self) -> None:
        self.buffer.clear()

    def __len__(self) -> int:
        return len(self.buffer)
