"""Tests for shared/llm_client.py."""

from __future__ import annotations

import pytest

from vlm_inspector_shared.llm_client import LLMClient


def test_from_env_reads_role_vars(monkeypatch):
    monkeypatch.setenv("ROLE_X_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("ROLE_X_API_KEY", "sk-test")
    monkeypatch.setenv("ROLE_X_MODEL", "claude-sonnet-4-6")
    client = LLMClient.from_env("ROLE_X")
    assert client.model == "claude-sonnet-4-6"
    assert client.base_url == "https://example.test/v1"


def test_from_env_missing_var_raises(monkeypatch):
    monkeypatch.delenv("ROLE_Y_BASE_URL", raising=False)
    monkeypatch.delenv("ROLE_Y_API_KEY", raising=False)
    monkeypatch.delenv("ROLE_Y_MODEL", raising=False)
    with pytest.raises(RuntimeError) as exc:
        LLMClient.from_env("ROLE_Y")
    assert "ROLE_Y" in str(exc.value)


@pytest.mark.asyncio
async def test_chat_calls_through_to_openai_client(monkeypatch):
    """Verify chat() forwards model + messages to the underlying SDK call."""

    captured = {}

    class FakeCompletions:
        async def create(self, **kw):
            captured.update(kw)
            return {"ok": True}

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    client = LLMClient(base_url="x", api_key="y", model="m")
    client.client = FakeClient()

    result = await client.chat(
        messages=[{"role": "user", "content": "hi"}],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    assert result == {"ok": True}
    assert captured["model"] == "m"
    assert captured["messages"] == [{"role": "user", "content": "hi"}]
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["temperature"] == 0.0
