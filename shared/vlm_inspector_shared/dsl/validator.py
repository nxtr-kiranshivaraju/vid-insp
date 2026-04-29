"""DSL validator: G1 (JSON-Schema structure) + G2 (semantic cross-references)."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from vlm_inspector_shared.dsl.schema import InspectionDSL


def _jsonschema_for_dsl() -> dict[str, Any]:
    """Build the JSON-Schema from Pydantic. Cached at module load."""
    return InspectionDSL.model_json_schema()


_DSL_JSONSCHEMA: dict[str, Any] | None = None


def _schema() -> dict[str, Any]:
    global _DSL_JSONSCHEMA
    if _DSL_JSONSCHEMA is None:
        _DSL_JSONSCHEMA = _jsonschema_for_dsl()
    return _DSL_JSONSCHEMA


# ---------------------------------------------------------------------------
# G1 — structural validation against the JSON-Schema
# ---------------------------------------------------------------------------


def validate_g1(dsl: dict[str, Any]) -> list[str]:
    """Structural validation. Returns a list of error messages (empty if valid)."""
    validator = Draft202012Validator(_schema())
    errors: list[str] = []
    for err in sorted(validator.iter_errors(dsl), key=lambda e: list(e.absolute_path)):
        path = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"G1[{path}]: {err.message}")
    return errors


# ---------------------------------------------------------------------------
# G2 — semantic cross-reference validation
# ---------------------------------------------------------------------------


def validate_g2(dsl: InspectionDSL) -> list[str]:
    """Semantic checks across the parsed DSL. Returns error messages."""
    errors: list[str] = []

    camera_ids = {c.id for c in dsl.cameras}
    schedule_ids = {s.id for s in dsl.schedules}
    question_ids = {q.id for q in dsl.questions}
    channel_ids = {c.id for c in dsl.alerts.channels}
    question_by_id = {q.id: q for q in dsl.questions}

    if dsl.alerts.default_channel and dsl.alerts.default_channel not in channel_ids:
        errors.append(
            f"G2[alerts.default_channel]: refers to unknown channel "
            f"{dsl.alerts.default_channel!r}"
        )

    for q in dsl.questions:
        if q.sample_during and q.sample_during not in schedule_ids:
            errors.append(
                f"G2[question:{q.id}]: sample_during={q.sample_during!r} is not a known schedule"
            )

    for r in dsl.rules:
        if r.on.camera not in camera_ids:
            errors.append(
                f"G2[rule:{r.id}]: on.camera={r.on.camera!r} is not a known camera"
            )
        if r.on.question not in question_ids:
            errors.append(
                f"G2[rule:{r.id}]: on.question={r.on.question!r} is not a known question"
            )
            # Skip `when[].field` checks if the question is missing — too noisy.
            continue

        question = question_by_id[r.on.question]
        properties = question.output_schema.properties
        for i, cond in enumerate(r.when):
            if cond.field not in properties:
                errors.append(
                    f"G2[rule:{r.id}.when[{i}]]: field={cond.field!r} is not in "
                    f"question {question.id!r} output_schema.properties"
                )

        for i, action in enumerate(r.actions):
            if action.channel_ref not in channel_ids:
                errors.append(
                    f"G2[rule:{r.id}.actions[{i}]]: channel_ref={action.channel_ref!r} "
                    f"is not a known alerts.channels[].id"
                )

    return errors


# ---------------------------------------------------------------------------
# Combined entry point
# ---------------------------------------------------------------------------


def validate_dsl(dsl: dict[str, Any]) -> tuple[InspectionDSL | None, list[str]]:
    """Run G1 then (if structurally valid) G2. Returns (parsed_dsl_or_None, errors)."""
    g1_errors = validate_g1(dsl)
    if g1_errors:
        return None, g1_errors
    try:
        parsed = InspectionDSL.model_validate(dsl)
    except ValidationError as e:
        return None, [f"G1[pydantic]: {err['loc']}: {err['msg']}" for err in e.errors()]
    g2_errors = validate_g2(parsed)
    if g2_errors:
        return None, g2_errors
    return parsed, []


__all__ = ["validate_g1", "validate_g2", "validate_dsl"]
