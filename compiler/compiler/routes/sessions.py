"""Session HTTP API.

Endpoints:
    POST   /sessions                            create + run Stage A
    GET    /sessions                            list
    GET    /sessions/{id}                       fetch
    PUT    /sessions/{id}/intents               edit intents (invalidates downstream)
    POST   /sessions/{id}/intents/approve       approve + run Stage C
    PUT    /sessions/{id}/questions             edit questions (invalidates rules)
    POST   /sessions/{id}/questions/approve     approve + run Stage R (deterministic)
    PUT    /sessions/{id}/rules                 edit rules
    POST   /sessions/{id}/rules/approve         approve rules
    PUT    /sessions/{id}/cameras               bind cameras (ARCH-4)
    PUT    /sessions/{id}/channels              bind alert channels (ARCH-4)
    POST   /sessions/{id}/validate              dry-run G1 + G2 against assembled DSL
    POST   /sessions/{id}/commit                validate + commit to registry

TODO(auth): These endpoints are currently unauthenticated. The compiler is
deployed behind a private ingress today, but before any external exposure we
need (a) per-customer auth (e.g. signed JWT or mTLS) and (b) a customer-id
guard on every session lookup so a token scoped to customer A cannot read or
mutate customer B's sessions.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from compiler.db.models import Session as SessionRow
from compiler.db.session import get_db
from compiler.services import sessions as svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    paragraphs: list[str] = Field(min_length=1)


class IntentsRequest(BaseModel):
    intents: list[dict[str, Any]]


class QuestionsRequest(BaseModel):
    questions: list[dict[str, Any]]


class RulesRequest(BaseModel):
    rules: list[dict[str, Any]]


class CamerasRequest(BaseModel):
    cameras: list[dict[str, Any]]


class ChannelsRequest(BaseModel):
    channels: list[dict[str, Any]]


class CommitRequest(BaseModel):
    metadata: dict[str, Any]
    default_channel: str | None = None


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _to_dict(s: SessionRow) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "status": s.status,
        "paragraphs": s.paragraphs,
        "intents": s.intents,
        "intents_approved": s.intents_approved,
        "questions": s.questions,
        "questions_approved": s.questions_approved,
        "rules": s.rules,
        "rules_approved": s.rules_approved,
        "cameras": s.cameras,
        "channels": s.channels,
        "dsl": s.dsl,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _err(e: svc.SessionError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/sessions", status_code=201)
async def create_session(
    body: CreateSessionRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        s = await svc.create_session(db, body.paragraphs)
    except svc.SessionError as e:
        raise _err(e) from e
    await db.commit()
    return _to_dict(s)


@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    rows = await svc.list_sessions(db)
    return [_to_dict(r) for r in rows]


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    try:
        s = await svc.get_session(db, session_id)
    except svc.SessionError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _to_dict(s)


@router.put("/sessions/{session_id}/intents")
async def put_intents(
    session_id: UUID, body: IntentsRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        s = await svc.update_intents(db, session_id, body.intents)
    except svc.SessionError as e:
        raise _err(e) from e
    await db.commit()
    return _to_dict(s)


@router.post("/sessions/{session_id}/intents/approve")
async def approve_intents(
    session_id: UUID, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        s = await svc.approve_intents(db, session_id)
    except svc.SessionError as e:
        raise _err(e) from e
    await db.commit()
    return _to_dict(s)


@router.put("/sessions/{session_id}/questions")
async def put_questions(
    session_id: UUID, body: QuestionsRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        s = await svc.update_questions(db, session_id, body.questions)
    except svc.SessionError as e:
        raise _err(e) from e
    await db.commit()
    return _to_dict(s)


@router.post("/sessions/{session_id}/questions/approve")
async def approve_questions(
    session_id: UUID, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        s = await svc.approve_questions(db, session_id)
    except svc.SessionError as e:
        raise _err(e) from e
    await db.commit()
    return _to_dict(s)


@router.put("/sessions/{session_id}/rules")
async def put_rules(
    session_id: UUID, body: RulesRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        s = await svc.update_rules(db, session_id, body.rules)
    except svc.SessionError as e:
        raise _err(e) from e
    await db.commit()
    return _to_dict(s)


@router.post("/sessions/{session_id}/rules/approve")
async def approve_rules(
    session_id: UUID, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        s = await svc.approve_rules(db, session_id)
    except svc.SessionError as e:
        raise _err(e) from e
    await db.commit()
    return _to_dict(s)


@router.put("/sessions/{session_id}/cameras")
async def put_cameras(
    session_id: UUID, body: CamerasRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        s = await svc.update_cameras(db, session_id, body.cameras)
    except svc.SessionError as e:
        raise _err(e) from e
    await db.commit()
    return _to_dict(s)


@router.put("/sessions/{session_id}/channels")
async def put_channels(
    session_id: UUID, body: ChannelsRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        s = await svc.update_channels(db, session_id, body.channels)
    except svc.SessionError as e:
        raise _err(e) from e
    await db.commit()
    return _to_dict(s)


@router.post("/sessions/{session_id}/validate")
async def validate(
    session_id: UUID, body: CommitRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        s, dsl, errors = await svc.validate_session(
            db, session_id, body.metadata, default_channel=body.default_channel
        )
    except svc.SessionError as e:
        raise _err(e) from e
    await db.commit()
    return {"session": _to_dict(s), "dsl": dsl, "errors": errors}


@router.post("/sessions/{session_id}/commit")
async def commit(
    session_id: UUID, body: CommitRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        s, registry = await svc.commit_session(
            db, session_id, body.metadata, default_channel=body.default_channel
        )
    except svc.SessionError as e:
        raise _err(e) from e
    await db.commit()
    return {"session": _to_dict(s), "registry": registry}
