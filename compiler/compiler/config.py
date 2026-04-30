"""Compiler service settings.

Note: model role env vars (COMPILER_INTENT_*, COMPILER_PROMPTGEN_*) are read by
shared/llm_client.py — not here. This module owns only the things specific to
the compiler service itself.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://compiler:compiler@localhost:5432/compiler"
    sync_database_url: str | None = None  # for one-shot migration runner; derived if None

    session_ttl_days: int = 7
    gc_interval_seconds: int = 24 * 60 * 60  # daily

    api_host: str = "0.0.0.0"
    api_port: int = 8001

    def sync_url(self) -> str:
        if self.sync_database_url:
            return self.sync_database_url
        return self.database_url.replace("+asyncpg", "")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
