"""Session orchestration: drives Stage A → C → R with approval gating.

State machine:

    created ──► [Stage A] ──► intents_ready
                                  │
                          (user edits an intent)
                                  ▼
                            intents_modified
                                  │
                            (POST /intents/approve)
                                  ▼
              [Stage C runs] ──► questions_ready
                                  │
                          (user edits a question)
                                  ▼
                          questions_modified
                                  │
                          (POST /questions/approve)
                                  ▼
              [Stage R runs] ──► rules_ready
                                  │
                          (user edits a rule)
                                  ▼
                            rules_modified
                                  │
                            (POST /rules/approve)
                                  ▼
                            ready_for_config
                                  │
                          (POST /commit, after cameras+channels bound)
                                  ▼
                            validated → committed
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from vlm_inspector_shared.dsl.schema import (
    AlertChannel,
    AlertConfig,
    Camera,
    InspectionDSL,
    Intent,
    Metadata,
    Question,
    Rule,
)
from vlm_inspector_shared.dsl.validator import validate_dsl
from vlm_inspector_shared.llm_client import LLMClient

from compiler.db.models import Session
from compiler.registry import commit_dsl
from compiler.stages import stage_a, stage_c, stage_r


class SessionError(Exception):
    """Raised when a session operation can't proceed (e.g. wrong state)."""


# ---------------------------------------------------------------------------
# Create + Stage A
# ---------------------------------------------------------------------------


async def create_session(
    db: AsyncSession,
    paragraphs: list[str],
    intent_client: LLMClient | None = None,
) -> Session:
    """Create a new session and run Stage A on the input paragraphs."""
    if not paragraphs:
        raise SessionError("at least one paragraph is required")

    full_text = "\n\n".join(p.strip() for p in paragraphs if p.strip())
    intents = await stage_a.extract_intents(full_text, client=intent_client)
    intents_payload = [_intent_to_dict(i) for i in intents]

    s = Session(
        paragraphs=list(paragraphs),
        status="intents_ready",
        intents=intents_payload,
        intents_approved=False,
    )
    db.add(s)
    await db.flush()
    return s


async def get_session(db: AsyncSession, session_id: UUID) -> Session:
    s = await db.get(Session, session_id)
    if s is None:
        raise SessionError(f"session {session_id} not found")
    return s


# ---------------------------------------------------------------------------
# Edits + invalidation
# ---------------------------------------------------------------------------


async def update_intents(
    db: AsyncSession, session_id: UUID, intents: list[dict[str, Any]]
) -> Session:
    s = await get_session(db, session_id)
    # Validate: must parse as Intent list. Reject otherwise.
    [Intent.model_validate(i) for i in intents]
    s.intents = intents
    s.intents_approved = False
    s.questions = None
    s.questions_approved = False
    s.rules = None
    s.rules_approved = False
    s.dsl = None
    s.status = "intents_modified"
    await db.flush()
    return s


async def update_questions(
    db: AsyncSession, session_id: UUID, questions: list[dict[str, Any]]
) -> Session:
    s = await get_session(db, session_id)
    [Question.model_validate(q) for q in questions]
    s.questions = questions
    s.questions_approved = False
    s.rules = None
    s.rules_approved = False
    s.dsl = None
    s.status = "questions_modified"
    await db.flush()
    return s


async def update_rules(
    db: AsyncSession, session_id: UUID, rules: list[dict[str, Any]]
) -> Session:
    s = await get_session(db, session_id)
    [Rule.model_validate(r) for r in rules]
    s.rules = rules
    s.rules_approved = False
    s.dsl = None
    s.status = "rules_modified"
    await db.flush()
    return s


async def update_cameras(
    db: AsyncSession, session_id: UUID, cameras: list[dict[str, Any]]
) -> Session:
    s = await get_session(db, session_id)
    [Camera.model_validate(c) for c in cameras]
    s.cameras = cameras
    s.dsl = None
    await db.flush()
    return s


async def update_channels(
    db: AsyncSession, session_id: UUID, channels: list[dict[str, Any]]
) -> Session:
    s = await get_session(db, session_id)
    [AlertChannel.model_validate(c) for c in channels]
    s.channels = channels
    s.dsl = None
    await db.flush()
    return s


# ---------------------------------------------------------------------------
# Approvals — each one triggers the next stage if needed.
# ---------------------------------------------------------------------------


async def approve_intents(
    db: AsyncSession,
    session_id: UUID,
    promptgen_client: LLMClient | None = None,
) -> Session:
    s = await get_session(db, session_id)
    if not s.intents:
        raise SessionError("cannot approve intents: none generated yet")

    intents = [Intent.model_validate(i) for i in s.intents]
    s.intents_approved = True

    # Generate questions only if they don't already exist or were invalidated.
    if not s.questions:
        questions = await stage_c.generate_questions(intents, client=promptgen_client)
        s.questions = [_question_to_dict(q) for q in questions]
        s.questions_approved = False
        s.rules = None
        s.rules_approved = False

    s.status = "questions_ready"
    await db.flush()
    return s


