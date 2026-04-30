"""Registry: commit versioned, SHA256-hashed DSL to Postgres only (no S3)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from compiler.db.models import DSLRegistry

# Bound on retry attempts when racing for the next version number. Concurrent
# committers may both compute the same N from `next_version` and lose the
# UNIQUE(customer_id, inspection_id, version) race; the loser retries with N+1.
# A small bound is fine — wizard-style use means contention is rare.
MAX_VERSION_RETRIES = 5


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
    """Insert a new versioned DSL row. Caller must have already validated.

    Retries on UNIQUE collision: two concurrent committers can compute the same
    next version, and the database arbitrates via the UNIQUE constraint. Retry
    inside a SAVEPOINT so the outer transaction survives.
    """
    customer_id = dsl["metadata"]["customer_id"]
    inspection_id = dsl["metadata"]["inspection_id"]
    sha = canonical_sha256(dsl)

    last_error: IntegrityError | None = None
    for _ in range(MAX_VERSION_RETRIES):
        version = await next_version(session, customer_id, inspection_id)
        entry = DSLRegistry(
            customer_id=customer_id,
            inspection_id=inspection_id,
            version=version,
            sha256=sha,
            dsl=dsl,
        )
        try:
            async with session.begin_nested():
                session.add(entry)
                # Explicit flush so the UNIQUE collision raises here, inside
                # the SAVEPOINT, and the outer transaction stays usable.
                await session.flush()
        except IntegrityError as e:
            last_error = e
            continue
        return entry

    raise RuntimeError(
        f"failed to allocate next version for ({customer_id}, {inspection_id}) "
        f"after {MAX_VERSION_RETRIES} retries"
    ) from last_error


__all__ = ["commit_dsl", "next_version", "canonical_sha256", "MAX_VERSION_RETRIES"]
