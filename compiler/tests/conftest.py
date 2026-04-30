"""Test fixtures: fake LLM client + ephemeral Postgres-backed DB."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from compiler.db.migrate import collect_migrations

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

TEST_DB_BASE = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://compiler:compiler@localhost:5432/compiler_test",
)


# ---------------------------------------------------------------------------
# Fake LLM responses keyed by paragraph fixture text.
# ---------------------------------------------------------------------------


INTENT_RESPONSES: dict[str, list[dict[str, Any]]] = {
    FIXTURES_DIR.joinpath("warehouse_ppe.txt").read_text().strip(): [
        {
            "check_type": "presence_required",
            "entity": "hard hat",
            "location": "loading bay",
            "required": True,
            "schedule": None,
            "severity": "high",
            "involves_people": True,
        },
        {
            "check_type": "presence_required",
            "entity": "hi-vis vest",
            "location": "loading bay",
            "required": True,
            "schedule": None,
            "severity": "high",
            "involves_people": True,
        },
        {
            "check_type": "presence_required",
            "entity": "spotter for forklift",
            "location": "loading bay",
            "required": True,
            "schedule": None,
            "severity": "safety_critical",
            "involves_people": True,
        },
    ],
    FIXTURES_DIR.joinpath("kitchen_hygiene.txt").read_text().strip(): [
        {
            "check_type": "activity_check",
            "entity": "hand washing after raw meat",
            "location": "kitchen",
            "required": True,
            "schedule": None,
            "severity": "high",
            "involves_people": True,
        },
        {
            "check_type": "presence_prohibited",
            "entity": "uncovered food on counter",
            "location": "kitchen",
            "required": False,
            "schedule": None,
            "severity": "medium",
            "involves_people": False,
        },
        {
            "check_type": "state_check",
            "entity": "wet floor",
            "location": "near cooking stations",
            "required": False,
            "schedule": None,
            "severity": "high",
            "involves_people": False,
        },
        {
            "check_type": "presence_required",
            "entity": "hairnet",
            "location": "kitchen",
            "required": True,
            "schedule": None,
            "severity": "medium",
            "involves_people": True,
        },
    ],
    FIXTURES_DIR.joinpath("hospital_fall_risk.txt").read_text().strip(): [
        {
            "check_type": "state_check",
            "entity": "bed rails raised for fall-risk patient",
            "location": "patient room",
            "required": True,
            "schedule": None,
            "severity": "safety_critical",
            "involves_people": True,
        },
        {
            "check_type": "presence_prohibited",
            "entity": "IV pole blocking hallway exit",
            "location": "hallway",
            "required": False,
            "schedule": None,
            "severity": "critical",
            "involves_people": False,
        },
    ],
}


def _question_for_intent(i: dict[str, Any]) -> dict[str, Any]:
    """Mirror what a well-behaved promptgen LLM would return for one intent."""
    entity_slug = (
        i["entity"]
        .lower()
        .replace("-", " ")
        .replace(" ", "_")
        .replace(",", "")[:40]
    )
    location_slug = (i.get("location") or "scene").lower().replace(" ", "_")[:30]
    qid = f"q_{entity_slug}_{location_slug}"
    primary_field = f"{entity_slug}_present"

    properties: dict[str, Any] = {
        primary_field: {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    }
    required = [primary_field, "confidence"]

    prompt = (
        f"Look at this image from {i.get('location') or 'the scene'}. "
        f"Is the condition '{i['entity']}' satisfied?"
    )
    if i.get("involves_people"):
        properties["violator_description"] = {"type": "string"}
        required.append("violator_description")
        prompt += (
            " For each person violating the rule, describe them "
            "(clothing color, position in frame, what they are doing) so a "
            "responder can identify them."
        )

    sample_every = {
        "medium": "5s",
        "high": "5s",
        "critical": "3s",
        "safety_critical": "2s",
    }[i["severity"]]
    return {
        "question_id": qid,
        "prompt": prompt,
        "output_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
        "target": "full_frame",
        "sample_every": sample_every,
    }


# ---------------------------------------------------------------------------
# Fake OpenAI-compatible response objects + clients
# ---------------------------------------------------------------------------


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class FakeIntentClient:
    """Stand-in for COMPILER_INTENT — returns canned intents per paragraph text."""

    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []

    async def chat(self, messages, response_format=None, **kw):
        self.calls.append(messages)
        user = messages[-1]["content"].strip()
        intents = INTENT_RESPONSES.get(user)
        if intents is None:
            for k, v in INTENT_RESPONSES.items():
                if user.startswith(k[:80]):
                    intents = v
                    break
        if intents is None:
            raise KeyError(
                f"FakeIntentClient: no canned response for paragraph: {user[:60]}…"
            )
        return _FakeResponse(json.dumps({"intents": intents}))


class FakePromptGenClient:
    """Stand-in for COMPILER_PROMPTGEN — returns one canned question per intent."""

    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []

    async def chat(self, messages, response_format=None, **kw):
        self.calls.append(messages)
        payload = json.loads(messages[-1]["content"])
        intents = payload["intents"]
        return _FakeResponse(
            json.dumps({"questions": [_question_for_intent(i) for i in intents]})
        )


@pytest.fixture
def fake_intent_client() -> FakeIntentClient:
    return FakeIntentClient()


@pytest.fixture
def fake_promptgen_client() -> FakePromptGenClient:
    return FakePromptGenClient()


@pytest.fixture
def llm_env(monkeypatch):
    """Set the four env vars so LLMClient.from_env() works in unit tests."""
    for role in ("COMPILER_INTENT", "COMPILER_PROMPTGEN"):
        monkeypatch.setenv(f"{role}_BASE_URL", "http://fake/v1")
        monkeypatch.setenv(f"{role}_API_KEY", "fake")
        monkeypatch.setenv(f"{role}_MODEL", "fake-model")


@pytest.fixture
def patch_stages(monkeypatch, fake_intent_client, fake_promptgen_client):
    """Patch the live stage A/C functions to use fakes (no real LLM calls)."""
    from compiler.services import sessions as svc
    from compiler.stages import stage_a, stage_c

    real_extract = stage_a.extract_intents
    real_generate = stage_c.generate_questions

    async def fake_extract(paragraph, client=None):
        return await real_extract(paragraph, client=client or fake_intent_client)

    async def fake_generate(intents, client=None):
        return await real_generate(intents, client=client or fake_promptgen_client)

    monkeypatch.setattr(svc.stage_a, "extract_intents", fake_extract)
    monkeypatch.setattr(svc.stage_c, "generate_questions", fake_generate)
    return {"intent": fake_intent_client, "promptgen": fake_promptgen_client}


# ---------------------------------------------------------------------------
# DB fixtures — each test gets a fresh schema.
# ---------------------------------------------------------------------------


@pytest.fixture
def test_db_url() -> str:
    return TEST_DB_BASE


@pytest_asyncio.fixture
async def db_engine(test_db_url) -> AsyncIterator[Any]:
    # Run DDL through psycopg2 — asyncpg refuses multi-statement scripts.
    import psycopg2

    sync_conn = psycopg2.connect(test_db_url)
    try:
        sync_conn.autocommit = True
        with sync_conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS sessions, dsl_registry, secrets CASCADE")
            for _name, sql in collect_migrations():
                cur.execute(sql)
    finally:
        sync_conn.close()

    async_url = test_db_url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(async_url, future=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine) -> AsyncIterator[AsyncSession]:
    Sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with Sessionmaker() as session:
        yield session


@pytest_asyncio.fixture
async def api_client(db_engine, patch_stages, monkeypatch):
    """ASGI httpx client wired to the test DB. Stage A/C and GC are faked.

    httpx.AsyncClient + ASGITransport runs the app in the test's event loop, so
    the asyncpg connections we create here are usable from the request handlers.
    """
    import httpx

    from compiler import gc as gc_mod
    from compiler.db import session as db_session_mod
    from compiler.main import create_app

    async def _no_gc() -> None:  # pragma: no cover
        return

    monkeypatch.setattr(gc_mod, "run_forever", _no_gc)

    Sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _get_db():
        async with Sessionmaker() as s:
            yield s

    app = create_app()
    app.dependency_overrides[db_session_mod.get_db] = _get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
