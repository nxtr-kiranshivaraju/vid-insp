"""Centralised UTC clock so tests can monkeypatch a single function."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
