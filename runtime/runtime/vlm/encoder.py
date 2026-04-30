"""Frame encoder: downscale to IMAGE_MAX_DIMENSION and JPEG-encode.

Cost knob is the dimension (image-token count scales with dims), not the quality.
"""

from __future__ import annotations

import cv2
import numpy as np

from runtime.exceptions import EncodingFailed


class FrameEncoder:
    def __init__(self, max_dimension: int = 1024, jpeg_quality: int = 85):
        self.max_dimension = max_dimension
        self.jpeg_quality = jpeg_quality

    def encode(self, frame: np.ndarray) -> bytes:
        if frame is None or frame.size == 0:
            raise EncodingFailed("empty frame")
        h, w = frame.shape[:2]
        scale = self.max_dimension / max(h, w)
        if scale < 1.0:
            new_w, new_h = max(int(w * scale), 1), max(int(h * scale), 1)
            frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, int(self.jpeg_quality)])
        if not ok:
            raise EncodingFailed("cv2.imencode returned False")
        return buf.tobytes()
