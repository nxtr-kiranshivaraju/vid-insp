"""Pydantic v2 models defining the InspectionDSL.

This is the contract between the compiler (Issue 2) and the runtime (Issue 3).
The DSL has no `vlm:` block — VLM provider/model identity is deployment config
(env vars on the runtime), not authoring config.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Primitive types
# ---------------------------------------------------------------------------

CheckType = Literal[
    "presence_required",
    "presence_prohibited",
    "state_check",
    "count_check",
    "activity_check",
]
Severity = Literal["medium", "high", "critical", "safety_critical"]
Target = Literal["full_frame", "cropped_zone", "clip"]
Operator = Literal[
    "equals",
    "not_equals",
    "greater_than",
    "less_than",
    "in",
    "contains",
    "exists",
]
ActionType = Literal["alert", "log", "webhook"]

DURATION_RE = re.compile(r"^\d+(ms|s|m|h)$")


def _validate_duration(v: str) -> str:
    if not DURATION_RE.match(v):
        raise ValueError(f"invalid duration: {v!r} (expected e.g. '5s', '30s', '2m')")
    return v


def _duration_seconds(v: str) -> float:
    n = float(v[:-1] if not v.endswith("ms") else v[:-2])
    if v.endswith("ms"):
        return n / 1000.0
    if v.endswith("s"):
        return n
    if v.endswith("m"):
        return n * 60
    if v.endswith("h"):
        return n * 3600
    raise ValueError(v)


# ---------------------------------------------------------------------------
# Intent (Stage A output)
# ---------------------------------------------------------------------------


class Intent(BaseModel):
    """One checkable condition extracted from the user's paragraph."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    check_type: CheckType
    entity: str
    location: str | None = None
    required: bool
    schedule: str | None = None
    severity: Severity
    involves_people: bool = False
    raw_text: str | None = None

    def short_id(self) -> str:
        """Deterministic short id derived from check_type+entity+location.

        Used by Stage R to build rule ids without depending on the LLM.
        """
        if self.id:
            return self.id
        slug_src = f"{self.check_type}|{self.entity}|{self.location or ''}"
        slug = re.sub(r"[^a-z0-9]+", "_", slug_src.lower()).strip("_")
        digest = hashlib.sha256(slug_src.encode("utf-8")).hexdigest()[:6]
        return f"{slug[:40]}_{digest}"

    def alert_message_template(self) -> str:
        loc = f" in {self.location}" if self.location else ""
        verb = "violation" if self.required else "prohibited condition"
        return f"{self.entity.capitalize()} {verb}{loc}"


# ---------------------------------------------------------------------------
# Question (Stage C output)
# ---------------------------------------------------------------------------


class QuestionOutputSchema(BaseModel):
    """JSON-Schema for the VLM response. Must include `confidence`."""

    model_config = ConfigDict(extra="allow")

    type: Literal["object"] = "object"
    properties: dict[str, Any]
    required: list[str]

    @model_validator(mode="after")
    def must_have_confidence(self) -> Self:
        if "confidence" not in self.properties:
            raise ValueError("output_schema.properties must include 'confidence'")
        if "confidence" not in self.required:
            raise ValueError("output_schema.required must include 'confidence'")
        return self


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    intent: Intent
    prompt: str
    output_schema: QuestionOutputSchema
    target: Target = "full_frame"
    sample_every: str
    sample_during: str | None = None
    min_confidence: float = Field(default=0.5, ge=0, le=1)

    @field_validator("sample_every")
    @classmethod
    def _check_sample_every(cls, v: str) -> str:
        return _validate_duration(v)


# ---------------------------------------------------------------------------
# Rule (Stage R output — DETERMINISTIC)
# ---------------------------------------------------------------------------


class RuleOn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera: str
    question: str


class RuleCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    operator: Operator
    value: Any = None


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ActionType
    channel_ref: str
    message: str


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    on: RuleOn
    when: list[RuleCondition]
    sustained_for: str | None = None
    sustained_threshold: float = Field(default=0.7, ge=0, le=1)  # ARCH-1
    cooldown: str = "60s"
    severity: Severity
    actions: list[Action]

    @field_validator("sustained_for")
    @classmethod
    def _check_sustained_for(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_duration(v)

    @field_validator("cooldown")
    @classmethod
    def _check_cooldown(cls, v: str) -> str:
        return _validate_duration(v)

    @model_validator(mode="after")
    def _critical_window_cap(self) -> Self:
        if self.severity in ("critical", "safety_critical") and self.sustained_for:
            if _duration_seconds(self.sustained_for) > 120:
                raise ValueError(
                    "sustained_for must not exceed 120s for critical or safety_critical rules"
                )
        return self


# ---------------------------------------------------------------------------
# Top-level DSL
# ---------------------------------------------------------------------------


class Camera(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    location: str | None = None
    rtsp_secret_ref: str | None = None  # ARCH-4: secret id, not the URL itself


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    cron: str | None = None
    description: str | None = None


class AlertChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["slack", "email", "webhook", "log"]
    webhook_secret_ref: str | None = None  # ARCH-4


class AlertConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channels: list[AlertChannel]
    default_channel: str | None = None


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str
    inspection_id: str
    name: str
    description: str | None = None


class InspectionDSL(BaseModel):
    """Versioned, validated inspection definition."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["1.0"] = "1.0"
    metadata: Metadata
    cameras: list[Camera]
    schedules: list[Schedule] = Field(default_factory=list)
    questions: list[Question]
    rules: list[Rule]
    alerts: AlertConfig

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        for label, ids in [
            ("camera", [c.id for c in self.cameras]),
            ("schedule", [s.id for s in self.schedules]),
            ("question", [q.id for q in self.questions]),
            ("rule", [r.id for r in self.rules]),
            ("alert channel", [c.id for c in self.alerts.channels]),
        ]:
            seen: set[str] = set()
            for i in ids:
                if i in seen:
                    raise ValueError(f"duplicate {label} id: {i!r}")
                seen.add(i)
        return self


__all__ = [
    "Action",
    "AlertChannel",
    "AlertConfig",
    "Camera",
    "InspectionDSL",
    "Intent",
    "Metadata",
    "Question",
    "QuestionOutputSchema",
    "Rule",
    "RuleCondition",
    "RuleOn",
    "Schedule",
    "Severity",
    "Target",
    "CheckType",
]