async def approve_questions(db: AsyncSession, session_id: UUID) -> Session:
    s = await get_session(db, session_id)
    if not s.intents_approved:
        raise SessionError("cannot approve questions before intents are approved")
    if not s.questions:
        raise SessionError("cannot approve questions: none generated yet")

    s.questions_approved = True

    if not s.rules:
        intents = [Intent.model_validate(i) for i in s.intents]
        questions = [Question.model_validate(q) for q in s.questions]
        if len(intents) != len(questions):
            raise SessionError(
                f"intent/question count mismatch ({len(intents)} vs {len(questions)})"
            )
        rules = stage_r.generate_rules(list(zip(intents, questions, strict=True)))
        s.rules = [r.model_dump(mode="json") for r in rules]
        s.rules_approved = False

    s.status = "rules_ready"
    await db.flush()
    return s


async def approve_rules(db: AsyncSession, session_id: UUID) -> Session:
    s = await get_session(db, session_id)
    if not s.questions_approved:
        raise SessionError("cannot approve rules before questions are approved")
    if not s.rules:
        raise SessionError("cannot approve rules: none generated yet")
    s.rules_approved = True
    s.status = "ready_for_config"
    await db.flush()
    return s


# ---------------------------------------------------------------------------
# Validate + commit
# ---------------------------------------------------------------------------


async def assemble_dsl(
    s: Session,
    metadata: dict[str, Any],
    default_channel: str | None = None,
) -> dict[str, Any]:
    if not (s.intents_approved and s.questions_approved and s.rules_approved):
        raise SessionError("all three stages must be approved before assembly")
    if not s.cameras:
        raise SessionError("cameras must be configured before commit (ARCH-4)")
    if not s.channels:
        raise SessionError("alert channels must be configured before commit")

    questions = [Question.model_validate(q) for q in (s.questions or [])]
    rules = [Rule.model_validate(r) for r in (s.rules or [])]

    # Bind unbound rule cameras to the first camera if there's only one. With
    # multiple cameras the user must edit rule.on.camera explicitly through
    # update_rules; we don't try to guess.
    cameras = [Camera.model_validate(c) for c in s.cameras]
    if len(cameras) == 1:
        sole = cameras[0].id
        for r in rules:
            if r.on.camera == stage_r.UNBOUND_CAMERA:
                r.on.camera = sole

    channels = [AlertChannel.model_validate(c) for c in s.channels]
    chosen_default = default_channel or (channels[0].id if channels else None)

    dsl = InspectionDSL(
        metadata=Metadata.model_validate(metadata),
        cameras=cameras,
        questions=questions,
        rules=rules,
        alerts=AlertConfig(channels=channels, default_channel=chosen_default),
    )
    return dsl.model_dump(mode="json")


async def validate_session(
    db: AsyncSession,
    session_id: UUID,
    metadata: dict[str, Any],
    default_channel: str | None = None,
) -> tuple[Session, dict[str, Any], list[str]]:
    s = await get_session(db, session_id)
    dsl = await assemble_dsl(s, metadata, default_channel=default_channel)
    parsed, errors = validate_dsl(dsl)
    if errors:
        return s, dsl, errors
    s.dsl = dsl
    s.status = "validated"
    await db.flush()
    assert parsed is not None
    return s, dsl, []


async def commit_session(
    db: AsyncSession,
    session_id: UUID,
    metadata: dict[str, Any],
    default_channel: str | None = None,
) -> tuple[Session, dict[str, Any]]:
    s, dsl, errors = await validate_session(
        db, session_id, metadata, default_channel=default_channel
    )
    if errors:
        raise SessionError(f"validation failed: {errors}")

    entry = await commit_dsl(db, dsl)
    s.dsl = dsl
    s.status = "committed"
    await db.flush()
    return s, {
        "registry_id": str(entry.id),
        "version": entry.version,
        "sha256": entry.sha256,
        "customer_id": entry.customer_id,
        "inspection_id": entry.inspection_id,
    }


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


async def list_sessions(db: AsyncSession, limit: int = 50) -> list[Session]:
    stmt = select(Session).order_by(Session.updated_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# (de)serialization helpers
# ---------------------------------------------------------------------------


def _intent_to_dict(i: Intent) -> dict[str, Any]:
    return i.model_dump(mode="json")


def _question_to_dict(q: Question) -> dict[str, Any]:
    return q.model_dump(mode="json")


__all__ = [
    "SessionError",
    "create_session",
    "get_session",
    "list_sessions",
    "update_intents",
    "update_questions",
    "update_rules",
    "update_cameras",
    "update_channels",
    "approve_intents",
    "approve_questions",
    "approve_rules",
    "validate_session",
    "commit_session",
    "assemble_dsl",
]
