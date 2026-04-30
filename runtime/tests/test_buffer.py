"""ARCH-7: temporal buffer with no_observation sentinel."""

from __future__ import annotations

from datetime import timedelta

from runtime.engine.buffer import Observation, TemporalBuffer


def test_window_returns_recent_only(_frozen_time):
    buf = TemporalBuffer()
    # 10 obs, one per minute starting 10 minutes ago
    for i in range(10):
        ts = _frozen_time.now - timedelta(minutes=10 - i)
        buf.append(Observation(timestamp=ts, answer={"x": i}, confidence=0.9))
    # last 5 minutes -> 5 observations
    out = buf.window_observations(timedelta(minutes=5))
    assert len(out) == 5


def test_gap_sentinel_recorded(_frozen_time):
    buf = TemporalBuffer()
    buf.append_gap()
    latest = buf.latest()
    assert latest is not None
    assert latest.is_gap is True
    assert latest.answer is None


def test_clear_empties_buffer(_frozen_time):
    buf = TemporalBuffer()
    buf.append(Observation(timestamp=_frozen_time.now, answer={"x": 1}, confidence=0.9))
    assert len(buf) == 1
    buf.clear()
    assert len(buf) == 0


def test_max_size_evicts_oldest(_frozen_time):
    buf = TemporalBuffer(max_size=3)
    for i in range(5):
        buf.append(Observation(timestamp=_frozen_time.now, answer={"x": i}, confidence=0.9))
    assert len(buf) == 3
    assert [o.answer["x"] for o in buf.buffer] == [2, 3, 4]
