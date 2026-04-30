"""Frame-differencing snapshot cache (ARCH-2).

Reuses the last VLM answer when the new frame is visually equivalent to the cached one.
Threshold is mean-absolute-pixel-difference on a 256x256 grayscale downscale.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


class SnapshotCache:
    """Per (camera, question) cache. ~10 lines of core logic; threshold is tunable."""

    def __init__(self, threshold: float = 15.0):
        # threshold: mean absolute pixel difference below which frames are "same scene".
        # Static cameras get a low diff (~5-10) for transient motion; scene change gets >30.
        self.threshold = threshold
        self.last_frame: np.ndarray | None = None
        self.last_answer: dict | None = None

    def is_scene_equivalent(self, new_frame: np.ndarray) -> bool:
        if self.last_frame is None:
            return False
        a = cv2.cvtColor(cv2.resize(self.last_frame, (256, 256)), cv2.COLOR_BGR2GRAY)
        b = cv2.cvtColor(cv2.resize(new_frame, (256, 256)), cv2.COLOR_BGR2GRAY)
        diff = float(np.mean(np.abs(a.astype(np.float32) - b.astype(np.float32))))
        return diff < self.threshold

    def update(self, frame: np.ndarray, answer: dict | None) -> None:
        self.last_frame = frame
        self.last_answer = answer

    def clear(self) -> None:
        self.last_frame = None
        self.last_answer = None
