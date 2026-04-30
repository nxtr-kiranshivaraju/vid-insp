"""Test fixtures shared by the package tests."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def minimal_dsl_dict() -> dict[str, Any]:
    """Smallest valid DSL: one camera, one question, one rule, one alert channel."""
    return {
        "version": "1.0",
        "metadata": {
            "customer_id": "acme",
            "inspection_id": "warehouse",
            "name": "Warehouse PPE",
        },
        "cameras": [{"id": "cam1", "name": "Loading Bay"}],
        "schedules": [],
        "questions": [
            {
                "id": "q_hard_hat",
                "intent": {
                    "check_type": "presence_required",
                    "entity": "hard hat",
                    "location": "loading bay",
                    "required": True,
                    "severity": "high",
                    "involves_people": True,
                },
                "prompt": "Look at this image from the loading bay. Is every person wearing a hard hat?",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "all_wearing_hard_hat": {"type": "boolean"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "violator_description": {"type": "string"},
                    },
                    "required": ["all_wearing_hard_hat", "confidence", "violator_description"],
                },
                "target": "full_frame",
                "sample_every": "5s",
            }
        ],
        "rules": [
            {
                "id": "rule_hard_hat",
                "on": {"camera": "cam1", "question": "q_hard_hat"},
                "when": [
                    {"field": "all_wearing_hard_hat", "operator": "equals", "value": False}
                ],
                "sustained_for": "30s",
                "sustained_threshold": 0.7,
                "cooldown": "120s",
                "severity": "high",
                "actions": [
                    {
                        "type": "alert",
                        "channel_ref": "default",
                        "message": "Hard hat violation in Loading Bay",
                    }
                ],
            }
        ],
        "alerts": {
            "channels": [{"id": "default", "type": "log"}],
            "default_channel": "default",
        },
    }
