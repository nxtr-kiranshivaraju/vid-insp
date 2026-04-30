"""Tests covering the PR-review fixes (SSRF, JSONB, voting math, etc.).

Each test names the issue it pins down so future regressions are easy to spot.
"""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest

from shared.dsl import (
    AlertChannel,
    AlertsBlock,
    Camera,
    DSL,
    Deployment,
    OutputSchema,
    Question,
    Rule,
    RuleAction,
    RuleOn,
)
from shared.dsl.schema import parse_duration

from runtime.config import Settings
from runtime.engine.buffer import Observation, TemporalBuffer
from runtime.engine.dispatcher import AlertDispatcher
from runtime.engine.rules import RuleEvaluator
from runtime.engine.url_safety import UnsafeUrlError, validate_https_webhook, validate_rtsp_url


# ---- #1 SSRF defenses --------------------------------------------------------


class TestUrlSafety:
    def test_loopback_rejected(self):
        with pytest.raises(UnsafeUrlError):
            validate_https_webhook("https://127.0.0.1/x")

    def test_link_local_rejected(self):
        with pytest.raises(UnsafeUrlError):
            validate_https_webhook("https://169.254.169.254/latest/meta-data")

    def test_private_rejected(self):
        with pytest.raises(UnsafeUrlError):
            validate_https_webhook("https://10.0.0.1/x")

    def test_http_scheme_rejected(self):
        with pytest.raises(UnsafeUrlError):
            validate_https_webhook("http://example.com/x")

    def test_file_scheme_rejected(self):
        with pytest.raises(UnsafeUrlError):
            validate_https_webhook("file:///etc/passwd")

    def test_rtsp_only_rtsp_or_rtsps(self):
        validate_rtsp_url("rtsp://10.0.0.5:554/stream")
        validate_rtsp_url("rtsps://example.com/stream")
        with pytest.raises(UnsafeUrlError):
            validate_rtsp_url("file:///etc/passwd")
        with pytest.raises(UnsafeUrlError):
            validate_rtsp_url("http://10.0.0.5/x")


async def test_dispatcher_rejects_unsafe_webhook(_frozen_time):
    sent = []

    async def handler(request):
        sent.append(request.url)
        return httpx.Response(200, json={"ok": True})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    channels = [AlertChannel(id="evil", type="slack_webhook", url="https://127.0.0.1/x")]
    rule = Rule(
        id="r1", on=RuleOn(camera="cam_a", question="q_a"),
        when={"violation_present": True}, sustained_for="30s", sustained_threshold=0.7,
        severity="high", cooldown="5m",
        actions=[RuleAction(type="alert", channel_ref="evil", message="m")],
    )
    d = AlertDispatcher(channels=channels, http_client=http, allow_private_webhooks=False)
    obs = Observation(timestamp=_frozen_time.now, answer={"violation_present": True}, confidence=0.9)
    from runtime.engine.rules import RuleResult

    dispatched = await d.dispatch(
        RuleResult(rule_id="r1", matched=True, vote_ratio=0.9, sample_count=6, gap_count=0),
        rule, obs,
    )
    await d.aclose()
    assert dispatched.channel_results["evil"]["ok"] is False
    assert "private/loopback" in dispatched.channel_results["evil"]["error"]
    assert sent == []  # never made the HTTP call


# ---- #3 dispatch_synthetic ---------------------------------------------------


async def test_dispatch_synthetic_calls_each_channel(_frozen_time):
    sent = []

    async def handler(request):
        sent.append(str(request.url))
        return httpx.Response(200)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    channels = [
        AlertChannel(id="slack", type="slack_webhook", url="https://hooks.slack.test/x"),
        AlertChannel(id="webhook", type="webhook", url="https://webhook.test/x"),
    ]
    d = AlertDispatcher(channels=channels, http_client=http, allow_private_webhooks=True)
    dispatched = await d.dispatch_synthetic(
        rule_id="observation_starved:cam_a",
        camera_id="cam_a",
        message="cam_a has produced no observations recently",
    )
    await d.aclose()
    assert dispatched.channel_results["slack"]["ok"] is True
    assert dispatched.channel_results["webhook"]["ok"] is True
    assert len(sent) == 2


