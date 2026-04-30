"""DSL validators G1 (schema) and G2 (cross-references and channel-shape rules).

G1 — schema-level validation. Pydantic catches most of this; the function returns
a list of error strings rather than raising, so callers can aggregate.

G2 — cross-reference validation: every Rule.on.{camera,question} resolves, every
RuleAction.channel_ref resolves, every Question.camera resolves, durations parse.
"""

from __future__ import annotations

from typing import Any

from shared.dsl.schema import DSL, parse_duration


class ValidationError(Exception):
    pass


def validate_g1(raw: dict[str, Any]) -> list[str]:
    """Validate that `raw` (a dict, e.g. from `dsl.model_dump()`) parses against the schema."""
    errors: list[str] = []
    try:
        DSL.model_validate(raw)
    except Exception as e:  # pydantic.ValidationError — kept generic to avoid a hard dep here
        errors.append(f"G1: {e}")
    return errors


def validate_g2(dsl: DSL) -> list[str]:
    errors: list[str] = []
    cam_ids = {c.id for c in dsl.cameras}
    q_ids = {q.id for q in dsl.questions}
    channel_ids = {c.id for c in dsl.alerts.channels}

    for q in dsl.questions:
        if q.camera not in cam_ids:
            errors.append(f"G2: question {q.id!r} references unknown camera {q.camera!r}")

    for r in dsl.rules:
        if r.on.camera not in cam_ids:
            errors.append(f"G2: rule {r.id!r} references unknown camera {r.on.camera!r}")
        if r.on.question not in q_ids:
            errors.append(f"G2: rule {r.id!r} references unknown question {r.on.question!r}")
        if r.sustained_for is not None:
            try:
                parse_duration(r.sustained_for)
            except ValueError as e:
                errors.append(f"G2: rule {r.id!r} has bad sustained_for: {e}")
        try:
            parse_duration(r.cooldown)
        except ValueError as e:
            errors.append(f"G2: rule {r.id!r} has bad cooldown: {e}")
        for a in r.actions:
            if a.channel_ref not in channel_ids:
                errors.append(
                    f"G2: rule {r.id!r} action references unknown channel {a.channel_ref!r}"
                )

    for c in dsl.cameras:
        try:
            parse_duration(c.sample_every)
        except ValueError as e:
            errors.append(f"G2: camera {c.id!r} has bad sample_every: {e}")

    for ch in dsl.alerts.channels:
        if ch.type == "slack_webhook" and not ch.url:
            errors.append(f"G2: slack_webhook channel {ch.id!r} requires url")
        if ch.type == "webhook" and not ch.url:
            errors.append(f"G2: webhook channel {ch.id!r} requires url")
        if ch.type == "pagerduty" and not ch.service_key:
            errors.append(f"G2: pagerduty channel {ch.id!r} requires service_key")

    return errors
