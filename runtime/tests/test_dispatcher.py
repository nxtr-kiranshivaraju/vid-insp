"""Dispatcher: routes alerts to channels with a mocked httpx client."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

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

from runtime.engine.buffer import Observation
from runtime.engine.dispatcher import AlertDispatcher
from runtime.engine.rules import RuleResult


def _channels() -> list[AlertChannel]:
    return [
        AlertChannel(id="slack", type="slack_webhook", url="https://hooks.slack.test/x"),
        AlertChannel(id="webhook", type="webhook", url="https://webhook.test/x"),
        AlertChannel(id="pd", type="pagerduty", service_key="key"),
    ]


def _rule(channel_ref: str = "slack", attach: bool = True) -> Rule:
    return Rule(
        id="r1",
        on=RuleOn(camera="cam_a", question="q_a"),
        when={"violation_present": True},
        sustained_for="30s",
        sustained_threshold=0.7,
        severity="high",
        cooldown="5m",
        actions=[RuleAction(type="alert", channel_ref=channel_ref, message="hi", attach=attach)],
    )


async def test_slack_dispatch_invokes_http(_frozen_time):
    sent = []

    async def handler(request: httpx.Request) -> httpx.Response:
        sent.append({"url": str(request.url), "json": json.loads(request.content.decode() or "null")})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)

    d = AlertDispatcher(channels=_channels(), http_client=http, allow_private_webhooks=True)
    obs = Observation(timestamp=_frozen_time.now, answer={
        "violator_description": "person without hard hat", "violation_present": True,
    }, confidence=0.9)
    result = RuleResult(rule_id="r1", matched=True, vote_ratio=0.83, sample_count=6, gap_count=0)

    dispatched = await d.dispatch(result, _rule(), obs, frame_jpeg=b"\xff\xd8\xff")
    await d.aclose()

    assert dispatched.channel_results["slack"]["ok"] is True
    assert sent[0]["url"].startswith("https://hooks.slack.test/")
    assert "hard hat" in sent[0]["json"]["attachments"][0]["text"]


async def test_pagerduty_payload_shape(_frozen_time):
    sent = []

    async def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content.decode()))
        return httpx.Response(202, json={"status": "success"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    d = AlertDispatcher(channels=_channels(), http_client=http, allow_private_webhooks=True)
    obs = Observation(timestamp=_frozen_time.now, answer={"violation_present": True}, confidence=0.9)
    result = RuleResult(rule_id="r1", matched=True, vote_ratio=0.9, sample_count=6, gap_count=0)
    await d.dispatch(result, _rule(channel_ref="pd"), obs, frame_jpeg=None)
    await d.aclose()

    assert sent[0]["routing_key"] == "key"
    assert sent[0]["event_action"] == "trigger"
    assert sent[0]["payload"]["severity"] == "error"  # high → error in PD


async def test_unknown_channel_logs_and_continues(_frozen_time):
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    d = AlertDispatcher(channels=_channels(), http_client=http, allow_private_webhooks=True)
    rule = _rule(channel_ref="missing")
    obs = Observation(timestamp=_frozen_time.now, answer={"violation_present": True}, confidence=0.9)
    result = RuleResult(rule_id="r1", matched=True, vote_ratio=0.9, sample_count=6, gap_count=0)
    dispatched = await d.dispatch(result, rule, obs, frame_jpeg=None)
    await d.aclose()
    assert dispatched.channel_results["missing"]["ok"] is False


async def test_violator_description_carried_in_payload(_frozen_time):
    sent = []

    async def handler(request):
        sent.append(json.loads(request.content.decode()))
        return httpx.Response(200)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    d = AlertDispatcher(channels=_channels(), http_client=http, allow_private_webhooks=True)
    obs = Observation(
        timestamp=_frozen_time.now,
        answer={"violator_description": "person in red jacket near forklift", "violation_present": True},
        confidence=0.9,
    )
    result = RuleResult(rule_id="r1", matched=True, vote_ratio=0.83, sample_count=6, gap_count=0)
    dispatched = await d.dispatch(result, _rule(), obs, frame_jpeg=b"\xff")
    await d.aclose()
    assert dispatched.payload["violator_description"] == "person in red jacket near forklift"
