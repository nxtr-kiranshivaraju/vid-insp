"""VLM client: thin wrapper over `shared.llm_client.LLMClient`.

Two roles configured by env (`RUNTIME_VLM_PRIMARY_*`, `RUNTIME_VLM_FALLBACK_*`).
Falls back on `RateLimitError`/`ProviderError` if a fallback is configured.
Tracks coercion errors per (question_id, provider) for the health endpoint.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from collections import defaultdict
from typing import Any

from shared.llm_client import LLMClient, LLMResponse, ProviderError, RateLimitError

from runtime.vlm.coercion import CoercedResponse, coerce_and_validate

log = logging.getLogger(__name__)


class VLMClient:
    """OpenAI-compatible VLM client. Primary + optional fallback by env-configured roles."""

    def __init__(
        self,
        semaphore: asyncio.Semaphore,
        primary: LLMClient | None = None,
        fallback: LLMClient | None = None,
    ):
        self.semaphore = semaphore
        self.primary = primary
        self.fallback = fallback
        # Per (question_id, provider) coercion-error counts for /health.
        self.coercion_error_counts: dict[tuple[str, str], int] = defaultdict(int)
        self.call_counts: dict[tuple[str, str], int] = defaultdict(int)

    @classmethod
    def from_env(cls, semaphore: asyncio.Semaphore | None = None) -> "VLMClient":
        if semaphore is None:
            semaphore = asyncio.Semaphore(int(os.environ.get("VLM_CONCURRENCY", "10")))
        primary = LLMClient.from_env("RUNTIME_VLM_PRIMARY")
        fallback = (
            LLMClient.from_env("RUNTIME_VLM_FALLBACK")
            if os.environ.get("RUNTIME_VLM_FALLBACK_BASE_URL")
            else None
        )
        return cls(semaphore=semaphore, primary=primary, fallback=fallback)

    async def ask(
        self,
        prompt: str,
        jpeg_bytes: bytes,
        output_schema: dict[str, Any],
        *,
        question_id: str = "unknown",
    ) -> CoercedResponse:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64,"
                            + base64.b64encode(jpeg_bytes).decode("ascii")
                        },
                    },
                ],
            }
        ]
        response_format = {"type": "json_schema", "json_schema": output_schema}

        async with self.semaphore:
            provider = "primary"
            try:
                raw = await self.primary.chat(messages=messages, response_format=response_format)
            except (RateLimitError, ProviderError) as e:
                if self.fallback is None:
                    log.warning("vlm_call_failed_no_fallback", extra={"error": str(e)})
                    raise
                log.info("vlm_failover_to_fallback", extra={"error": str(e)})
                provider = "fallback"
                raw = await self.fallback.chat(
                    messages=messages, response_format=response_format
                )

        self.call_counts[(question_id, provider)] += 1
        content = raw.choices[0].message_content
        coerced = coerce_and_validate(content, output_schema)
        coerced.usage = raw.usage
        coerced.provider = provider
        coerced.model = raw.model
        if coerced.coercion_errors:
            self.coercion_error_counts[(question_id, provider)] += 1
        return coerced

    async def test_call(self, jpeg_bytes: bytes) -> bool:
        """Used by G3: cheapest possible call to verify the endpoint answers."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Reply with the single word: ok"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64,"
                            + base64.b64encode(jpeg_bytes).decode("ascii")
                        },
                    },
                ],
            }
        ]
        async with self.semaphore:
            await self.primary.chat(messages=messages)
        return True
