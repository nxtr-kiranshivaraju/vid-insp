"""OpenAI Chat Completions–compatible LLM client. One instance per role.

Roles defined in the platform (per ARCH-2.2):
- COMPILER_INTENT       — Stage A (intent extraction)
- COMPILER_PROMPTGEN    — Stage C (question generation)
- RUNTIME_VLM_PRIMARY   — primary VLM (Issue 3)
- RUNTIME_VLM_FALLBACK  — fallback VLM (Issue 3)

Each role is configured via env: <ROLE>_BASE_URL, <ROLE>_API_KEY, <ROLE>_MODEL.
Any provider exposing the OpenAI Chat Completions spec works (OpenAI, Anthropic via
LiteLLM/OpenRouter, Gemini via OpenAI-compat, vLLM, Ollama, Azure OpenAI).
"""

from __future__ import annotations

import os
from typing import Any

from openai import AsyncOpenAI


class LLMClient:
    """OpenAI Chat Completions-compatible client. One instance per role."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url
        self.model = model
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
        **kw: Any,
    ) -> Any:
        """Thin pass-through to chat.completions.create with the role's model bound."""
        return await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format=response_format,
            **kw,
        )

    @classmethod
    def from_env(cls, role: str) -> "LLMClient":
        """Factory: reads <ROLE>_BASE_URL, <ROLE>_API_KEY, <ROLE>_MODEL from env."""
        try:
            return cls(
                base_url=os.environ[f"{role}_BASE_URL"],
                api_key=os.environ[f"{role}_API_KEY"],
                model=os.environ[f"{role}_MODEL"],
            )
        except KeyError as missing:
            raise RuntimeError(
                f"LLMClient.from_env({role!r}): missing env var {missing.args[0]}"
            ) from missing


__all__ = ["LLMClient"]
