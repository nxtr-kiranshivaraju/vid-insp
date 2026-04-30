"""Stage R — deterministic rule generation. NO LLM mock; the function takes
plain (Intent, Question) arguments and is fully deterministic.
"""

from __future__ import annotations

from vlm_inspector_shared.dsl.schema import (
    Intent,
    Question,
    QuestionOutputSchema,
)

from compiler.stages import stage_r


def _question(*, qid: str, primary: str, severity: str, intent: Intent) -> Question:
    return Question(
        id=qid,
        intent=intent,
        prompt="Look at this image. Is X true?",
        output_schema=QuestionOutputSchema(
            properties={
                primary: {"type": "boolean"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "violator_description": {"type": "string"},
            },
            required=[primary, "confidence", "violator_description"],
        ),
        sample_every={
            "medium": "5s",
            "high": "5s",
            "critical": "3s",
            "safety_critical": "2s",
        }[severity],
    )


def test_required_intent_fires_when_field_is_false():
    intent = Intent(
        check_type="presence_required",
        entity="hard hat",
        location="bay",
        required=True,
        severity="high",
        involves_people=True,
    )
    q = _question(qid="q1", primary="all_wearing_hard_hat", severity="high", intent=intent)
    rule = stage_r.generate_rule(intent, q)
    assert rule.when[0].field == "all_wearing_hard_hat"
    assert rule.when[0].value is False
    assert rule.severity == "high"
    assert rule.sustained_for == "30s"
    assert rule.cooldown == "120s"
    assert rule.sustained_threshold == 0.7  # ARCH-1


def test_prohibited_intent_fires_when_field_is_true():
    intent = Intent(
        check_type="presence_prohibited",
        entity="wet floor",
        required=False,
        severity="critical",
    )
    q = _question(qid="q2", primary="floor_is_wet", severity="critical", intent=intent)
    rule = stage_r.generate_rule(intent, q)
    assert rule.when[0].value is True
    assert rule.sustained_for == "10s"
    assert rule.cooldown == "60s"


def test_rule_id_deterministic_byte_identical():
    """Acceptance criterion: byte-identical Rule output across runs."""
    intent = Intent(
        check_type="state_check",
        entity="bed rails raised",
        location="patient room",
        required=True,
        severity="safety_critical",
        involves_people=True,
    )
    q = _question(
        qid="q_bed_rails",
        primary="bed_rails_raised",
        severity="safety_critical",
        intent=intent,
    )
    a = stage_r.generate_rule(intent, q)
    b = stage_r.generate_rule(intent, q)
    assert a.model_dump_json() == b.model_dump_json()


def test_pick_primary_field_skips_confidence_and_violator_description():
    intent = Intent(check_type="state_check", entity="x", required=True, severity="medium")
    q = Question(
        id="q",
        intent=intent,
        prompt="Look at the scene. Is X true?",
        output_schema=QuestionOutputSchema(
            properties={
                "x_present": {"type": "boolean"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "violator_description": {"type": "string"},
            },
            required=["x_present", "confidence", "violator_description"],
        ),
        sample_every="5s",
    )
    assert stage_r.pick_primary_field(q) == "x_present"
