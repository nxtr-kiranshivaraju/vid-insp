"""Daily GC job: deletes uncommitted sessions older than TTL."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from compiler.db.models import Session


@pytest.mark.asyncio
async def test_gc_deletes_old_uncommitted_keeps_committed_and_recent(
    db, db_engine, monkeypatch
):
    now = datetime.now(timezone.utc)
    cutoff_old = now - timedelta(days=8)
    recent = now - timedelta(days=2)

    db.add_all(
        [
            Session(
                paragraphs=["x"],
                status="created",
                updated_at=cutoff_old,
                created_at=cutoff_old,
            ),
            Session(
                paragraphs=["x"],
                status="committed",
                updated_at=cutoff_old,
                created_at=cutoff_old,
            ),
            Session(
                paragraphs=["x"],
                status="created",
                updated_at=recent,
                created_at=recent,
            ),
        ]
    )
    await db.commit()

    # Point the GC at the test engine.
    from compiler.db import session as db_session_mod
    from compiler import gc as gc_mod
    from sqlalchemy.ext.asyncio import async_sessionmaker

    Sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(db_session_mod, "session_factory", lambda: Sessionmaker)

    deleted = await gc_mod.gc_once()
    assert deleted == 1

    rows = (await db.execute(select(Session))).scalars().all()
    statuses = sorted(r.status for r in rows)
    assert statuses == ["committed", "created"]  # only the recent + committed survive
