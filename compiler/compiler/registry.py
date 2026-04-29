"""Registry: commit versioned, SHA256-hashed DSL to Postgres only (no S3)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compiler.db.models import DSLRegistry


def canonical_sha256(dsl: dict[str, Any]) -> str:
    """SHA256 of the canonical JSON form (sorted keys, no whitespace)."""
    payload = json.dumps(dsl, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def next_version(session: AsyncSession, customer_id: str, inspection_id: str) -> int:
    stmt = (
        select(DSLRegistry.version)
        .where(
            DSLRegistry.customer_id == customer_id,
            DSLRegistry.inspection_id == inspection_id,
        )
        .order_by(DSLRegistry.version.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return (row or 0) + 1


async def commit_dsl(session: AsyncSession, dsl: dict[str, Any]) -> DSLRegistry:
    """Insert a new versioned DSL row. Caller must have already validated."""
    customer_id = dsl["metadata"]["customer_id"]
    inspection_id = dsl["metadata"]["inspection_id"]
    version = await next_version(session, customer_id, inspection_id)
    sha = canonical_sha256(dsl)

    entry = DSLRegistry(
        customer_id=customer_id,
        inspection_id=inspection_id,
        version=version,
        sha256=sha,
        dsl=dsl,
    )
    session.add(entry)
    await session.flush()
    return entry


__all__ = ["commit_dsl", "next_version", "canonical_sha256"]
