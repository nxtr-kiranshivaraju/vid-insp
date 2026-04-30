"""Retention job: daily delete of `observations` rows older than the configured window."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from runtime.clock import utcnow

log = logging.getLogger(__name__)


class RetentionJob:
    def __init__(self, pool: Any, retention_days: int = 90, interval_s: float = 86400.0):
        self.pool = pool
        self.retention_days = retention_days
        self.interval_s = interval_s

    async def run_once(self) -> int:
        cutoff = utcnow() - timedelta(days=self.retention_days)
        # asyncpg returns "DELETE n" — peel off the count for the log.
        result = await self.pool.execute(
            "DELETE FROM observations WHERE timestamp < $1", cutoff
        )
        deleted = 0
        if isinstance(result, str) and result.startswith("DELETE"):
            try:
                deleted = int(result.split()[1])
            except (IndexError, ValueError):
                deleted = 0
        elif isinstance(result, int):
            deleted = result
        log.info(
            "retention_cleanup",
            extra={"deleted_rows": deleted, "cutoff": cutoff.isoformat()},
        )
        return deleted

    async def run_forever(self, *, run_immediately: bool = True) -> None:
        """Run the retention sweep on a schedule.

        Defaults to running once at startup so backlog from a long downtime is cleaned
        up immediately, not after `interval_s` (24h by default).
        """
        if run_immediately:
            try:
                await self.run_once()
            except Exception as e:
                log.exception("retention_initial_run_failed", extra={"error": str(e)})
        while True:
            try:
                await asyncio.sleep(self.interval_s)
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.exception("retention_job_failed", extra={"error": str(e)})
