"""Daily session garbage collector. Deletes uncommitted sessions older than TTL."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from compiler.config import get_settings
from compiler.db import session as db_session
from compiler.db.models import Session

log = logging.getLogger(__name__)


async def gc_once() -> int:
    """Delete uncommitted sessions older than TTL. Returns rows deleted."""
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.session_ttl_days)
    async with db_session.session_factory()() as db:
        stmt = (
            delete(Session)
            .where(Session.status != "committed")
            .where(Session.updated_at < cutoff)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount or 0


async def run_forever() -> None:
    settings = get_settings()
    while True:
        try:
            n = await gc_once()
            if n:
                log.info("session GC removed %d expired sessions", n)
        except Exception:  # noqa: BLE001 — daemon loop must not die
            log.exception("session GC failed")
        await asyncio.sleep(settings.gc_interval_seconds)


__all__ = ["gc_once", "run_forever"]
