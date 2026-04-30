"""DSL schema (Issue 2 deliverable, stubbed here for runtime independence).

The schema is intentionally minimal — only what the runtime needs to consume.
Pydantic v2 models, `model_dump()` produces a JSON-friendly dict.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


Severity = Literal["medium", "high", "critical", "safety_critical"]
ChannelType = Literal["slack_webhook", "pagerduty", "webhook"]


_DURATION_RE = re.compile(r"^\s*(\d+)\s*(ms|s|m|h)\s*$")


def parse_duration(value: str) -> timedelta:
    """Parse a duration string like '30s', '5m', '1h' into a timedelta."""
    if isinstance(value, timedelta):
        return value
    if not isinstance(value, str):
        raise ValueError(f"duration must be a string, got {type(value).__name__}")
    m = _DURATION_RE.match(value)
    if not m:
        raise ValueError(f"invalid duration: {value!r} (expected e.g. '30s', '5m')")
    n, unit = int(m.group(1)), m.group(2)
    return {
        "ms": timedelta(milliseconds=n),
        "s": timedelta(seconds=n),
        "m": timedelta(minutes=n),
        "h": timedelta(hours=n),
    }[unit]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Deployment(_Base):
    id: str
    customer_id: str
    inspection_id: str


class Camera(_Base):
    id: str
    rtsp_url: str
    sample_every: str = "5s"  # default cadence


class OutputSchema(_Base):
    """JSON-Schema-shaped object for VLM structured output."""

    type: Literal["object"] = "object"
    properties: dict[str, dict[str, Any]]
    required: list[str] = Field(default_factory=list)


class Question(_Base):
    id: str
    camera: str
    prompt: str
    output_schema: OutputSchema


class RuleOn(_Base):
    camera: str
    question: str


class RuleAction(_Base):
    type: Literal["alert"] = "alert"
    channel_ref: str
    message: str
    attach: bool = False


class Rule(_Base):
    id: str
    on: RuleOn
    when: dict[str, Any]
    sustained_for: str | None = None
    sustained_threshold: float = 0.7
    allow_gaps: bool = False
    severity: Severity = "medium"
    cooldown: str = "5m"
    actions: list[RuleAction]

    @field_validator("sustained_threshold")
    @classmethod
    def _threshold_in_range(cls, v: float) -> float:
        if not (0.0 < v <= 1.0):
            raise ValueError("sustained_threshold must be in (0, 1]")
        return v


class AlertChannel(_Base):
    id: str
    type: ChannelType
    # Channel-specific fields — kept loose. Validator (G2) enforces the right ones per type.
    url: str | None = None
    service_key: str | None = None
    cooldown: str = "5m"


class AlertsBlock(_Base):
    channels: list[AlertChannel]


class DSL(_Base):
    version: int = 1
    deployment: Deployment
    cameras: list[Camera]
    questions: list[Question]
    rules: list[Rule]
    alerts: AlertsBlock


def load_dsl_file(path: str | Path) -> DSL:
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return DSL.model_validate(raw)
