"""Tests for shared/dsl/schema.py."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vlm_inspector_shared.dsl.schema import (
    InspectionDSL,
    Intent,
    Question,
    QuestionOutputSchema,
    Rule,
    RuleCondition,
    RuleOn,
    Action,
)


def test_minimal_dsl_parses(minimal_dsl_dict):
    dsl = InspectionDSL.model_validate(minimal_dsl_dict)
    assert dsl.version == "1.0"
    assert dsl.rules[0].sustained_threshold == 0.7  # ARCH-1 default


def test_no_vlm_block_in_dsl(minimal_dsl_dict):
    """The DSL must not have a top-level `vlm:` block. ARCH decision."""
    minimal_dsl_dict["vlm"] = {"provider": "openai"}
    with pytest.raises(ValidationError) as exc:
        InspectionDSL.model_validate(minimal_dsl_dict)
    assert "vlm" in str(exc.value).lower() or "extra" in str(exc.value).lower()


def test_jsonschema_export_is_valid_json(minimal_dsl_dict):
    schema = InspectionDSL.model_json_schema()
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "rules" in schema["properties"]


def test_question_output_schema_requires_confidence():
    with pytest.raises(ValidationError):
        QuestionOutputSchema(
            properties={"answer": {"type": "string"}},
            required=["answer"],
        )


def test_question_output_schema_with_confidence_ok():
    s = QuestionOutputSchema(
        properties={
            "answer": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        required=["answer", "confidence"],
    )
    assert "confidence" in s.properties


def test_rule_critical_window_capped():
    """Critical/safety_critical rules must have sustained_for <= 120s."""
    intent = Intent(
        check_type="state_check",
        entity="fire",
        required=False,
        severity="safety_critical",
    )
    q = Question(
        id="q_fire",
        intent=intent,
        prompt="Look at this image. Is there a fire?",
        output_schema=QuestionOutputSchema(
            properties={
                "fire_present": {"type": "boolean"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            required=["fire_present", "confidence"],
        ),
        sample_every="2s",
    )
    assert q.id == "q_fire"

    with pytest.raises(ValidationError) as exc:
        Rule(
            id="r1",
            on=RuleOn(camera="cam1", question="q_fire"),
            when=[RuleCondition(field="fire_present", operator="equals", value=True)],
            sustained_for="3m",  # 180s — too long for safety_critical
            cooldown="30s",
            severity="safety_critical",
            actions=[Action(type="alert", channel_ref="default", message="fire")],
        )
    assert "120s" in str(exc.value) or "sustained_for" in str(exc.value)


def test_duplicate_question_ids_rejected(minimal_dsl_dict):
    minimal_dsl_dict["questions"].append(minimal_dsl_dict["questions"][0])
    with pytest.raises(ValidationError) as exc:
        InspectionDSL.model_validate(minimal_dsl_dict)
    assert "duplicate" in str(exc.value).lower()


def test_intent_short_id_deterministic():
    a = Intent(check_type="presence_required", entity="hard hat", location="bay", required=True, severity="high")
    b = Intent(check_type="presence_required", entity="hard hat", location="bay", required=True, severity="high")
    assert a.short_id() == b.short_id()
    assert len(a.short_id()) > 0
