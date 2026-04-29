"""SQLAlchemy 2.0 models for the compiler's own state.

The shared `dsl_registry` and `secrets` tables are defined in
shared/dsl/migrations/001_initial.sql — this file is concerned only with the
compiler-side `sessions` table.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Integer, MetaData, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

metadata_obj = MetaData()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    metadata = metadata_obj


# ---------------------------------------------------------------------------
# Sessions: the compiler's working memory while a user shapes a DSL.
# ---------------------------------------------------------------------------


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="created")
    # States: created, intents_ready, intents_modified, questions_ready,
    #         questions_modified, rules_ready, rules_modified,
    #         ready_for_config, validated, committed
    paragraphs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)

    intents: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    intents_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    questions: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    questions_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    rules: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    rules_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    cameras: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    channels: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    dsl: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
        server_default=func.now(),
    )


# ---------------------------------------------------------------------------
# Registry: append-only versioned DSL snapshots. Schema mirrors
# shared/dsl/migrations/001_initial.sql.
# ---------------------------------------------------------------------------


class DSLRegistry(Base):
    __tablename__ = "dsl_registry"
    __table_args__ = (UniqueConstraint("customer_id", "inspection_id", "version"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    inspection_id: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    dsl: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    committed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Secrets: ARCH-4. RTSP/webhook URLs live here, NOT in the DSL.
# LLM/VLM API keys are NEVER stored here — they are env-only.
# ---------------------------------------------------------------------------


class Secret(Base):
    __tablename__ = "secrets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    secret_type: Mapped[str] = mapped_column(Text, nullable=False)  # rtsp_url | webhook_url
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, server_default=func.now()
    )
