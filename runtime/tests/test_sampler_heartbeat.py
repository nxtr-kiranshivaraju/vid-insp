"""Sampler with mocked cv2.VideoCapture: heartbeat failure → reconnect → reset."""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pytest

from runtime.camera.failure import CameraFailureHandler
from runtime.camera.sampler import FrameSampler
from runtime.exceptions import RTSPOpenFailed


class FakeCapture:
    """A fake cv2.VideoCapture that returns frames N times then starts failing grabs."""

    def __init__(self, ok_grabs: int = 5, ok_reads: int = 5, open_ok: bool = True):
        self._open_ok = open_ok
        self._remaining_grabs = ok_grabs
        self._remaining_reads = ok_reads
        self.released = False

    def isOpened(self) -> bool:
        return self._open_ok

    def grab(self) -> bool:
        if self._remaining_grabs <= 0:
            return False
        self._remaining_grabs -= 1
        return True

    def read(self):
        if self._remaining_reads <= 0:
            return False, None
        self._remaining_reads -= 1
        return True, np.zeros((480, 640, 3), dtype=np.uint8)

    def release(self) -> None:
        self.released = True

    def get(self, _prop: int) -> float:
        return 25.0


class FakeCv2:
    """Hands out a queue of FakeCaptures so we can simulate reconnect cycles."""

    CAP_PROP_FPS = 5

    def __init__(self, captures: list[FakeCapture]):
        self.queue = list(captures)
        self.handed: list[FakeCapture] = []

    def VideoCapture(self, _url: str) -> FakeCapture:
        cap = self.queue.pop(0) if self.queue else FakeCapture(open_ok=False)
        self.handed.append(cap)
        return cap


async def test_open_then_heartbeat_ok():
    handler = CameraFailureHandler(starved_threshold=99)
    fake = FakeCv2([FakeCapture(ok_grabs=10)])
    sampler = FrameSampler("rtsp://x", "cam_a", handler, cv2_module=fake)
    await sampler.open()
    assert await sampler.heartbeat() is True


async def test_heartbeat_failure_triggers_reconnect_and_reset():
    handler = CameraFailureHandler(starved_threshold=99)
    reset_calls = []
    handler.register_reset_callback("cam_a", lambda cid: reset_calls.append(cid))

    fake = FakeCv2([
        FakeCapture(ok_grabs=0, ok_reads=0),  # initial: opens but every grab fails
        FakeCapture(ok_grabs=5),              # reconnect target
    ])
    sampler = FrameSampler("rtsp://x", "cam_a", handler, cv2_module=fake)
    await sampler.open()

    # First heartbeat: fails, triggers reconnect to second FakeCapture, on_reconnect fires.
    ok = await sampler.heartbeat()
    assert ok is True  # reconnect succeeded → cap is non-None
    assert reset_calls == ["cam_a"]
    assert handler.consecutive_failures.get("cam_a", 0) == 0


async def test_starved_alert_after_threshold(monkeypatch):
    starved = []

    async def on_starved(camera_id: str):
        starved.append(camera_id)

    handler = CameraFailureHandler(
        starved_threshold=3, base_delay=0.0, max_delay=0.0, on_starved=on_starved
    )

    # Patch asyncio.sleep so backoff doesn't slow the test.
    monkeypatch.setattr("runtime.camera.failure.asyncio.sleep", lambda *_: _noop())

    for _ in range(3):
        await handler.on_failure("cam_x", RuntimeError("boom"))

    assert starved == ["cam_x"]


async def _noop():
    return None


async def test_reconnect_resets_starved_state(monkeypatch):
    starved = []

    async def on_starved(camera_id: str):
        starved.append(camera_id)

    handler = CameraFailureHandler(starved_threshold=2, base_delay=0.0, on_starved=on_starved)
    monkeypatch.setattr("runtime.camera.failure.asyncio.sleep", lambda *_: _noop())

    await handler.on_failure("cam_x", RuntimeError("a"))
    await handler.on_failure("cam_x", RuntimeError("b"))
    assert starved == ["cam_x"]

    handler.on_reconnect("cam_x")
    # After reconnect, threshold counter resets and starved tag is cleared.
    await handler.on_failure("cam_x", RuntimeError("c"))
    await handler.on_failure("cam_x", RuntimeError("d"))
    assert starved == ["cam_x", "cam_x"]
