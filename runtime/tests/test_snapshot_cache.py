"""ARCH-2: frame differencing dedup."""

from __future__ import annotations

from runtime.camera.snapshot_cache import SnapshotCache


def test_first_frame_is_not_equivalent(static_frame):
    cache = SnapshotCache(threshold=15.0)
    assert cache.is_scene_equivalent(static_frame) is False


def test_static_then_static_is_equivalent(static_frame):
    cache = SnapshotCache(threshold=15.0)
    cache.update(static_frame, {"violation_present": False, "confidence": 0.9})
    assert cache.is_scene_equivalent(static_frame) is True


def test_person_walking_past_does_not_trigger_new_call(static_frame, near_identical_frame):
    """A person occupying ~5% of a static scene stays under the default threshold."""
    cache = SnapshotCache(threshold=15.0)
    cache.update(static_frame, {"violation_present": False, "confidence": 0.9})
    assert cache.is_scene_equivalent(near_identical_frame) is True


def test_scene_change_triggers_new_call(static_frame, scene_change_frame):
    cache = SnapshotCache(threshold=15.0)
    cache.update(static_frame, {"violation_present": False, "confidence": 0.9})
    assert cache.is_scene_equivalent(scene_change_frame) is False


def test_clear_resets_state(static_frame):
    cache = SnapshotCache(threshold=15.0)
    cache.update(static_frame, {"violation_present": False, "confidence": 0.9})
    cache.clear()
    assert cache.last_frame is None
    assert cache.last_answer is None
    assert cache.is_scene_equivalent(static_frame) is False
