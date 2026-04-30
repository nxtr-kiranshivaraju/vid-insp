"""End-to-end approval gating + downstream invalidation.

Drives the service layer directly (not HTTP) so the assertions are tight and
read like the spec's state machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from compiler.services import sessions as svc

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.asyncio
async def test_full_approval_lifecycle(db, patch_stages):
    text = (FIXTURES / "warehouse_ppe.txt").read_text().strip()
    s = await svc.create_session(db, [text])
    await db.commit()

    assert s.status == "intents_ready"
    assert s.intents and len(s.intents) == 3
    assert not s.intents_approved

    # Stage C must NOT have run yet.
    assert s.questions is None
    assert promptgen_calls(patch_stages) == 0

    # Approve intents → Stage C runs.
    s = await svc.approve_intents(db, s.id)
    await db.commit()
    assert s.status == "questions_ready"
    assert s.questions and len(s.questions) == 3
    assert promptgen_calls(patch_stages) == 1

    # Stage R must NOT have run yet.
    assert s.rules is None

    # Approve questions → Stage R runs (deterministic, no LLM call).
    s = await svc.approve_questions(db, s.id)
    await db.commit()
    assert s.status == "rules_ready"
    assert s.rules and len(s.rules) == 3
    # No new LLM call — Stage R is deterministic.
    assert promptgen_calls(patch_stages) == 1

    s = await svc.approve_rules(db, s.id)
    await db.commit()
    assert s.status == "ready_for_config"


@pytest.mark.asyncio
async def test_editing_intents_invalidates_downstream(db, patch_stages):
    text = (FIXTURES / "warehouse_ppe.txt").read_text().strip()
    s = await svc.create_session(db, [text])
    await db.commit()
    s = await svc.approve_intents(db, s.id)
    s = await svc.approve_questions(db, s.id)
    s = await svc.approve_rules(db, s.id)
    await db.commit()
    assert s.status == "ready_for_config"

    # Drop the third intent.
    new_intents = s.intents[:-1]
    s = await svc.update_intents(db, s.id, new_intents)
    await db.commit()
    assert s.status == "intents_modified"
    assert not s.intents_approved
    assert s.questions is None
    assert s.rules is None
    assert not s.questions_approved
    assert not s.rules_approved


@pytest.mark.asyncio
async def test_cannot_approve_questions_before_intents(db, patch_stages):
    text = (FIXTURES / "warehouse_ppe.txt").read_text().strip()
    s = await svc.create_session(db, [text])
    await db.commit()
    with pytest.raises(svc.SessionError):
        await svc.approve_questions(db, s.id)


@pytest.mark.asyncio
async def test_cannot_approve_rules_before_questions(db, patch_stages):
    text = (FIXTURES / "warehouse_ppe.txt").read_text().strip()
    s = await svc.create_session(db, [text])
    await db.commit()
    s = await svc.approve_intents(db, s.id)
    await db.commit()
    with pytest.raises(svc.SessionError):
        await svc.approve_rules(db, s.id)


@pytest.mark.asyncio
async def test_re_approving_after_modification_re_runs_only_affected(db, patch_stages):
    """If the user edits intents, re-approving must re-run Stage C (and Stage R
    after questions approve). It must not re-run Stage C if questions were the
    only thing edited.
    """
    text = (FIXTURES / "kitchen_hygiene.txt").read_text().strip()
    s = await svc.create_session(db, [text])
    await db.commit()
    s = await svc.approve_intents(db, s.id)
    s = await svc.approve_questions(db, s.id)
    s = await svc.approve_rules(db, s.id)
    await db.commit()
    initial_promptgen_calls = promptgen_calls(patch_stages)
    assert initial_promptgen_calls == 1

    # Edit a question (not intents) — Stage C should NOT re-run.
    qs = list(s.questions)
    qs[0]["prompt"] = qs[0]["prompt"] + " (edited)"
    s = await svc.update_questions(db, s.id, qs)
    await db.commit()
    assert s.status == "questions_modified"
    assert promptgen_calls(patch_stages) == initial_promptgen_calls

    # Re-approve questions → Stage R re-runs.
    s = await svc.approve_questions(db, s.id)
    await db.commit()
    assert s.status == "rules_ready"
    assert promptgen_calls(patch_stages) == initial_promptgen_calls  # still no LLM


@pytest.mark.asyncio
async def test_editing_cameras_after_validation_resets_status(db, patch_stages):
    """If cameras change after a validate, the assembled DSL is stale, so
    status must drop back to ready_for_config — otherwise it lies about state.
    """
    text = (FIXTURES / "warehouse_ppe.txt").read_text().strip()
    s = await svc.create_session(db, [text])
    s = await svc.approve_intents(db, s.id)
    s = await svc.approve_questions(db, s.id)
    s = await svc.approve_rules(db, s.id)
    await svc.update_cameras(
        db,
        s.id,
        [{"id": "cam_main", "name": "Bay", "rtsp_secret_ref": "x"}],
    )
    await svc.update_channels(db, s.id, [{"id": "default", "type": "log"}])
    metadata = {"customer_id": "a", "inspection_id": "b", "name": "n"}
    s, _, errors = await svc.validate_session(db, s.id, metadata, default_channel="default")
    await db.commit()
    assert errors == []
    assert s.status == "validated"
    assert s.dsl is not None

    s = await svc.update_cameras(
        db,
        s.id,
        [{"id": "cam_other", "name": "Other", "rtsp_secret_ref": "y"}],
    )
    await db.commit()
    assert s.status == "ready_for_config"
    assert s.dsl is None


@pytest.mark.asyncio
async def test_cannot_edit_cameras_after_commit(db, patch_stages):
    text = (FIXTURES / "warehouse_ppe.txt").read_text().strip()
    s = await svc.create_session(db, [text])
    s = await svc.approve_intents(db, s.id)
    s = await svc.approve_questions(db, s.id)
    s = await svc.approve_rules(db, s.id)
    await svc.update_cameras(
        db,
        s.id,
        [{"id": "cam_main", "name": "Bay", "rtsp_secret_ref": "x"}],
    )
    await svc.update_channels(db, s.id, [{"id": "default", "type": "log"}])
    metadata = {"customer_id": "a", "inspection_id": "b", "name": "n"}
    await svc.commit_session(db, s.id, metadata, default_channel="default")
    await db.commit()

    with pytest.raises(svc.SessionError, match="committed"):
        await svc.update_cameras(
            db,
            s.id,
            [{"id": "cam_other", "name": "Other", "rtsp_secret_ref": "y"}],
        )


def promptgen_calls(patch_stages) -> int:
    return len(patch_stages["promptgen"].calls)
