"""Stage A — intent extraction. Mocked LLM, no real calls."""

from __future__ import annotations

from pathlib import Path

import pytest

from compiler.stages import stage_a

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.asyncio
async def test_warehouse_extracts_three_intents(fake_intent_client):
    text = (FIXTURES / "warehouse_ppe.txt").read_text().strip()
    intents = await stage_a.extract_intents(text, client=fake_intent_client)
    assert len(intents) == 3
    entities = [i.entity for i in intents]
    assert any("hard hat" in e for e in entities)
    assert any("hi-vis" in e for e in entities)
    assert any("spotter" in e for e in entities)


@pytest.mark.asyncio
async def test_kitchen_extracts_four_intents(fake_intent_client):
    text = (FIXTURES / "kitchen_hygiene.txt").read_text().strip()
    intents = await stage_a.extract_intents(text, client=fake_intent_client)
    assert len(intents) == 4


@pytest.mark.asyncio
async def test_hospital_extracts_two_intents(fake_intent_client):
    text = (FIXTURES / "hospital_fall_risk.txt").read_text().strip()
    intents = await stage_a.extract_intents(text, client=fake_intent_client)
    assert len(intents) == 2


@pytest.mark.asyncio
async def test_compound_rule_split(fake_intent_client):
    """The warehouse paragraph has 'hard hats AND hi-vis vests' — must split."""
    text = (FIXTURES / "warehouse_ppe.txt").read_text().strip()
    intents = await stage_a.extract_intents(text, client=fake_intent_client)
    hard_hat = next(i for i in intents if "hard hat" in i.entity)
    hi_vis = next(i for i in intents if "hi-vis" in i.entity)
    assert hard_hat.entity != hi_vis.entity


def test_parse_intents_accepts_json_array():
    raw = '[{"check_type":"presence_required","entity":"x","required":true,"severity":"high"}]'
    intents = stage_a.parse_intents(raw)
    assert len(intents) == 1


def test_parse_intents_accepts_keyed_object():
    raw = '{"intents":[{"check_type":"state_check","entity":"x","required":true,"severity":"high"}]}'
    intents = stage_a.parse_intents(raw)
    assert len(intents) == 1


def test_parse_intents_rejects_unknown_array_key():
    """If the response wraps the array under an unrecognized key, fail loudly
    rather than silently picking an arbitrary list."""
    import pytest as _pytest

    raw = '{"some_other_key":[{"check_type":"state_check","entity":"x","required":true,"severity":"high"}]}'
    with _pytest.raises(ValueError, match="missing 'intents' array"):
        stage_a.parse_intents(raw)
