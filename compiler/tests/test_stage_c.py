"""Stage C — question generation. Mocked LLM, no real calls.

Verifies prompt-engineering rules: confidence required, ARCH-3 violator
description for people-related intents.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from compiler.stages import stage_a, stage_c

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.asyncio
async def test_every_question_requires_confidence(
    fake_intent_client, fake_promptgen_client
):
    text = (FIXTURES / "kitchen_hygiene.txt").read_text().strip()
    intents = await stage_a.extract_intents(text, client=fake_intent_client)
    questions = await stage_c.generate_questions(intents, client=fake_promptgen_client)
    for q in questions:
        assert "confidence" in q.output_schema.properties
        assert "confidence" in q.output_schema.required


@pytest.mark.asyncio
async def test_people_intents_get_violator_description_arch3(
    fake_intent_client, fake_promptgen_client
):
    text = (FIXTURES / "warehouse_ppe.txt").read_text().strip()
    intents = await stage_a.extract_intents(text, client=fake_intent_client)
    questions = await stage_c.generate_questions(intents, client=fake_promptgen_client)
    for intent, q in zip(intents, questions, strict=True):
        if intent.involves_people:
            assert "violator_description" in q.output_schema.properties, (
                f"ARCH-3: question {q.id} for people-related intent must include "
                "violator_description"
            )
            assert "describe them" in q.prompt.lower() or "describe " in q.prompt.lower()


@pytest.mark.asyncio
async def test_non_people_intent_skips_violator_description(
    fake_intent_client, fake_promptgen_client
):
    text = (FIXTURES / "kitchen_hygiene.txt").read_text().strip()
    intents = await stage_a.extract_intents(text, client=fake_intent_client)
    questions = await stage_c.generate_questions(intents, client=fake_promptgen_client)
    pairs = list(zip(intents, questions, strict=True))
    # 'wet floor' has no violator
    floor_pair = next(p for p in pairs if "wet floor" in p[0].entity)
    assert "violator_description" not in floor_pair[1].output_schema.properties


@pytest.mark.asyncio
async def test_sample_every_severity_defaults(
    fake_intent_client, fake_promptgen_client
):
    text = (FIXTURES / "hospital_fall_risk.txt").read_text().strip()
    intents = await stage_a.extract_intents(text, client=fake_intent_client)
    questions = await stage_c.generate_questions(intents, client=fake_promptgen_client)
    pairs = dict(zip([i.severity for i in intents], questions, strict=True))
    # safety_critical -> 2s
    assert pairs["safety_critical"].sample_every == "2s"
    # critical -> 3s
    assert pairs["critical"].sample_every == "3s"


def test_system_prompt_contains_required_rules():
    sp = stage_c.system_prompt()
    assert "confidence" in sp
    assert "violator_description" in sp
    assert "ARCH-3" in sp
    assert "ARCH-1" in sp
