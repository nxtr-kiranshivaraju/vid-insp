"""Compiler-side smoke that the validator catches the things the spec calls out:
broken schemas (G1) and dangling references (G2). The shared package has the
exhaustive coverage; this exists so a compiler-only `pytest` run is meaningful.
"""

from __future__ import annotations

import copy

import pytest
from vlm_inspector_shared.dsl.validator import validate_dsl

DSL = {
    "version": "1.0",
    "metadata": {"customer_id": "c", "inspection_id": "i", "name": "n"},
    "cameras": [{"id": "cam1", "name": "Main"}],
    "schedules": [],
    "questions": [
        {
            "id": "q1",
            "intent": {
                "check_type": "presence_required",
                "entity": "x",
                "required": True,
                "severity": "medium",
            },
            "prompt": "Look at this image. Is x present?",
            "output_schema": {
                "type": "object",
                "properties": {
                    "x_present": {"type": "boolean"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["x_present", "confidence"],
            },
            "target": "full_frame",
            "sample_every": "5s",
        }
    ],
    "rules": [
        {
            "id": "r1",
            "on": {"camera": "cam1", "question": "q1"},
            "when": [{"field": "x_present", "operator": "equals", "value": False}],
            "sustained_for": "30s",
            "sustained_threshold": 0.7,
            "cooldown": "120s",
            "severity": "medium",
            "actions": [{"type": "alert", "channel_ref": "default", "message": "x"}],
        }
    ],
    "alerts": {
        "channels": [{"id": "default", "type": "log"}],
        "default_channel": "default",
    },
}


def test_clean_dsl():
    parsed, errs = validate_dsl(DSL)
    assert errs == []
    assert parsed is not None


@pytest.mark.parametrize(
    "mutation,token",
    [
        (lambda d: d["rules"][0]["on"].update({"question": "ghost"}), "ghost"),
        (lambda d: d["rules"][0]["on"].update({"camera": "ghost"}), "ghost"),
        (lambda d: d["rules"][0]["when"][0].update({"field": "no_field"}), "no_field"),
        (lambda d: d["rules"][0]["actions"][0].update({"channel_ref": "ghostc"}), "ghostc"),
    ],
)
def test_g2_dangling_refs(mutation, token):
    d = copy.deepcopy(DSL)
    mutation(d)
    parsed, errs = validate_dsl(d)
    assert parsed is None
    assert any(token in e for e in errs)


def test_g1_missing_required_field():
    d = copy.deepcopy(DSL)
    del d["rules"]
    parsed, errs = validate_dsl(d)
    assert parsed is None
    assert any("rules" in e for e in errs)


def test_g1_broken_question_schema():
    d = copy.deepcopy(DSL)
    # Drop confidence — Pydantic-level G1 should catch this.
    d["questions"][0]["output_schema"]["properties"].pop("confidence")
    d["questions"][0]["output_schema"]["required"] = ["x_present"]
    parsed, errs = validate_dsl(d)
    assert parsed is None
    assert any("confidence" in e for e in errs)
