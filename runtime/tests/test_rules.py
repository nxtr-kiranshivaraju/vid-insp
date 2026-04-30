"""ARCH-1: sliding-window voting + ARCH-7 gap policy."""

from __future__ import annotations

from datetime import timedelta

from shared.dsl import Rule, RuleAction, RuleOn

from runtime.engine.buffer import Observation, TemporalBuffer
from runtime.engine.rules import RuleEvaluator


def _rule(threshold: float, sustained: str = "30s", allow_gaps: bool = False) -> Rule:
    return Rule(
        id="rule_test",
        on=RuleOn(camera="cam_a", question="q_a"),
        when={"violation_present": True},
        sustained_for=sustained,
        sustained_threshold=threshold,
        allow_gaps=allow_gaps,
        severity="high",
        cooldown="1m",
        actions=[RuleAction(type="alert", channel_ref="ch1", message="m")],
    )


def _fill_buffer(_frozen_time, buf: TemporalBuffer, matches: int, total: int) -> None:
    """Append `total` observations, the first `matches` of which match the rule."""
    base = _frozen_time.now - timedelta(seconds=25)
    for i in range(total):
        ts = base + timedelta(seconds=i * 4)  # well within a 30s window
        present = i < matches
        buf.append(Observation(
            timestamp=ts,
            answer={"violation_present": present, "confidence": 0.9},
            confidence=0.9,
        ))


def test_5_of_6_at_threshold_0_7_fires(_frozen_time):
    buf = TemporalBuffer()
    _fill_buffer(_frozen_time, buf, matches=5, total=6)
    evaluator = RuleEvaluator()
    result = evaluator.evaluate(_rule(0.7), buf)
    assert result is not None and result.matched
    assert abs(result.vote_ratio - (5 / 6)) < 1e-6
    assert result.sample_count == 6


def test_5_of_6_at_threshold_0_9_does_not_fire(_frozen_time):
    buf = TemporalBuffer()
    _fill_buffer(_frozen_time, buf, matches=5, total=6)
    evaluator = RuleEvaluator()
    assert evaluator.evaluate(_rule(0.9), buf) is None


def test_gaps_with_allow_gaps_false_block_firing(_frozen_time):
    buf = TemporalBuffer()
    _fill_buffer(_frozen_time, buf, matches=5, total=6)
    # Inject 2 gaps
    buf.append_gap()
    buf.append_gap()
    evaluator = RuleEvaluator()
    assert evaluator.evaluate(_rule(0.7, allow_gaps=False), buf) is None


def test_gaps_with_allow_gaps_true_allow_firing(_frozen_time):
    buf = TemporalBuffer()
    _fill_buffer(_frozen_time, buf, matches=5, total=6)
    buf.append_gap()
    evaluator = RuleEvaluator()
    result = evaluator.evaluate(_rule(0.7, allow_gaps=True), buf)
    assert result is not None and result.matched


def test_cooldown_blocks_second_firing(_frozen_time):
    buf = TemporalBuffer()
    _fill_buffer(_frozen_time, buf, matches=5, total=6)
    evaluator = RuleEvaluator()
    r1 = evaluator.evaluate(_rule(0.7), buf)
    r2 = evaluator.evaluate(_rule(0.7), buf)
    assert r1 is not None and r1.matched
    assert r2 is None


def test_instant_rule_fires_on_latest(_frozen_time):
    rule = Rule(
        id="instant",
        on=RuleOn(camera="cam_a", question="q_a"),
        when={"violation_present": True},
        sustained_for=None,
        severity="high",
        cooldown="5m",
        actions=[RuleAction(type="alert", channel_ref="ch1", message="m")],
    )
    buf = TemporalBuffer()
    buf.append(Observation(timestamp=_frozen_time.now, answer={"violation_present": True}, confidence=0.9))
    evaluator = RuleEvaluator()
    result = evaluator.evaluate(rule, buf)
    assert result is not None and result.matched and result.sample_count == 1


def test_comparison_operators_in_when(_frozen_time):
    rule = Rule(
        id="conf_gate",
        on=RuleOn(camera="cam_a", question="q_a"),
        when={"violation_present": True, "confidence": {"$gte": 0.8}},
        sustained_for="30s",
        sustained_threshold=0.7,
        allow_gaps=False,
        severity="high",
        cooldown="5m",
        actions=[RuleAction(type="alert", channel_ref="ch1", message="m")],
    )
    buf = TemporalBuffer()
    base = _frozen_time.now - timedelta(seconds=25)
    for i in range(6):
        ts = base + timedelta(seconds=i * 4)
        ans = {"violation_present": True, "confidence": 0.9 if i < 5 else 0.4}
        buf.append(Observation(timestamp=ts, answer=ans, confidence=ans["confidence"]))
    evaluator = RuleEvaluator()
    result = evaluator.evaluate(rule, buf)
    # 5 of 6 still at high confidence with violation -> fires at 0.7 threshold
    assert result is not None and result.matched
