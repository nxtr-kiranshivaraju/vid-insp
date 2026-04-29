"""Registry-level tests: SHA256 hashing and version-collision retry."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from compiler import registry
from compiler.db.models import DSLRegistry


def _dsl(customer: str = "acme", inspection: str = "warehouse_ppe") -> dict:
    return {
        "metadata": {
            "customer_id": customer,
            "inspection_id": inspection,
            "name": "Test",
        },
        "questions": [],
        "rules": [],
    }


@pytest.mark.asyncio
async def test_canonical_sha256_stable_across_key_order():
    a = {"metadata": {"a": 1, "b": 2}, "x": [1, 2]}
    b = {"x": [1, 2], "metadata": {"b": 2, "a": 1}}
    assert registry.canonical_sha256(a) == registry.canonical_sha256(b)


@pytest.mark.asyncio
async def test_commit_dsl_recovers_from_version_race(db_engine, monkeypatch):
    """Simulate a UNIQUE collision and verify commit_dsl retries with N+1.

    We force the first call to next_version() to return a stale value, so
    the INSERT collides with a concurrently-committed row. The retry loop
    should re-read next_version and succeed.
    """
    Sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    # Pre-populate version 1 to set up the collision.
    async with Sessionmaker() as s, s.begin():
        s.add(
            DSLRegistry(
                customer_id="acme",
                inspection_id="warehouse_ppe",
                version=1,
                sha256="0" * 64,
                dsl=_dsl(),
            )
        )

    real_next = registry.next_version
    calls = {"n": 0}

    async def flaky_next(session, customer_id, inspection_id):
        calls["n"] += 1
        # First call: lie and say next is 1 (already taken). Subsequent
        # calls: defer to the real implementation.
        if calls["n"] == 1:
            return 1
        return await real_next(session, customer_id, inspection_id)

    monkeypatch.setattr(registry, "next_version", flaky_next)

    async with Sessionmaker() as s, s.begin():
        entry = await registry.commit_dsl(s, _dsl())

    assert entry.version == 2
    assert calls["n"] >= 2  # at least one retry happened


@pytest.mark.asyncio
async def test_commit_dsl_gives_up_after_max_retries(db_engine, monkeypatch):
    """If next_version stays stale forever, we surface a clear RuntimeError."""
    Sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async with Sessionmaker() as s, s.begin():
        s.add(
            DSLRegistry(
                customer_id="acme",
                inspection_id="warehouse_ppe",
                version=1,
                sha256="0" * 64,
                dsl=_dsl(),
            )
        )

    async def always_stale(session, customer_id, inspection_id):
        return 1

    monkeypatch.setattr(registry, "next_version", always_stale)

    async with Sessionmaker() as s, s.begin():
        with pytest.raises(RuntimeError, match="failed to allocate next version"):
            await registry.commit_dsl(s, _dsl())
