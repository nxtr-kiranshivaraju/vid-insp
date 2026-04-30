"""Read-only API contract tests."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from shared.dsl import (
    AlertChannel,
    AlertsBlock,
    Camera,
    Deployment,
    DSL,
    OutputSchema,
    Question,
    Rule,
    RuleAction,
    RuleOn,
)

from runtime.api.routes import build_app
from runtime.config import Settings
from runtime.engine.buffer import Observation
from runtime.engine.orchestrator import build_deployment


def _dsl() -> DSL:
    return DSL(
        deployment=Deployment(id="dep_x", customer_id="c", inspection_id="i"),
        cameras=[Camera(id="cam_a", rtsp_url="rtsp://a")],
        questions=[Question(
            id="q_a", camera="cam_a", prompt="?",
            output_schema=OutputSchema(
                type="object",
                properties={"violation_present": {"type": "boolean"}, "confidence": {"type": "number"}},
                required=["violation_present", "confidence"],
            ),
        )],
        rules=[Rule(
            id="r1", on=RuleOn(camera="cam_a", question="q_a"),
            when={"violation_present": True}, sustained_for="30s", sustained_threshold=0.7,
            severity="high", cooldown="5m",
            actions=[RuleAction(type="alert", channel_ref="ch1", message="m")],
        )],
        alerts=AlertsBlock(channels=[
            AlertChannel(id="ch1", type="slack_webhook", url="https://example.test/x")
        ]),
    )


@pytest.fixture
def client(stub_vlm, fake_pool, _frozen_time):
    settings = Settings()
    deployment = build_deployment(_dsl(), settings=settings, vlm=stub_vlm, pool=fake_pool)
    deployment.health.mark_frame("cam_a")
    deployment.cost.record("cam_a", "q_a", {"prompt_tokens": 1000, "completion_tokens": 50})
    deployment.alerts.recent.appendleft({
        "rule_id": "r1", "camera_id": "cam_a", "severity": "high",
        "dispatched_at": _frozen_time.now.isoformat(),
        "channel_results": {}, "payload": {"message": "hi"},
    })
    app = build_app({
        "deployment": deployment,
        "boot_report": {"aborted": False},
        "settings": settings,
        "db_available": True,
    })
    return TestClient(app)


def test_status(client):
    r = client.get("/deployments/dep_x/status")
    assert r.status_code == 200
    body = r.json()
    assert body["deployment_id"] == "dep_x"
    assert any(c["id"] == "cam_a" for c in body["cameras"])


def test_alerts(client):
    r = client.get("/deployments/dep_x/alerts")
    assert r.status_code == 200
    assert r.json()["alerts"][0]["rule_id"] == "r1"


def test_cost(client):
    r = client.get("/deployments/dep_x/cost")
    body = r.json()
    assert "totals" in body
    assert body["per_camera_question"][0]["camera_id"] == "cam_a"


def test_health(client):
    r = client.get("/deployments/dep_x/health")
    body = r.json()
    assert "cameras" in body
    assert body["cameras"][0]["camera_id"] == "cam_a"


def test_unknown_deployment_404(client):
    r = client.get("/deployments/nope/status")
    assert r.status_code == 404


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True
