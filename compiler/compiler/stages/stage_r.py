"""Stage R — deterministic rule generation. NO LLM call.

Given an approved (intent, question) pair, derive a Rule. Defaults are documented
in the spec; the user can edit any field in step 4 of the wizard.
"""

from __future__ import annotations

from vlm_inspector_shared.dsl.schema import (
    Action,
    Intent,
    Question,
    Rule,
    RuleCondition,
    RuleOn,
    Severity,
)

# Camera id used as a placeholder until the user binds the rule at deploy time.
UNBOUND_CAMERA = "<unbound>"
DEFAULT_CHANNEL = "default"

_SUSTAINED_FOR_BY_SEVERITY: dict[Severity, str] = {
    "medium": "30s",
    "high": "30s",
    "critical": "10s",
    "safety_critical": "5s",
}
_COOLDOWN_BY_SEVERITY: dict[Severity, str] = {
    "medium": "120s",
    "high": "120s",
    "critical": "60s",
    "safety_critical": "30s",
}


def pick_primary_field(question: Question) -> str:
    """Return the first non-confidence required field in the output schema.

    `confidence` is metadata, never the rule trigger. `violator_description` is
    a string description used for alert messages, never a trigger field. So we
    skip both and pick the next required field.
    """
    skip = {"confidence", "violator_description"}
    for name in question.output_schema.required:
        if name not in skip:
            return name
    raise ValueError(
        f"question {question.id!r} has no usable primary field "
        f"(required={question.output_schema.required})"
    )


def generate_rule(intent: Intent, question: Question) -> Rule:
    """Deterministically build a Rule from an approved (intent, question) pair.

    `intent.required` semantics:
      - True  ("must be present"): rule fires when the answer is False.
      - False ("must NOT be present"): rule fires when the answer is True.
    """
    primary_field = pick_primary_field(question)
    expected_value = False if intent.required else True

    severity: Severity = intent.severity
    sustained_for = _SUSTAINED_FOR_BY_SEVERITY[severity]
    cooldown = _COOLDOWN_BY_SEVERITY[severity]

    return Rule(
        id=f"rule_{intent.short_id()}",
        on=RuleOn(camera=UNBOUND_CAMERA, question=question.id),
        when=[
            RuleCondition(
                field=primary_field,
                operator="equals",
                value=expected_value,
            )
        ],
        sustained_for=sustained_for,
        sustained_threshold=0.7,  # ARCH-1
        cooldown=cooldown,
        severity=severity,
        actions=[
            Action(
                type="alert",
                channel_ref=DEFAULT_CHANNEL,
                message=intent.alert_message_template(),
            )
        ],
    )


def generate_rules(pairs: list[tuple[Intent, Question]]) -> list[Rule]:
    return [generate_rule(intent, q) for intent, q in pairs]


__all__ = ["generate_rule", "generate_rules", "pick_primary_field", "UNBOUND_CAMERA"]
