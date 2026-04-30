"""Postgres pool helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


_SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""


async def create_pool(database_url: str, min_size: int = 2, max_size: int = 10):
    """Create an asyncpg connection pool with a JSONB codec registered.

    Without the codec, asyncpg refuses to bind Python dicts to jsonb columns and
    callers fall back to `json.dumps(...)` — which then double-encodes if a future
    reader assumes the JSONB column already came back as a Python object.
    """
    import asyncpg

    async def _init(conn):
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )
        await conn.set_type_codec(
            "json",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )

    return await asyncpg.create_pool(
        database_url, min_size=min_size, max_size=max_size, init=_init
    )


async def apply_migrations(pool: Any, migrations_dir: Path | None = None) -> int:
    """Apply every .sql file in `migrations_dir` exactly once.

    Each file is wrapped in its own transaction (via the connection), and the
    `schema_migrations` table records what's already been applied so re-runs
    only execute new files. Returns the number of migrations *applied this call*.
    """
    if migrations_dir is None:
        migrations_dir = Path(__file__).parent / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        return 0

    applied_count = 0
    # asyncpg pools expose `acquire()`; the FakePool used in tests provides a
    # no-op transaction shim that satisfies the same surface.
    async with _maybe_acquire(pool) as conn:
        await conn.execute(_SCHEMA_MIGRATIONS_DDL)
        already = await _fetch_applied(conn)

    for f in files:
        if f.name in already:
            log.info("migration_skipped", extra={"file": f.name})
            continue
        sql = f.read_text(encoding="utf-8")
        async with _maybe_acquire(pool) as conn:
            tx = _maybe_transaction(conn)
            async with tx:
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES ($1)", f.name
                )
        applied_count += 1
        log.info("migration_applied", extra={"file": f.name})
    return applied_count


async def _fetch_applied(conn) -> set[str]:
    rows = await conn.fetch("SELECT filename FROM schema_migrations")
    out: set[str] = set()
    for row in rows:
        try:
            out.add(row["filename"])
        except (KeyError, TypeError):
            try:
                out.add(row[0])
            except Exception:
                continue
    return out


# ---- pool/connection compatibility shims (so tests can pass a FakePool) ------


class _DirectPoolCtx:
    def __init__(self, pool):
        self._pool = pool

    async def __aenter__(self):
        return self._pool

    async def __aexit__(self, *_):
        return False


def _maybe_acquire(pool: Any):
    """Use `pool.acquire()` if available, otherwise treat the pool itself as the conn.

    Real asyncpg pools require acquire(); the in-memory FakePool just is the conn.
    """
    if hasattr(pool, "acquire"):
        return pool.acquire()
    return _DirectPoolCtx(pool)


class _NullTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


def _maybe_transaction(conn):
    if hasattr(conn, "transaction"):
        return conn.transaction()
    return _NullTransaction()
