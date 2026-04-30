"""Postgres pool helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


async def create_pool(database_url: str, min_size: int = 2, max_size: int = 10):
    """Create an asyncpg connection pool. Imported lazily so tests don't need asyncpg."""
    import asyncpg

    return await asyncpg.create_pool(database_url, min_size=min_size, max_size=max_size)


async def apply_migrations(pool: Any, migrations_dir: Path | None = None) -> int:
    """Apply every .sql file in migrations_dir, in lexicographic order. Idempotent."""
    if migrations_dir is None:
        migrations_dir = Path(__file__).parent / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    n = 0
    for f in files:
        sql = f.read_text(encoding="utf-8")
        await pool.execute(sql)
        n += 1
        log.info("migration_applied", extra={"file": f.name})
    return n
