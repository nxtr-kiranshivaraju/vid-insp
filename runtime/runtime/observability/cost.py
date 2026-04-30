"""Cost meter — tracks $/camera/question and rolling $/hour, $/day.

Token cost is computed from the OpenAI-shaped `usage` dict returned by the LLM client.
Hourly snapshots are persisted to Postgres so /cost can answer queries across restarts.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from runtime.clock import utcnow

log = logging.getLogger(__name__)


@dataclass
class CostEntry:
    timestamp: datetime
    cost_usd: float


@dataclass
class CostMeter:
    deployment_id: str
    cost_per_mtok_input: float = 3.0
    cost_per_mtok_output: float = 15.0
    pool: Any | None = None
    # In-memory rolling window per (camera_id, question_id) → deque[CostEntry]
    rolling: dict[tuple[str, str], deque[CostEntry]] = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=10000)))
    # Hour bucket sums waiting to be persisted: (camera_id, question_id, hour_iso) → (calls, usd)
    pending: dict[tuple[str, str, datetime], tuple[int, float]] = field(default_factory=dict)

    def record(self, camera_id: str, question_id: str, usage: dict[str, int] | None) -> float:
        usage = usage or {}
        in_tok = usage.get("prompt_tokens", 0) or 0
        out_tok = usage.get("completion_tokens", 0) or 0
        cost = (in_tok / 1_000_000.0) * self.cost_per_mtok_input + (
            out_tok / 1_000_000.0
        ) * self.cost_per_mtok_output
        ts = utcnow()
        self.rolling[(camera_id, question_id)].append(CostEntry(timestamp=ts, cost_usd=cost))
        hour = ts.replace(minute=0, second=0, microsecond=0)
        prev_calls, prev_cost = self.pending.get((camera_id, question_id, hour), (0, 0.0))
        self.pending[(camera_id, question_id, hour)] = (prev_calls + 1, prev_cost + cost)
        return cost

    def _sum_window(self, key: tuple[str, str], window: timedelta) -> float:
        cutoff = utcnow() - window
        return float(sum(e.cost_usd for e in self.rolling.get(key, ()) if e.timestamp >= cutoff))

    def per_camera_question(self) -> list[dict[str, Any]]:
        out = []
        for (camera_id, question_id), entries in self.rolling.items():
            hour = self._sum_window((camera_id, question_id), timedelta(hours=1))
            day = self._sum_window((camera_id, question_id), timedelta(days=1))
            out.append({
                "camera_id": camera_id,
                "question_id": question_id,
                "usd_last_hour": round(hour, 6),
                "usd_last_day": round(day, 6),
                "calls_total": len(entries),
            })
        return out

    def totals(self) -> dict[str, float]:
        hour = sum(self._sum_window(k, timedelta(hours=1)) for k in self.rolling)
        day = sum(self._sum_window(k, timedelta(days=1)) for k in self.rolling)
        return {"usd_last_hour": round(hour, 6), "usd_last_day": round(day, 6)}

    async def persist_pending(self) -> int:
        """Flush pending hour-bucket aggregates to Postgres. Returns rows written.

        On insert failure we fold the unwritten rows back into `pending` so the
        next flush picks them up. The "swap then write" pattern means concurrent
        `record()` calls land in a fresh dict, not the one we're draining.
        """
        if self.pool is None or not self.pending:
            return 0
        rows = self.pending
        self.pending = {}
        written = 0
        for (camera_id, question_id, hour), (calls, cost) in list(rows.items()):
            try:
                await self.pool.execute(
                    "INSERT INTO cost_snapshots "
                    "(deployment_id, camera_id, question_id, hour, call_count, cost_usd) "
                    "VALUES ($1, $2, $3, $4, $5, $6) "
                    "ON CONFLICT (deployment_id, camera_id, question_id, hour) DO UPDATE "
                    "SET call_count = cost_snapshots.call_count + EXCLUDED.call_count, "
                    "    cost_usd  = cost_snapshots.cost_usd  + EXCLUDED.cost_usd",
                    self.deployment_id,
                    camera_id,
                    question_id,
                    hour,
                    calls,
                    cost,
                )
                written += 1
            except Exception as e:
                # Re-fold the unwritten row plus everything after it.
                log.warning("cost_persist_row_failed", extra={"error": str(e)})
                key = (camera_id, question_id, hour)
                prev_calls, prev_cost = self.pending.get(key, (0, 0.0))
                self.pending[key] = (prev_calls + calls, prev_cost + cost)
        return written

    async def run_persist_loop(self, interval_s: float = 300.0) -> None:
        while True:
            try:
                await asyncio.sleep(interval_s)
                n = await self.persist_pending()
                if n:
                    log.info("cost_persisted", extra={"rows": n})
            except asyncio.CancelledError:
                # Final flush on shutdown
                try:
                    await self.persist_pending()
                except Exception:
                    pass
                raise
            except Exception as e:
                log.exception("cost_persist_failed", extra={"error": str(e)})