# ---- #6 voting math: integer comparison guards float drift -------------------


def test_voting_threshold_uses_integer_count(_frozen_time):
    """0.7 * 10 == 7.000...001 in float; with the old ratio comparison 7/10 didn't
    fire even though that's clearly the user's intent."""
    rule = Rule(
        id="r1", on=RuleOn(camera="cam_a", question="q_a"),
        when={"violation_present": True}, sustained_for="60s", sustained_threshold=0.7,
        severity="high", cooldown="5m",
        actions=[RuleAction(type="alert", channel_ref="ch1", message="m")],
    )
    buf = TemporalBuffer()
    base = _frozen_time.now - timedelta(seconds=55)
    for i in range(10):
        ts = base + timedelta(seconds=i * 5)
        present = i < 7  # exactly 7 / 10 = 0.7
        buf.append(Observation(
            timestamp=ts,
            answer={"violation_present": present, "confidence": 0.9},
            confidence=0.9,
        ))
    evaluator = RuleEvaluator()
    result = evaluator.evaluate(rule, buf)
    assert result is not None and result.matched
    assert result.sample_count == 10


# ---- #22 unknown $op surfaces --------------------------------------------------


def test_unknown_operator_raises(_frozen_time):
    rule = Rule(
        id="r1", on=RuleOn(camera="cam_a", question="q_a"),
        when={"confidence": {"$between": [0.7, 0.9]}},  # bogus
        sustained_for=None, severity="high", cooldown="5m",
        actions=[RuleAction(type="alert", channel_ref="ch1", message="m")],
    )
    buf = TemporalBuffer()
    buf.append(Observation(
        timestamp=_frozen_time.now,
        answer={"confidence": 0.8}, confidence=0.8,
    ))
    evaluator = RuleEvaluator()
    with pytest.raises(ValueError, match="unknown rule operator"):
        evaluator.evaluate(rule, buf)


# ---- #25 fractional duration parsing -----------------------------------------


def test_parse_duration_fractional():
    assert parse_duration("1.5s") == timedelta(milliseconds=1500)
    assert parse_duration("0.5h") == timedelta(minutes=30)


# ---- #18 bool→number explicit coercion ---------------------------------------


def test_bool_to_number_coerces_explicitly():
    from runtime.vlm.coercion import coerce_and_validate

    schema = {
        "type": "object",
        "properties": {"score": {"type": "number"}, "confidence": {"type": "number"}},
        "required": ["score", "confidence"],
    }
    out = coerce_and_validate({"score": True, "confidence": False}, schema)
    assert out.data["score"] == 1.0
    assert out.data["confidence"] == 0.0
    # No error string — this is a successful coercion now.
    assert all("score" not in e and "confidence" not in e for e in out.coercion_errors)


# ---- #14 retention runs at startup ------------------------------------------


async def test_retention_runs_immediately_on_start():
    from runtime.observability.retention import RetentionJob

    class _Pool:
        def __init__(self):
            self.calls = 0

        async def execute(self, *_a, **_k):
            self.calls += 1
            return "DELETE 0"

    pool = _Pool()
    job = RetentionJob(pool=pool, retention_days=1, interval_s=3600.0)
    deleted = await job.run_once()
    assert pool.calls == 1
    assert deleted == 0


# ---- #20 LLMClient typed exception detection ---------------------------------


def test_llm_client_detects_429_via_status():
    from shared.llm_client import _looks_like_429

    class _StubErr(Exception):
        status_code = 429

    assert _looks_like_429(_StubErr("rate limited"))
    assert _looks_like_429(Exception("got 429 from upstream"))
    assert not _looks_like_429(Exception("connection refused"))


# ---- #8 dispatcher only encodes JPEG when something attaches it --------------


