"""Alert dispatcher: Slack webhook, PagerDuty, generic webhook.

Cooldown dedup is handled in the rule engine (per rule). The dispatcher itself just
routes payloads. It also exposes `ping()` for G6 (notification preflight).
"""

from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from shared.dsl import AlertChannel, Rule

from runtime.clock import utcnow
from runtime.engine.buffer import Observation
from runtime.engine.rules import RuleResult
from runtime.engine.url_safety import UnsafeUrlError, validate_https_webhook

log = logging.getLogger(__name__)

PD_ENQUEUE_URL = "https://events.pagerduty.com/v2/enqueue"


@dataclass
class DispatchedAlert:
    rule_id: str
    camera_id: str
    severity: str
    payload: dict[str, Any]
    dispatched_at: Any
    channel_results: dict[str, dict[str, Any]] = field(default_factory=dict)


def _default_http_client() -> httpx.AsyncClient:
    """Defaults: no redirects (avoids redirect-to-private SSRF), bounded pool."""
    return httpx.AsyncClient(
        timeout=10.0,
        follow_redirects=False,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
    )


class AlertDispatcher:
    """Routes alerts to configured channels. Channels are looked up by id."""

    def __init__(
        self,
        channels: list[AlertChannel],
        *,
        http_client: httpx.AsyncClient | None = None,
        history_sink=None,  # callable(DispatchedAlert) -> awaitable
        allow_private_webhooks: bool = False,
    ):
        self._channels: dict[str, AlertChannel] = {c.id: c for c in channels}
        self._http = http_client or _default_http_client()
        self._history_sink = history_sink
        self._allow_private_webhooks = allow_private_webhooks

    async def aclose(self) -> None:
        await self._http.aclose()

    async def dispatch(
        self,
        rule_result: RuleResult,
        rule: Rule,
        latest_obs: Observation,
        frame_jpeg: bytes | None = None,
    ) -> DispatchedAlert:
        snapshot_b64 = base64.b64encode(frame_jpeg).decode("ascii") if frame_jpeg else None
        violator = ""
        if isinstance(latest_obs.answer, dict):
            violator = str(latest_obs.answer.get("violator_description", "") or "")

        dispatched = DispatchedAlert(
            rule_id=rule.id,
            camera_id=rule.on.camera,
            severity=rule.severity,
            dispatched_at=utcnow(),
            payload={
                "rule_id": rule.id,
                "severity": rule.severity,
                "camera_id": rule.on.camera,
                "timestamp": latest_obs.timestamp.isoformat(),
                "violator_description": violator,
                "vote_ratio": rule_result.vote_ratio,
                "sample_count": rule_result.sample_count,
                "gap_count": rule_result.gap_count,
            },
        )

        for action in rule.actions:
            if action.type != "alert":
                continue
            ch = self._channels.get(action.channel_ref)
            if ch is None:
                log.warning("dispatch_unknown_channel", extra={"channel": action.channel_ref})
                dispatched.channel_results[action.channel_ref] = {
                    "ok": False,
                    "error": "unknown channel",
                }
                continue
            payload = dict(dispatched.payload)
            payload["message"] = action.message
            if action.attach and snapshot_b64:
                payload["snapshot_b64"] = snapshot_b64
            try:
                ok, detail = await self._send(ch, payload)
            except Exception as e:
                ok, detail = False, {"error": str(e)}
            dispatched.channel_results[action.channel_ref] = {"ok": ok, **detail}

        if self._history_sink is not None:
            try:
                await self._history_sink(dispatched)
            except Exception as e:
                log.exception("alert_history_sink_failed", extra={"error": str(e)})

        return dispatched

    async def dispatch_synthetic(
        self,
        rule_id: str,
        camera_id: str,
        message: str,
        *,
        severity: str = "high",
        extra_payload: dict[str, Any] | None = None,
    ) -> DispatchedAlert:
        """Public API for system-generated alerts (e.g. observation-starved).

        Behaves like `dispatch()` but doesn't require a Rule/Observation pair, so
        callers don't need to fabricate dummy objects or reach into private methods.
        """
        ts = utcnow()
        payload: dict[str, Any] = {
            "rule_id": rule_id,
            "severity": severity,
            "camera_id": camera_id,
            "timestamp": ts.isoformat(),
            "violator_description": "",
            "vote_ratio": 0.0,
            "sample_count": 0,
            "gap_count": 0,
            "message": message,
        }
        if extra_payload:
            payload.update(extra_payload)

        dispatched = DispatchedAlert(
            rule_id=rule_id,
            camera_id=camera_id,
            severity=severity,
            dispatched_at=ts,
            payload=payload,
        )
        for ch in self._channels.values():
            try:
                ok, detail = await self._send(ch, payload)
            except Exception as e:
                ok, detail = False, {"error": str(e)}
            dispatched.channel_results[ch.id] = {"ok": ok, **detail}

        if self._history_sink is not None:
            try:
                await self._history_sink(dispatched)
            except Exception as e:
                log.exception("alert_history_sink_failed", extra={"error": str(e)})
        return dispatched

    async def ping(self, channel: AlertChannel) -> tuple[bool, dict[str, Any]]:
        """G6 preflight: send a harmless test ping."""
        payload = {
            "rule_id": "preflight",
            "severity": "info",
            "camera_id": "preflight",
            "timestamp": utcnow().isoformat(),
            "message": f"VLM Inspector preflight ping ({channel.id})",
        }
        try:
            return await self._send(channel, payload)
        except Exception as e:
            return False, {"error": str(e)}

    async def _send(
        self, channel: AlertChannel, payload: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        if channel.type == "slack_webhook":
            self._validate_webhook(channel.url)
            body = {
                "text": (
                    f"[{payload['severity'].upper()}] {payload.get('message', '')} "
                    f"({payload['camera_id']} @ {payload['timestamp']})"
                ),
                "attachments": [{"text": _summarise(payload)}],
            }
            r = await self._http.post(channel.url, json=body)
            r.raise_for_status()
            return True, {"status": r.status_code}
        if channel.type == "pagerduty":
            body = {
                "routing_key": channel.service_key,
                "event_action": "trigger",
                "dedup_key": _pd_dedup_key(payload),
                "payload": {
                    "summary": payload.get("message", "VLM Inspector alert"),
                    "severity": _pd_severity(payload.get("severity", "medium")),
                    "source": payload.get("camera_id", "unknown"),
                    "custom_details": payload,
                },
            }
            r = await self._http.post(PD_ENQUEUE_URL, json=body)
            r.raise_for_status()
            return True, {"status": r.status_code}
        if channel.type == "webhook":
            self._validate_webhook(channel.url)
            r = await self._http.post(channel.url, json=payload)
            r.raise_for_status()
            return True, {"status": r.status_code}
        return False, {"error": f"unknown channel type: {channel.type}"}

    def _validate_webhook(self, url: str | None) -> None:
        if not url:
            raise UnsafeUrlError("channel url is empty")
        validate_https_webhook(url, allow_private=self._allow_private_webhooks)


def _pd_severity(s: str) -> str:
    return {
        "medium": "warning",
        "high": "error",
        "critical": "critical",
        "safety_critical": "critical",
        "info": "info",
    }.get(s, "warning")


def _pd_dedup_key(payload: dict[str, Any]) -> str:
    """Stable key per (rule_id, camera_id) so PagerDuty collapses repeats inside cooldown."""
    seed = f"{payload.get('rule_id', '')}|{payload.get('camera_id', '')}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()


def _summarise(payload: dict[str, Any]) -> str:
    parts = [
        f"rule={payload.get('rule_id', 'unknown')}",
        f"vote_ratio={float(payload.get('vote_ratio', 0) or 0):.2f}",
        f"samples={payload.get('sample_count', 0)}",
    ]
    if payload.get("violator_description"):
        parts.append(f"violator={payload['violator_description']}")
    return " | ".join(parts)
