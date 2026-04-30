"""Append-only observation log (ARCH-5).

Write path is the only path used during runtime operation; reads are for /observations
audit queries on the read-only API. The pool is asyncpg-shaped but tests pass a fake
pool with the same `execute`/`fetch` surface.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Protocol

from runtime.engine.buffer import Observation

log = logging.getLogger(__name__)


class _PoolLike(Protocol):
    async def execute(self, *args: Any, **kwargs: Any) -> Any: ...
    async def fetch(self, *args: Any, **kwargs: Any) -> list[Any]: ...


class ObservationLog:
    """Append-only Postgres log."""

    def __init__(self, pool: _PoolLike, deployment_id: str):
        self.pool = pool
        self.deployment_id = deployment_id

    async def record(self, camera_id: str, question_id: str, obs: Observation) -> None:
        # Pass the dict straight through. The asyncpg pool registers a JSONB codec
        # at acquire-time (db.pool.create_pool), so the bind is encoded once.
        # Pre-`json.dumps()`-ing here would produce a JSON-encoded string-of-JSON.
        await self.pool.execute(
            "INSERT INTO observations "
            "(deployment_id, camera_id, question_id, timestamp, answer, confidence, is_gap) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            self.deployment_id,
            camera_id,
            question_id,
            obs.timestamp,
            obs.answer,
            float(obs.confidence),
            bool(obs.is_gap),
        )

    async def query(
        self,
        *,
        camera_id: str | None = None,
        question_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses = ["deployment_id = $1"]
        params: list[Any] = [self.deployment_id]
        i = 2
        if camera_id:
            clauses.append(f"camera_id = ${i}")
            params.append(camera_id)
            i += 1
        if question_id:
            clauses.append(f"question_id = ${i}")
            params.append(question_id)
            i += 1
        if since:
            clauses.append(f"timestamp >= ${i}")
            params.append(since)
            i += 1
        if until:
            clauses.append(f"timestamp <= ${i}")
            params.append(until)
            i += 1
        sql = (
            "SELECT camera_id, question_id, timestamp, answer, confidence, is_gap "
            f"FROM observations WHERE {' AND '.join(clauses)} "
            f"ORDER BY timestamp DESC LIMIT ${i} OFFSET ${i + 1}"
        )
        params.extend([int(limit), int(offset)])
        rows = await self.pool.fetch(sql, *params)
        out = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get("answer"), str):
                try:
                    d["answer"] = json.loads(d["answer"])
                except (TypeError, ValueError):
                    pass
            if isinstance(d.get("timestamp"), datetime):
                d["timestamp"] = d["timestamp"].isoformat()
            out.append(d)
        return out
