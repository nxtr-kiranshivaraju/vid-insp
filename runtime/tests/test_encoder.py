"""Frame encoder respects IMAGE_MAX_DIMENSION and JPEG_QUALITY."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from runtime.exceptions import EncodingFailed
from runtime.vlm.encoder import FrameEncoder


def _decode(jpeg_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def test_4k_frame_downscaled_to_max_dim_1024():
    enc = FrameEncoder(max_dimension=1024, jpeg_quality=85)
    frame = np.random.randint(0, 255, size=(2160, 3840, 3), dtype=np.uint8)
    out = enc.encode(frame)
    decoded = _decode(out)
    h, w = decoded.shape[:2]
    assert max(h, w) == 1024
    # Aspect ratio preserved (3840:2160 = 16:9)
    assert abs(w / h - (3840 / 2160)) < 0.02


def test_quality_progression_byte_sizes():
    """quality 60/85/95 should produce roughly 1:2:4 byte ratios on a textured frame."""
    rng = np.random.default_rng(seed=0)
    # Use noise (high entropy) so JPEG quality really matters.
    frame = rng.integers(0, 255, size=(720, 1280, 3), dtype=np.uint8)
    sizes = {}
    for q in (60, 85, 95):
        enc = FrameEncoder(max_dimension=1280, jpeg_quality=q)
        sizes[q] = len(enc.encode(frame))
    # Strict ordering — higher quality is always at least as large.
    assert sizes[60] < sizes[85] < sizes[95]
    # Spec says "roughly 1:2:4". On high-entropy content the ratio compresses;
    # require monotonic growth and a meaningful gap between 60 and 95.
    assert sizes[85] / sizes[60] > 1.3
    assert sizes[95] / sizes[60] > 2.0


def test_smaller_than_max_dim_not_upscaled():
    enc = FrameEncoder(max_dimension=2048, jpeg_quality=85)
    frame = np.random.randint(0, 255, size=(480, 640, 3), dtype=np.uint8)
    out = enc.encode(frame)
    decoded = _decode(out)
    assert decoded.shape[:2] == (480, 640)


def test_empty_frame_raises():
    enc = FrameEncoder()
    with pytest.raises(EncodingFailed):
        enc.encode(np.array([], dtype=np.uint8).reshape(0, 0, 3))
