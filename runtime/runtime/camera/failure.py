"""Camera failure handler with exponential backoff (ARCH-6)."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)


class CameraFailureHandler:
    """Tracks consecutive RTSP failures per camera. Emits observation-starved alert.

    Reset callbacks (e.g. clearing temporal buffers for a camera on reconnect) are
    registered with `register_reset_callback(camera_id, callable)`.
    """

    def __init__(
        self,
        *,
        max_retries: int = 10,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        starved_threshold: int = 5,
        on_starved: Callable[[str], Awaitable[Any]] | None = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.starved_threshold = starved_threshold
        self._on_starved = on_starved
        self.consecutive_failures: dict[str, int] = defaultdict(int)
        self._reset_callbacks: dict[str, list[Callable[[str], None]]] = defaultdict(list)
        self._starved_emitted: set[str] = set()

    def register_reset_callback(self, camera_id: str, callback: Callable[[str], None]) -> None:
        self._reset_callbacks[camera_id].append(callback)

    async def on_failure(self, camera_id: str, error: Exception) -> None:
        self.consecutive_failures[camera_id] += 1
        n = self.consecutive_failures[camera_id]
        log.warning(
            "camera_failure",
            extra={"camera_id": camera_id, "consecutive": n, "error": str(error)},
        )
        if n >= self.starved_threshold and camera_id not in self._starved_emitted:
            self._starved_emitted.add(camera_id)
            if self._on_starved is not None:
                try:
                    await self._on_starved(camera_id)
                except Exception as e:
                    log.exception("on_starved_callback_failed", extra={"error": str(e)})
        delay = min(self.base_delay * (2 ** min(n, 16)), self.max_delay)
        await asyncio.sleep(delay)

    def on_reconnect(self, camera_id: str) -> None:
        """Called by FrameSampler after a successful reconnect.

        Resets per-camera failure count and fires reset callbacks (rule engine clears
        temporal buffers so sustained_for can't span the gap).
        """
        prev = self.consecutive_failures.get(camera_id, 0)
        self.consecutive_failures[camera_id] = 0
        self._starved_emitted.discard(camera_id)
        if prev > 0:
            log.info("camera_reconnect", extra={"camera_id": camera_id, "had_failures": prev})
        for cb in self._reset_callbacks.get(camera_id, []):
            try:
                cb(camera_id)
            except Exception as e:
                log.exception("reset_callback_failed", extra={"error": str(e)})
