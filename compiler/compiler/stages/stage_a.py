"""Stage A — intent extraction (LLM call via shared client, role COMPILER_INTENT)."""

from __future__ import annotations

import json
from typing import Any

from vlm_inspector_shared.dsl.schema import Intent
from vlm_inspector_shared.llm_client import LLMClient

ROLE = "COMPILER_INTENT"

SYSTEM_PROMPT = """You are an inspection-rule analyst. Given a paragraph describing workplace inspection requirements, extract a list of structured intents. Each intent represents ONE checkable condition.

For each intent, output:
- check_type: one of [presence_required, presence_prohibited, state_check, count_check, activity_check]
- entity: the object or condition being checked (e.g., "hard hat", "wet floor", "hand washing")
- location: where the check applies (e.g., "loading bay", "kitchen", "all areas"), or null if not specified
- required: boolean — true if the entity MUST be present/true, false if it must NOT be
- schedule: natural language schedule if mentioned (e.g., "during shift hours"), or null
- severity: inferred severity [medium, high, critical, safety_critical] based on safety implications
- involves_people: boolean — true if humans are subjects of the check (PPE, hand washing, falls), false otherwise

IMPORTANT: Split compound rules. "Hard hats AND hi-vis vests" → two separate intents.

Return a JSON object with key "intents" containing an array of these objects. Do not include any prose outside the JSON.
"""


async def extract_intents(paragraph: str, client: LLMClient | None = None) -> list[Intent]:
    """Call the COMPILER_INTENT model and return a list of Intent objects."""
    client = client or LLMClient.from_env(ROLE)
    response = await client.chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": paragraph},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    raw = _content(response)
    return parse_intents(raw)


def parse_intents(raw: str) -> list[Intent]:
    """Parse the LLM's JSON response into a list of Intent objects."""
    data = json.loads(raw)
    items: list[dict[str, Any]]
    if isinstance(data, dict):
        if "intents" in data:
            items = data["intents"]
        elif isinstance(next(iter(data.values()), None), list):
            # Tolerate different key names ("results", "items", etc.).
            items = next(v for v in data.values() if isinstance(v, list))
        else:
            raise ValueError(f"intent response missing array: {data!r}")
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError(f"unexpected intent response type: {type(data).__name__}")

    return [Intent.model_validate(item) for item in items]


def _content(response: Any) -> str:
    """Extract message content from an OpenAI chat completion response or fake."""
    # OpenAI SDK returns ChatCompletion with .choices[0].message.content
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if not choices:
        raise ValueError("LLM response had no choices")
    first = choices[0]
    msg = getattr(first, "message", None) or first.get("message")
    content = getattr(msg, "content", None) if msg is not None else None
    if content is None and isinstance(msg, dict):
        content = msg.get("content")
    if not isinstance(content, str):
        raise ValueError("LLM response content was not a string")
    return content


__all__ = ["extract_intents", "parse_intents", "SYSTEM_PROMPT", "ROLE"]
