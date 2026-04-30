"""ARCH-9: adaptive cadence with severity floor."""

from __future__ import annotations

from datetime import timedelta

from runtime.engine.cadence import AdaptiveCadence


def test_unstable_returns_base():
    c = AdaptiveCadence()
    interval = c.compute_interval(timedelta(seconds=5), "medium", recent_answers=[
        {"x": 1}, {"x": 2}, {"x": 1}, {"x": 2}, {"x": 1}
    ])
    assert interval == timedelta(seconds=5)


def test_stable_medium_slows_to_3x():
    c = AdaptiveCadence()
    same = [{"x": 1}] * 5
    interval = c.compute_interval(timedelta(seconds=5), "medium", recent_answers=same)
    assert interval == timedelta(seconds=15)


def test_safety_critical_floor_caps_slowdown():
    c = AdaptiveCadence()
    same = [{"x": 1}] * 5
    # base 5s; stable would slow to 15s; floor for safety_critical is 3s.
    interval = c.compute_interval(timedelta(seconds=5), "safety_critical", recent_answers=same)
    assert interval == timedelta(seconds=3)


def test_critical_floor():
    c = AdaptiveCadence()
    same = [{"x": 1}] * 5
    interval = c.compute_interval(timedelta(seconds=5), "critical", recent_answers=same)
    assert interval == timedelta(seconds=5)


def test_high_floor():
    c = AdaptiveCadence()
    same = [{"x": 1}] * 5
    interval = c.compute_interval(timedelta(seconds=10), "high", recent_answers=same)
    assert interval == timedelta(seconds=10)


def test_absolute_max_caps_slowdown():
    c = AdaptiveCadence()
    same = [{"x": 1}] * 5
    # base 20s -> 60s, but capped at 30s absolute_max; medium has no floor
    interval = c.compute_interval(timedelta(seconds=20), "medium", recent_answers=same)
    assert interval == timedelta(seconds=30)
