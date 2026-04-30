"""Persistent RTSP frame sampler with 30s heartbeat (Resolved Decision #4)."""

from __future__ import annotations

import asyncio
import logging
import socket
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import cv2
import numpy as np

from runtime.clock import utcnow
from runtime.exceptions import RTSPOpenFailed

log = logging.getLogger(__name__)


class FrameSampler:
    """Persistent RTSP connection with heartbeat. One instance per camera."""

    def __init__(
        self,
        rtsp_url: str,
        camera_id: str,
        failure_handler,
        heartbeat_interval: float = 30.0,
        cv2_module: Any = cv2,
    ):
        self.rtsp_url = rtsp_url
        self.camera_id = camera_id
        self.cap: Any | None = None
        self.last_heartbeat_ok: datetime | None = None
        self.failure_handler = failure_handler
        self.heartbeat_interval = heartbeat_interval
        self._cv2 = cv2_module
        self._lock = asyncio.Lock()

    async def open(self) -> None:
        """Open the RTSP connection. Called at boot; reopened on heartbeat failure."""
        cap = await asyncio.to_thread(self._cv2.VideoCapture, self.rtsp_url)
        if not cap.isOpened():
            await asyncio.to_thread(cap.release)
            raise RTSPOpenFailed(self.camera_id, f"VideoCapture.isOpened() returned False")
        self.cap = cap
        self.last_heartbeat_ok = utcnow()
        log.info("rtsp_opened", extra={"camera_id": self.camera_id})

    async def heartbeat(self) -> bool:
        """Probe: can we still grab a frame? Caller runs this on a heartbeat_interval loop.

        Returns True on success. On failure, attempts a reconnect (which may itself fail —
        callers should treat False as "this camera is currently degraded").
        """
        if self.cap is None:
            await self._reconnect()
            return self.cap is not None
        ok = await asyncio.to_thread(self.cap.grab)
        if ok:
            self.last_heartbeat_ok = utcnow()
            return True
        await self._reconnect()
        return self.cap is not None

    async def _reconnect(self) -> None:
        """Close, reopen, signal failure handler (resets sustained_for state)."""
        async with self._lock:
            if self.cap is not None:
                try:
                    await asyncio.to_thread(self.cap.release)
                except Exception:
                    pass
                self.cap = None
            try:
                await self.open()
            except Exception as e:
                log.warning(
                    "rtsp_reconnect_failed",
                    extra={"camera_id": self.camera_id, "error": str(e)},
                )
                await self.failure_handler.on_failure(self.camera_id, e)
                return
            # Successful reconnect — notify the handler so sustained_for state resets.
            self.failure_handler.on_reconnect(self.camera_id)

    async def sample(self) -> np.ndarray | None:
        """Grab one frame from the persistent stream. Returns None on failure."""
        if self.cap is None:
            return None
        ret, frame = await asyncio.to_thread(self.cap.read)
        return frame if ret else None

    async def close(self) -> None:
        if self.cap is not None:
            try:
                await asyncio.to_thread(self.cap.release)
            except Exception:
                pass
            self.cap = None


async def probe_rtsp(
    rtsp_url: str,
    *,
    cv2_module: Any = cv2,
    timeout: float = 10.0,
    socket_timeout: float = 3.0,
) -> tuple[bool, dict[str, Any]]:
    """Open an RTSP stream, grab one frame, return (ok, detail).

    Used by G5 and the `/probe` HTTP endpoint. Performs a fast TCP probe first so
    unreachable hosts don't block on OpenCV's internal RTSP timeouts.
    """
    reachable, detail = await _tcp_reachable(rtsp_url, socket_timeout)
    if not reachable:
        return False, detail
    try:
        return await asyncio.wait_for(_probe_inner(rtsp_url, cv2_module), timeout=timeout)
    except asyncio.TimeoutError:
        return False, {"error": f"timed out after {timeout}s"}


async def _tcp_reachable(rtsp_url: str, timeout: float) -> tuple[bool, dict[str, Any]]:
    """Quick TCP reachability check on the RTSP host:port. Returns (ok, detail)."""
    parsed = urlparse(rtsp_url)
    host = parsed.hostname
    port = parsed.port or 554
    if not host:
        return False, {"error": f"could not parse host from URL: {rtsp_url!r}"}

    def _check() -> tuple[bool, str]:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True, ""
        except OSError as e:
            return False, str(e)

    ok, msg = await asyncio.to_thread(_check)
    return (ok, {"host": host, "port": port}) if ok else (
        False, {"error": f"tcp probe failed: {msg}", "host": host, "port": port}
    )


async def _probe_inner(rtsp_url: str, cv2_module: Any) -> tuple[bool, dict[str, Any]]:
    cap = await asyncio.to_thread(cv2_module.VideoCapture, rtsp_url)
    try:
        if not cap.isOpened():
            return False, {"error": "VideoCapture.isOpened() returned False"}
        ret, frame = await asyncio.to_thread(cap.read)
        if not ret or frame is None:
            return False, {"error": "could not read a frame"}
        h, w = frame.shape[:2]
        fps = float(cap.get(cv2_module.CAP_PROP_FPS) or 0.0)
        return True, {"resolution": f"{w}x{h}", "fps_estimate": fps}
    finally:
        try:
            await asyncio.to_thread(cap.release)
        except Exception:
            pass
