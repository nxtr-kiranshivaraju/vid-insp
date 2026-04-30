"""Full session lifecycle through the HTTP API."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.mark.asyncio
async def test_health(api_client):
    r = await api_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_full_lifecycle_warehouse(api_client):
    text = (FIXTURES / "warehouse_ppe.txt").read_text().strip()

    # Create session — runs Stage A.
    r = await api_client.post("/sessions", json={"paragraphs": [text]})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert r.json()["status"] == "intents_ready"
    assert len(r.json()["intents"]) == 3

    # Approve intents → Stage C runs.
    r = await api_client.post(f"/sessions/{sid}/intents/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "questions_ready"
    assert len(r.json()["questions"]) == 3

    # Approve questions → Stage R runs.
    r = await api_client.post(f"/sessions/{sid}/questions/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "rules_ready"
    rules = r.json()["rules"]
    assert len(rules) == 3
    for rule in rules:
        assert rule["sustained_threshold"] == 0.7  # ARCH-1

    r = await api_client.post(f"/sessions/{sid}/rules/approve")
    assert r.json()["status"] == "ready_for_config"

    cameras = [{"id": "cam_main", "name": "Loading Bay", "rtsp_secret_ref": "cam_main_rtsp"}]
    channels = [{"id": "default", "type": "log"}]
    r = await api_client.put(f"/sessions/{sid}/cameras", json={"cameras": cameras})
    assert r.status_code == 200, r.text
    r = await api_client.put(f"/sessions/{sid}/channels", json={"channels": channels})
    assert r.status_code == 200, r.text

    body = {
        "metadata": {
            "customer_id": "acme",
            "inspection_id": "warehouse_ppe",
            "name": "Warehouse PPE",
        },
        "default_channel": "default",
    }
    r = await api_client.post(f"/sessions/{sid}/commit", json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["session"]["status"] == "committed"
    reg = j["registry"]
    assert reg["version"] == 1
    assert len(reg["sha256"]) == 64
    expected = hashlib.sha256(
        json.dumps(j["session"]["dsl"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert reg["sha256"] == expected


@pytest.mark.asyncio
async def test_rules_have_arch1_threshold_default(api_client):
    text = (FIXTURES / "kitchen_hygiene.txt").read_text().strip()
    r = await api_client.post("/sessions", json={"paragraphs": [text]})
    sid = r.json()["id"]
    await api_client.post(f"/sessions/{sid}/intents/approve")
    r = await api_client.post(f"/sessions/{sid}/questions/approve")
    for rule in r.json()["rules"]:
        assert rule["sustained_threshold"] == 0.7


@pytest.mark.asyncio
async def test_validate_returns_errors_when_camera_unbound(api_client):
    """Calling /commit without binding cameras must reject."""
    text = (FIXTURES / "hospital_fall_risk.txt").read_text().strip()
    r = await api_client.post("/sessions", json={"paragraphs": [text]})
    sid = r.json()["id"]
    await api_client.post(f"/sessions/{sid}/intents/approve")
    await api_client.post(f"/sessions/{sid}/questions/approve")
    await api_client.post(f"/sessions/{sid}/rules/approve")

    body = {"metadata": {"customer_id": "h", "inspection_id": "fr", "name": "Fall Risk"}}
    r = await api_client.post(f"/sessions/{sid}/commit", json=body)
    assert r.status_code == 400
    assert "cameras" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_second_commit_increments_version(api_client):
    text = (FIXTURES / "warehouse_ppe.txt").read_text().strip()
    cameras = [{"id": "cam_main", "name": "Bay", "rtsp_secret_ref": "x"}]
    channels = [{"id": "default", "type": "log"}]
    metadata = {
        "customer_id": "acme",
        "inspection_id": "warehouse_ppe",
        "name": "Warehouse PPE",
    }
    body = {"metadata": metadata, "default_channel": "default"}

    versions = []
    for _ in range(2):
        r = await api_client.post("/sessions", json={"paragraphs": [text]})
        sid = r.json()["id"]
        await api_client.post(f"/sessions/{sid}/intents/approve")
        await api_client.post(f"/sessions/{sid}/questions/approve")
        await api_client.post(f"/sessions/{sid}/rules/approve")
        await api_client.put(f"/sessions/{sid}/cameras", json={"cameras": cameras})
        await api_client.put(f"/sessions/{sid}/channels", json={"channels": channels})
        r = await api_client.post(f"/sessions/{sid}/commit", json=body)
        assert r.status_code == 200, r.text
        versions.append(r.json()["registry"]["version"])
    assert versions == [1, 2]


@pytest.mark.asyncio
async def test_dsl_has_no_vlm_block(api_client):
    text = (FIXTURES / "warehouse_ppe.txt").read_text().strip()
    r = await api_client.post("/sessions", json={"paragraphs": [text]})
    sid = r.json()["id"]
    await api_client.post(f"/sessions/{sid}/intents/approve")
    await api_client.post(f"/sessions/{sid}/questions/approve")
    await api_client.post(f"/sessions/{sid}/rules/approve")
    await api_client.put(
        f"/sessions/{sid}/cameras",
        json={"cameras": [{"id": "cam_main", "name": "Bay"}]},
    )
    await api_client.put(
        f"/sessions/{sid}/channels", json={"channels": [{"id": "default", "type": "log"}]}
    )
    body = {
        "metadata": {"customer_id": "a", "inspection_id": "b", "name": "n"},
        "default_channel": "default",
    }
    r = await api_client.post(f"/sessions/{sid}/commit", json=body)
    assert r.status_code == 200, r.text
    dsl = r.json()["session"]["dsl"]
    assert "vlm" not in dsl
