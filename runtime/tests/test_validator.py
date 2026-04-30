"""DSL validators (G1 + G2)."""

from __future__ import annotations

from shared.dsl import (
    AlertChannel,
    AlertsBlock,
    Camera,
    Deployment,
    DSL,
    OutputSchema,
    Question,
    Rule,
    RuleAction,
    RuleOn,
    validate_g1,
    validate_g2,
)


def _ok_dsl() -> DSL:
    return DSL(
        deployment=Deployment(id="d", customer_id="c", inspection_id="i"),
        cameras=[Camera(id="cam", rtsp_url="rtsp://x")],
        questions=[Question(id="q", camera="cam", prompt="?", output_schema=OutputSchema(
            type="object",
            properties={"violation_present": {"type": "boolean"}, "confidence": {"type": "number"}},
            required=["violation_present", "confidence"],
        ))],
        rules=[Rule(
            id="r", on=RuleOn(camera="cam", question="q"), when={"violation_present": True},
            sustained_for="30s", sustained_threshold=0.7, severity="high", cooldown="5m",
            actions=[RuleAction(type="alert", channel_ref="ch", message="m")],
        )],
        alerts=AlertsBlock(channels=[AlertChannel(id="ch", type="slack_webhook", url="https://x")]),
    )


def test_g1_passes_for_valid_dsl():
    assert validate_g1(_ok_dsl().model_dump()) == []


def test_g1_fails_for_missing_field():
    raw = _ok_dsl().model_dump()
    del raw["cameras"]
    errors = validate_g1(raw)
    assert errors


def test_g2_unknown_camera_in_question():
    dsl = _ok_dsl()
    dsl.questions[0].camera = "nope"
    errors = validate_g2(dsl)
    assert any("unknown camera" in e for e in errors)


def test_g2_unknown_channel_in_action():
    dsl = _ok_dsl()
    dsl.rules[0].actions[0].channel_ref = "nope"
    errors = validate_g2(dsl)
    assert any("unknown channel" in e for e in errors)


def test_g2_bad_duration():
    dsl = _ok_dsl()
    dsl.rules[0].sustained_for = "not-a-duration"
    errors = validate_g2(dsl)
    assert any("sustained_for" in e for e in errors)


def test_g2_slack_requires_url():
    dsl = _ok_dsl()
    dsl.alerts.channels[0].url = None
    errors = validate_g2(dsl)
    assert any("requires url" in e for e in errors)
