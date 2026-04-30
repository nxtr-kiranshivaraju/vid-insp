"""Top-level exception hierarchy for the runtime."""

from __future__ import annotations


class RuntimeServiceError(Exception):
    pass


class BootFailure(RuntimeServiceError):
    """Boot aborted (raised by gates G3/G7 on hard failure or DSL re-validation)."""


class RTSPOpenFailed(RuntimeServiceError):
    def __init__(self, camera_id: str, message: str = ""):
        self.camera_id = camera_id
        super().__init__(f"camera {camera_id}: {message or 'failed to open RTSP stream'}")


class EncodingFailed(RuntimeServiceError):
    pass


class CoercionFailed(RuntimeServiceError):
    """Raised only if coercion can't recover at all (e.g. invalid JSON top-level)."""
