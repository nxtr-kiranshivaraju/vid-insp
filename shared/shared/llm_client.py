"""OpenAI-compatible async LLM/VLM client.

Wraps the `openai` SDK's AsyncOpenAI. Configured per-role from environment variables
so the runtime can have multiple roles (PRIMARY, FALLBACK) without provider-specific code.

ENV per role (where ROLE is e.g. ``RUNTIME_VLM_PRIMARY``):
    {ROLE}_BASE_URL   — OpenAI-compatible base URL (required)
    {ROLE}_API_KEY    — API key (required)
    {ROLE}_MODEL      — model name (required)
    {ROLE}_TIMEOUT    — request timeout, seconds (optional, default 60)

Errors are surfaced as our own exception types so callers don't depend on openai internals.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


class LLMClientError(Exception):
    pass


class RateLimitError(LLMClientError):
    """Raised when the upstream returns a 429 / quota error."""


class ProviderError(LLMClientError):
    """Raised when the upstream returns a 5xx or otherwise refuses to answer."""


@dataclass
class LLMResponseChoice:
    message_content: str

    @property
    def message(self) -> "LLMResponseChoice":  # for openai-style attribute access
        return self


@dataclass
class LLMResponse:
    choices: list[LLMResponseChoice]
    raw: Any = None
    usage: dict[str, int] | None = None  # {prompt_tokens, completion_tokens, total_tokens}
    model: str | None = None


class LLMClient:
    """Thin async wrapper over an OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        client: Any | None = None,  # injectable for tests
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = client  # lazy-initialised below

    @classmethod
    def from_env(cls, prefix: str) -> "LLMClient":
        base_url = os.environ.get(f"{prefix}_BASE_URL")
        api_key = os.environ.get(f"{prefix}_API_KEY")
        model = os.environ.get(f"{prefix}_MODEL")
        timeout = float(os.environ.get(f"{prefix}_TIMEOUT", "60"))
        missing = [
            name
            for name, val in [
                (f"{prefix}_BASE_URL", base_url),
                (f"{prefix}_API_KEY", api_key),
                (f"{prefix}_MODEL", model),
            ]
            if not val
        ]
        if missing:
            raise LLMClientError(f"missing required env vars: {', '.join(missing)}")
        return cls(base_url=base_url, api_key=api_key, model=model, timeout=timeout)

    def _ensure_client(self):
        if self._client is None:
            # Lazy import so the module loads even when openai isn't installed in tests
            # that mock everything out.
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        return self._client

    async def chat(
        self,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | None = None,
        **extra: Any,
    ) -> LLMResponse:
        client = self._ensure_client()
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
        if response_format is not None:
            kwargs["response_format"] = response_format
        kwargs.update(extra)
        try:
            raw = await client.chat.completions.create(**kwargs)
        except Exception as e:  # normalise
            etype = type(e).__name__
            if "RateLimit" in etype or "429" in str(e):
                raise RateLimitError(str(e)) from e
            raise ProviderError(f"{etype}: {e}") from e
        # Normalise the response so callers don't depend on openai's object shape.
        choices = [
            LLMResponseChoice(message_content=(c.message.content or ""))
            for c in raw.choices
        ]
        usage = None
        if getattr(raw, "usage", None) is not None:
            u = raw.usage
            usage = {
                "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
                "total_tokens": getattr(u, "total_tokens", 0) or 0,
            }
        return LLMResponse(
            choices=choices,
            raw=raw,
            usage=usage,
            model=getattr(raw, "model", self.model),
        )
