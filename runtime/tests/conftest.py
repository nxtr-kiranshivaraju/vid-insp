"""Shared fixtures: in-memory fake DB pool, a stub VLM client, fixture frames."""

from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pytest


# ---- DB pool stub ------------------------------------------------------------


class FakePool:
    """Minimal asyncpg-shaped pool that backs `observations`, `alert_history`,
    and `cost_snapshots` with Python dicts/lists. Good enough for the runtime's
    actual SQL surface; *not* a general SQL emulator."""

    def __init__(self):
        self.observations: list[dict[str, Any]] = []
        self.alert_history: list[dict[str, Any]] = []
        self.cost_snapshots: dict[tuple[str, str, str, datetime], dict[str, Any]] = {}
        self.executed: list[tuple[str, tuple]] = []

    async def execute(self, sql: str, *args: Any) -> str:
        self.executed.append((sql, args))
        s = sql.strip()
        s_low = s.lower()
        if s_low.startswith("create"):
            return "CREATE"
        if s_low.startswith("insert into observations"):
            d_id, cam, q, ts, ans, conf, gap = args
            self.observations.append({
                "deployment_id": d_id, "camera_id": cam, "question_id": q,
                "timestamp": ts, "answer": ans, "confidence": conf, "is_gap": gap,
            })
            return "INSERT 0 1"
        if s_low.startswith("insert into alert_history"):
            self.alert_history.append({
                "deployment_id": args[0], "rule_id": args[1], "camera_id": args[2],
                "severity": args[3], "message": args[4],
                "violator_description": args[5], "vote_ratio": args[6],
                "payload": args[7], "dispatched_at": args[8],
            })
            return "INSERT 0 1"
        if s_low.startswith("insert into cost_snapshots"):
            d_id, cam, q, hour, calls, cost = args
            key = (d_id, cam, q, hour)
            prev = self.cost_snapshots.get(key, {"call_count": 0, "cost_usd": 0.0})
            self.cost_snapshots[key] = {
                "deployment_id": d_id, "camera_id": cam, "question_id": q,
                "hour": hour,
                "call_count": prev["call_count"] + calls,
                "cost_usd": prev["cost_usd"] + cost,
            }
            return "INSERT 0 1"
        if s_low.startswith("delete from observations"):
            (cutoff,) = args
            before = len(self.observations)
            self.observations = [o for o in self.observations if o["timestamp"] >= cutoff]
            return f"DELETE {before - len(self.observations)}"
        return "OK"

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        s_low = sql.strip().lower()
        if "from observations" not in s_low:
            return []
        # Very small subset of WHERE handling — enough for the API shape.
        d_id = args[0]
        rows = [o for o in self.observations if o["deployment_id"] == d_id]
        # The remaining args are: optional camera/question/since/until + limit + offset.
        # We just sort and slice — the tests we care about don't exercise the filters.
        rows.sort(key=lambda r: r["timestamp"], reverse=True)
        # Last two args are limit and offset.
        limit, offset = args[-2], args[-1]
        return [dict(r) for r in rows[offset:offset + limit]]

    async def fetchval(self, sql: str, *args: Any) -> Any:
        return None

    async def close(self) -> None:
        return None


@pytest.fixture
def fake_pool() -> FakePool:
    return FakePool()


# ---- Stub VLM ----------------------------------------------------------------


@dataclass
class StubVLM:
    """Drop-in replacement for runtime.vlm.client.VLMClient."""

    canned_answer: dict[str, Any] = field(default_factory=lambda: {
        "violation_present": True,
        "violator_description": "person without hard hat near forklift",
        "confidence": 0.9,
    })
    raise_n: int = 0  # how many calls should raise before returning
    coercion_errors: list[str] = field(default_factory=list)
    last_usage: dict[str, int] | None = field(default_factory=lambda: {
        "prompt_tokens": 1000, "completion_tokens": 50, "total_tokens": 1050
    })
    last_provider: str = "primary"
    coercion_error_counts: dict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))
    call_counts: dict[tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))
    calls: int = 0

    async def ask(self, prompt: str, jpeg_bytes: bytes, output_schema: dict, *, question_id: str = "unknown"):
        from runtime.vlm.coercion import CoercedResponse
        self.calls += 1
        self.call_counts[(question_id, self.last_provider)] += 1
        if self.raise_n > 0:
            self.raise_n -= 1
            raise RuntimeError("stub: synthetic VLM failure")
        if self.coercion_errors:
            self.coercion_error_counts[(question_id, self.last_provider)] += 1
        return CoercedResponse(
            data=dict(self.canned_answer),
            coercion_errors=list(self.coercion_errors),
            raw=self.canned_answer,
        )

    async def test_call(self, jpeg_bytes: bytes) -> bool:
        return True


@pytest.fixture
def stub_vlm() -> StubVLM:
    return StubVLM()


# ---- Fixture frames ---------------------------------------------------------


@pytest.fixture
def static_frame() -> np.ndarray:
    rng = np.random.default_rng(seed=42)
    return rng.integers(low=80, high=180, size=(720, 1280, 3), dtype=np.uint8)


@pytest.fixture
def near_identical_frame(static_frame: np.ndarray) -> np.ndarray:
    """Same scene with mild noise (simulating a person walking past a static cam)."""
    out = static_frame.copy()
    # Add tiny noise everywhere
    rng = np.random.default_rng(seed=7)
    noise = rng.integers(-3, 3, size=out.shape, dtype=np.int16)
    out = np.clip(out.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    # Paint a small "person walking past" rectangle (~5% of pixels)
    out[300:380, 600:680, :] = 60
    return out


@pytest.fixture
def scene_change_frame() -> np.ndarray:
    """A wholly different scene — large mean-pixel diff."""
    return np.full((720, 1280, 3), 230, dtype=np.uint8)


@pytest.fixture(autouse=True)
def _frozen_time(monkeypatch):
    """Fix the clock for deterministic tests; individual tests can override."""

    class _Clock:
        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)

        def advance(self, **kwargs):
            self.now = self.now + timedelta(**kwargs)

    clock = _Clock()

    def _utcnow():
        return clock.now

    monkeypatch.setattr("runtime.clock.utcnow", _utcnow)
    # Also patch the imported reference inside modules that pulled it at import time.
    for mod in [
        "runtime.engine.buffer",
        "runtime.engine.rules",
        "runtime.engine.dispatcher",
        "runtime.observability.cost",
        "runtime.observability.health",
        "runtime.observability.retention",
        "runtime.observability.alerts",
        "runtime.engine.orchestrator",
        "runtime.camera.sampler",
    ]:
        try:
            monkeypatch.setattr(f"{mod}.utcnow", _utcnow, raising=False)
        except Exception:
            pass
    return clock