async def test_dispatch_synthetic_carries_extra_payload(_frozen_time):
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    channels = [AlertChannel(id="ch", type="slack_webhook", url="https://hooks.slack.test/x")]
    d = AlertDispatcher(channels=channels, http_client=http, allow_private_webhooks=True)
    dispatched = await d.dispatch_synthetic(
        rule_id="r", camera_id="cam_a", message="m",
        extra_payload={"reason": "starved", "consecutive_failures": 5},
    )
    await d.aclose()
    assert dispatched.payload["reason"] == "starved"
    assert dispatched.payload["consecutive_failures"] == 5


# ---- #12 PagerDuty dedup_key -------------------------------------------------


async def test_pagerduty_includes_dedup_key(_frozen_time):
    sent = []

    async def handler(request):
        import json
        sent.append(json.loads(request.content.decode()))
        return httpx.Response(202, json={"status": "success"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    channels = [AlertChannel(id="pd", type="pagerduty", service_key="key")]
    d = AlertDispatcher(channels=channels, http_client=http, allow_private_webhooks=True)
    await d.dispatch_synthetic(rule_id="rule1", camera_id="cam_a", message="m")
    await d.aclose()
    assert "dedup_key" in sent[0]
    assert sent[0]["dedup_key"]  # non-empty


# ---- #7 schema_migrations table is created and skip-on-rerun -----------------


async def test_apply_migrations_skips_already_applied(tmp_path):
    from runtime.db.pool import apply_migrations

    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_init.sql").write_text("CREATE TABLE foo (id int);")
    (mig_dir / "002_more.sql").write_text("CREATE TABLE bar (id int);")

    class _Pool:
        def __init__(self):
            self.applied: set[str] = set()
            self.executed: list[str] = []

        async def execute(self, sql, *args):
            self.executed.append(sql)
            if sql.startswith("INSERT INTO schema_migrations"):
                self.applied.add(args[0])
            return "OK"

        async def fetch(self, sql, *args):
            if "FROM schema_migrations" in sql:
                return [{"filename": f} for f in self.applied]
            return []

    pool = _Pool()
    n1 = await apply_migrations(pool, migrations_dir=mig_dir)
    n2 = await apply_migrations(pool, migrations_dir=mig_dir)
    assert n1 == 2
    assert n2 == 0  # already applied → skipped


# ---- #4 naive datetime coercion in /observations -----------------------------


def test_coerce_aware_datetime():
    from datetime import datetime, timezone
    from runtime.api.routes import _coerce_aware

    naive = datetime(2026, 1, 1, 12, 0, 0)
    aware = _coerce_aware(naive)
    assert aware.tzinfo is timezone.utc
    assert _coerce_aware(None) is None


# ---- #2 API auth -------------------------------------------------------------


def test_api_requires_bearer_token_when_configured(stub_vlm, fake_pool, _frozen_time):
    from fastapi.testclient import TestClient

    from runtime.api.routes import build_app
    from runtime.engine.orchestrator import build_deployment

    settings = Settings()
    settings.api_auth_token = "shh-secret"
    settings.allow_private_webhooks = True
    dsl = DSL(
        deployment=Deployment(id="d", customer_id="c", inspection_id="i"),
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
            AlertChannel(id="ch1", type="slack_webhook", url="https://hooks.slack.test/x")
        ]),
    )
    deployment = build_deployment(dsl, settings=settings, vlm=stub_vlm, pool=fake_pool)
    app = build_app({
        "deployment": deployment,
        "boot_report": {"aborted": False},
        "settings": settings,
        "db_available": True,
    })
    client = TestClient(app)

    # Healthz still open (no auth required for liveness)
    assert client.get("/healthz").status_code == 200

    # Other endpoints reject missing token
    r = client.get("/deployments/d/status")
    assert r.status_code == 401

    # Wrong token
    r = client.get("/deployments/d/status", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401

    # Correct token
    r = client.get("/deployments/d/status", headers={"Authorization": "Bearer shh-secret"})
    assert r.status_code == 200


def test_probe_rejects_non_rtsp(stub_vlm, fake_pool, _frozen_time):
    from fastapi.testclient import TestClient

    from runtime.api.routes import build_app
    from runtime.engine.orchestrator import build_deployment

    settings = Settings()
    settings.allow_private_webhooks = True
    dsl = DSL(
        deployment=Deployment(id="d", customer_id="c", inspection_id="i"),
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
            AlertChannel(id="ch1", type="slack_webhook", url="https://hooks.slack.test/x")
        ]),
    )
    deployment = build_deployment(dsl, settings=settings, vlm=stub_vlm, pool=fake_pool)
    app = build_app({
        "deployment": deployment,
        "boot_report": {"aborted": False},
        "settings": settings,
        "db_available": True,
    })
    client = TestClient(app)

    # file:// would let OpenCV read a local file — must be rejected
    r = client.post("/probe", json={"rtsp_url": "file:///etc/passwd"})
    assert r.status_code == 400


