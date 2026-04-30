"""Tests for shared/dsl/validator.py."""

from __future__ import annotations

import copy

from vlm_inspector_shared.dsl.schema import InspectionDSL
from vlm_inspector_shared.dsl.validator import (
    validate_dsl,
    validate_g1,
    validate_g2,
)


def test_validate_g1_passes_clean_dsl(minimal_dsl_dict):
    assert validate_g1(minimal_dsl_dict) == []


def test_validate_g1_rejects_missing_required(minimal_dsl_dict):
    minimal_dsl_dict.pop("rules")
    errs = validate_g1(minimal_dsl_dict)
    assert any("rules" in e for e in errs)


def test_validate_g2_clean(minimal_dsl_dict):
    parsed = InspectionDSL.model_validate(minimal_dsl_dict)
    assert validate_g2(parsed) == []


def test_validate_g2_dangling_camera(minimal_dsl_dict):
    minimal_dsl_dict["rules"][0]["on"]["camera"] = "ghost_cam"
    parsed = InspectionDSL.model_validate(minimal_dsl_dict)
    errs = validate_g2(parsed)
    assert any("ghost_cam" in e for e in errs)


def test_validate_g2_dangling_question(minimal_dsl_dict):
    minimal_dsl_dict["rules"][0]["on"]["question"] = "ghost_q"
    parsed = InspectionDSL.model_validate(minimal_dsl_dict)
    errs = validate_g2(parsed)
    assert any("ghost_q" in e for e in errs)


def test_validate_g2_field_not_in_output_schema(minimal_dsl_dict):
    minimal_dsl_dict["rules"][0]["when"][0]["field"] = "no_such_field"
    parsed = InspectionDSL.model_validate(minimal_dsl_dict)
    errs = validate_g2(parsed)
    assert any("no_such_field" in e for e in errs)


def test_validate_g2_dangling_channel_ref(minimal_dsl_dict):
    minimal_dsl_dict["rules"][0]["actions"][0]["channel_ref"] = "ghost_channel"
    parsed = InspectionDSL.model_validate(minimal_dsl_dict)
    errs = validate_g2(parsed)
    assert any("ghost_channel" in e for e in errs)


def test_validate_g2_dangling_schedule(minimal_dsl_dict):
    minimal_dsl_dict["questions"][0]["sample_during"] = "ghost_schedule"
    parsed = InspectionDSL.model_validate(minimal_dsl_dict)
    errs = validate_g2(parsed)
    assert any("ghost_schedule" in e for e in errs)


def test_validate_dsl_combined_returns_parsed(minimal_dsl_dict):
    parsed, errs = validate_dsl(minimal_dsl_dict)
    assert errs == []
    assert parsed is not None
    assert parsed.metadata.customer_id == "acme"


def test_validate_dsl_combined_returns_errors(minimal_dsl_dict):
    bad = copy.deepcopy(minimal_dsl_dict)
    bad["rules"][0]["on"]["question"] = "ghost"
    parsed, errs = validate_dsl(bad)
    assert parsed is None
    assert any("ghost" in e for e in errs)
