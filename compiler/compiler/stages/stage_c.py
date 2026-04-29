"""Stage C — question generation (LLM call via shared client, role COMPILER_PROMPTGEN).

Generates one Question per approved intent. Does NOT generate the rule — that
is Stage R's deterministic job.
"""

from __future__ import annotations

import json
from typing import Any

from vlm_inspector_shared.dsl.schema import (
    Intent,
    Question,
    QuestionOutputSchema,
)
from vlm_inspector_shared.llm_client import LLMClient
from vlm_inspector_shared.prompts import load_prompt

from compiler.stages.stage_a import _content

ROLE = "COMPILER_PROMPTGEN"

# sample_every defaults by severity (per prompt-engineering rule 8)
SAMPLE_EVERY_BY_SEVERITY = {
    "medium": "5s",
    "high": "5s",
    "critical": "3s",
    "safety_critical": "2s",
}


def system_prompt() -> str:
    return load_prompt("prompt_engineering_rules")


async def generate_questions(
    intents: list[Intent],
    client: LLMClient | None = None,
) -> list[Question]:
    """Call the COMPILER_PROMPTGEN model. Returns one Question per intent."""
    client = client or LLMClient.from_env(ROLE)
    response = await client.chat(
        messages=[
            {"role": "system", "content": system_prompt()},
            {
                "role": "user",
                "content": json.dumps(
                    {"intents": [_intent_for_llm(i) for i in intents]},
                    indent=2,
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    raw = _content(response)
    return parse_questions(raw, intents)


def parse_questions(raw: str, intents: list[Intent]) -> list[Question]:
    """Parse the LLM's JSON response into a list of Question objects.

    The LLM is asked to return one question per intent in the same order. We
    pair them back up here so we can attach the original Intent (which Stage R
    needs to derive the rule).
    """
    data = json.loads(raw)
    if isinstance(data, dict) and "questions" in data:
        items = data["questions"]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError(f"question response missing array: {data!r}")
    if len(items) != len(intents):
        raise ValueError(
            f"Stage C returned {len(items)} questions for {len(intents)} intents"
        )

    out: list[Question] = []
    for intent, item in zip(intents, items, strict=True):
        out.append(_build_question(intent, item))
    return out


def _build_question(intent: Intent, item: dict[str, Any]) -> Question:
    qid = item.get("question_id") or item.get("id")
    if not qid:
        raise ValueError(f"question item missing question_id: {item!r}")

    schema_dict = item["output_schema"]
    schema = QuestionOutputSchema.model_validate(schema_dict)

    severity_default = SAMPLE_EVERY_BY_SEVERITY.get(intent.severity, "5s")
    return Question(
        id=qid,
        intent=intent,
        prompt=item["prompt"],
        output_schema=schema,
        target=item.get("target", "full_frame"),
        sample_every=item.get("sample_every", severity_default),
    )


def _intent_for_llm(i: Intent) -> dict[str, Any]:
    return {
        "check_type": i.check_type,
        "entity": i.entity,
        "location": i.location,
        "required": i.required,
        "schedule": i.schedule,
        "severity": i.severity,
        "involves_people": i.involves_people,
    }


__all__ = ["generate_questions", "parse_questions", "system_prompt", "ROLE"]