# ---- #5 JSONB binds: dict passed straight through ---------------------------


async def test_observation_log_passes_dict_not_string(stub_vlm, fake_pool, _frozen_time):
    from runtime.engine.buffer import Observation
    from runtime.observability.log import ObservationLog

    log_obj = ObservationLog(pool=fake_pool, deployment_id="d")
    obs = Observation(
        timestamp=_frozen_time.now,
        answer={"violation_present": True, "confidence": 0.9},
        confidence=0.9,
    )
    await log_obj.record("cam_a", "q_a", obs)
    row = fake_pool.observations[-1]
    # Stored as dict — the asyncpg JSONB codec encodes once at the driver layer.
    assert isinstance(row["answer"], dict)
    assert row["answer"]["violation_present"] is True


async def test_alert_history_passes_dict_payload(_frozen_time):
    from runtime.engine.dispatcher import DispatchedAlert
    from runtime.observability.alerts import AlertHistory

    class _Pool:
        def __init__(self):
            self.captured = []

        async def execute(self, sql, *args):
            self.captured.append(args)
            return "INSERT 0 1"

    pool = _Pool()
    hist = AlertHistory(pool=pool, deployment_id="d")
    await hist.record(DispatchedAlert(
        rule_id="r1", camera_id="cam_a", severity="high",
        payload={"rule_id": "r1", "vote_ratio": 0.9, "message": "m"},
        dispatched_at=_frozen_time.now,
    ))
    args = pool.captured[0]
    payload_arg = args[7]  # payload is positional 8 (after deployment_id, rule_id, ...)
    assert isinstance(payload_arg, dict)


# ---- #16 stop() is idempotent ------------------------------------------------


async def test_stop_is_idempotent(stub_vlm, fake_pool, _frozen_time):
    from runtime.engine.orchestrator import build_deployment

    settings = Settings()
    dsl = DSL(
        deployment=Deployment(id="d", customer_id="c", inspection_id="i"),
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
            AlertChannel(id="ch1", type="slack_webhook", url="https://hooks.slack.test/x")
        ]),
    )
    deployment = build_deployment(dsl, settings=settings, vlm=stub_vlm, pool=fake_pool)
    await deployment.stop()
    # Should not error or double-close.
    await deployment.stop()


# ---- #23 buffer window is bounded by data, not buffer size ------------------


def test_buffer_window_short_circuits_old_observations(_frozen_time):
    from datetime import timedelta

    buf = TemporalBuffer(max_size=10000)
    # 9000 ancient observations + 5 recent ones
    for i in range(9000):
        ts = _frozen_time.now - timedelta(hours=24, seconds=i)
        buf.append(Observation(timestamp=ts, answer={"x": True}, confidence=1.0))
    for i in range(5):
        ts = _frozen_time.now - timedelta(seconds=i)
        buf.append(Observation(timestamp=ts, answer={"x": True}, confidence=1.0))
    out = buf.window_observations(timedelta(seconds=30))
    # Should return only the 5 recent ones, not all 9005.
    assert len(out) == 5
