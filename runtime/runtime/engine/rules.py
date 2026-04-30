"""Rule evaluator with sliding-window voting (ARCH-1) and per-rule cooldown.

Sliding-window math (ARCH-1): with VLM accuracy 0.85 and a 30s window at 5s sampling
(6 samples), consecutive-agreement detects 0.85^6 = 38% of real violations. Voting at
0.7 threshold detects ~95% — that's the whole reason this exists.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.dsl import Rule
from shared.dsl.schema import parse_duration

from runtime.clock import utcnow
from runtime.engine.buffer import TemporalBuffer

log = logging.getLogger(__name__)

# Operators we know about. Anything else is a config error and we surface it
# instead of silently failing the match.
_KNOWN_OPS = ("$gte", "$lte", "$gt", "$lt", "$eq", "$ne")


@dataclass
class RuleResult:
    rule_id: str
    matched: bool
    vote_ratio: float
    sample_count: int
    gap_count: int


class RuleEvaluator:
    """Per-instance state. Tests and callers should construct one per deployment
    so no state leaks across tests via a class-level attribute."""

    def __init__(self) -> None:
        self._last_fired: dict[str, datetime] = {}

    def evaluate(self, rule: Rule, buffer: TemporalBuffer) -> RuleResult | None:
        if not rule.sustained_for:
            return self._evaluate_instant(rule, buffer)

        window = parse_duration(rule.sustained_for)
        observations = buffer.window_observations(window)

        real_obs = [o for o in observations if not o.is_gap]
        gap_count = len(observations) - len(real_obs)

        if not real_obs:
            return None

        # Gap policy (ARCH-7): default `allow_gaps=False` resets sustained_for.
        if gap_count > 0 and not rule.allow_gaps:
            return None

        matches = sum(1 for o in real_obs if self._conditions_match(rule.when, o.answer))
        # Compare integer counts, not floats. With 10 samples and threshold 0.7
        # the user expects "7 or more matches"; floating ratio comparison can
        # off-by-one on edge cases (e.g. 0.7 * 10 == 7.000000000000001).
        min_matches = max(1, math.ceil(rule.sustained_threshold * len(real_obs)))
        if matches >= min_matches:
            if self._cooldown_active(rule):
                return None
            self._set_cooldown(rule)
            return RuleResult(
                rule_id=rule.id,
                matched=True,
                vote_ratio=matches / len(real_obs),
                sample_count=len(real_obs),
                gap_count=gap_count,
            )
        return None

    # ---- helpers ------------------------------------------------------------

    def _evaluate_instant(self, rule: Rule, buffer: TemporalBuffer) -> RuleResult | None:
        latest = buffer.latest()
        if latest is None or latest.is_gap:
            return None
        if not self._conditions_match(rule.when, latest.answer):
            return None
        if self._cooldown_active(rule):
            return None
        self._set_cooldown(rule)
        return RuleResult(
            rule_id=rule.id,
            matched=True,
            vote_ratio=1.0,
            sample_count=1,
            gap_count=0,
        )

    @staticmethod
    def _conditions_match(when: dict[str, Any], answer: dict | None) -> bool:
        if answer is None:
            return False
        for key, expected in when.items():
            actual = answer.get(key)
            if isinstance(expected, dict):
                for op, threshold in expected.items():
                    if op not in _KNOWN_OPS:
                        # Don't silently fail-closed — surface the typo.
                        raise ValueError(
                            f"unknown rule operator {op!r} in when[{key!r}]; "
                            f"supported: {_KNOWN_OPS}"
                        )
                    if op == "$gte" and not (actual is not None and actual >= threshold):
                        return False
                    if op == "$lte" and not (actual is not None and actual <= threshold):
                        return False
                    if op == "$gt" and not (actual is not None and actual > threshold):
                        return False
                    if op == "$lt" and not (actual is not None and actual < threshold):
                        return False
                    if op == "$eq" and actual != threshold:
                        return False
                    if op == "$ne" and actual == threshold:
                        return False
            else:
                if actual != expected:
                    return False
        return True

    def _cooldown_active(self, rule: Rule) -> bool:
        last = self._last_fired.get(rule.id)
        if last is None:
            return False
        return utcnow() - last < parse_duration(rule.cooldown)

    def _set_cooldown(self, rule: Rule) -> None:
        self._last_fired[rule.id] = utcnow()
