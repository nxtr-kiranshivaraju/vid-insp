"""ARCH-8: schema-violation coercion."""

from __future__ import annotations

import json

from runtime.vlm.coercion import coerce_and_validate


SCHEMA = {
    "type": "object",
    "properties": {
        "violation_present": {"type": "boolean"},
        "violator_description": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["violation_present", "confidence"],
}


def test_string_true_coerces_to_bool():
    raw = {"violation_present": "true", "confidence": "0.85", "violator_description": "x"}
    out = coerce_and_validate(raw, SCHEMA)
    assert out.data["violation_present"] is True
    assert out.data["confidence"] == 0.85
    assert out.coercion_errors == []


def test_string_false_coerces_to_bool():
    raw = {"violation_present": "false", "confidence": 0.1}
    out = coerce_and_validate(raw, SCHEMA)
    assert out.data["violation_present"] is False
    assert out.data["confidence"] == 0.1


def test_yes_no_strings_coerce():
    out = coerce_and_validate({"violation_present": "yes", "confidence": 0.5}, SCHEMA)
    assert out.data["violation_present"] is True
    out = coerce_and_validate({"violation_present": "NO", "confidence": 0.5}, SCHEMA)
    assert out.data["violation_present"] is False


def test_extra_fields_stripped():
    raw = {"violation_present": True, "confidence": 0.5, "bonus": "extra"}
    out = coerce_and_validate(raw, SCHEMA)
    assert "bonus" not in out.data


def test_missing_required_field_logs_error_and_uses_default():
    raw = {"confidence": 0.5}  # missing violation_present
    out = coerce_and_validate(raw, SCHEMA)
    assert "missing required field: violation_present" in out.coercion_errors
    assert out.data["violation_present"] is False  # default for boolean


def test_missing_optional_field_filled_with_none():
    raw = {"violation_present": True, "confidence": 0.5}  # no violator_description
    out = coerce_and_validate(raw, SCHEMA)
    assert out.data["violator_description"] is None


def test_missing_confidence_defaults_to_zero_and_flags():
    raw = {"violation_present": True}
    out = coerce_and_validate(raw, SCHEMA)
    assert out.data["confidence"] == 0.0
    assert any("confidence" in e for e in out.coercion_errors)


def test_top_level_json_string_is_parsed():
    raw = json.dumps({"violation_present": "true", "confidence": "0.7"})
    out = coerce_and_validate(raw, SCHEMA)
    assert out.data["violation_present"] is True
    assert out.data["confidence"] == 0.7


def test_invalid_json_string_returns_errors():
    out = coerce_and_validate("{not json", SCHEMA)
    assert any("JSON parse failed" in e for e in out.coercion_errors)


def test_unwraps_openai_response_format_envelope():
    envelope = {"name": "q", "schema": SCHEMA, "strict": False}
    out = coerce_and_validate({"violation_present": True, "confidence": 0.5}, envelope)
    assert out.data["violation_present"] is True
