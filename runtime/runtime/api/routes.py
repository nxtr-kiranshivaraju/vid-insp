"""Read-only HTTP API for the runtime.

Endpoints (matching the contract in Issue 1):
  GET  /deployments/{id}/status
  GET  /deployments/{id}/alerts
  GET  /deployments/{id}/cost
  GET  /deployments/{id}/health
  GET  /deployments/{id}/observations  (paginated, filterable)
  POST /probe                          (used by the UI to validate camera URLs)
  GET  /healthz                        (liveness)

All routes other than /healthz require `Authorization: Bearer <API_AUTH_TOKEN>`
when the runtime was started with a non-empty token.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from runtime.camera.sampler import probe_rtsp
from runtime.engine.url_safety import UnsafeUrlError, validate_rtsp_url

log = logging.getLogger(__name__)


class ProbeRequest(BaseModel):
    rtsp_url: str


def _coerce_aware(dt: datetime | None) -> datetime | None:
    """FastAPI parses naive ISO strings as naive datetimes — coerce to UTC so
    comparisons against tz-aware DB timestamps don't blow up."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def build_app(state: dict[str, Any]) -> FastAPI:
    """Build the FastAPI app. `state` carries the running Deployment + boot report."""

    app = FastAPI(title="vlm-runtime", version="0.1.0")
    router = APIRouter()

    expected_token = (state.get("settings").api_auth_token if state.get("settings") else "") or ""

    async def require_auth(authorization: Optional[str] = Header(default=None)) -> None:
        if not expected_token:
            return  # auth disabled by config
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        provided = authorization.split(" ", 1)[1].strip()
        if not secrets.compare_digest(provided, expected_token):
            raise HTTPException(status_code=401, detail="invalid bearer token")

    def _require_deployment(deployment_id: str):
        d = state.get("deployment")
        if d is None or d.deployment_id != deployment_id:
            raise HTTPException(status_code=404, detail="deployment not found")
        return d

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        d = state.get("deployment")
        return {
            "ok": True,
            "deployment": d.deployment_id if d else None,
            "db_available": state.get("db_available", False),
        }

    @router.get("/deployments/{deployment_id}/status")
    async def status(deployment_id: str, _: None = Depends(require_auth)) -> dict[str, Any]:
        d = _require_deployment(deployment_id)
        return {
            "deployment_id": d.deployment_id,
            "running": not d._stopping,
            "cameras": [
                {"id": c.id, "failed": c.id in d.failed_cameras}
                for c in d.dsl.cameras
            ],
            "tasks": [{"name": t.get_name(), "done": t.done()} for t in d.tasks],
            "boot_report": state.get("boot_report"),
        }

    @router.get("/deployments/{deployment_id}/alerts")
    async def alerts(
        deployment_id: str,
        limit: int = 100,
        _: None = Depends(require_auth),
    ) -> dict[str, Any]:
        d = _require_deployment(deployment_id)
        return {"alerts": d.alerts.list_recent(limit=limit)}

    @router.get("/deployments/{deployment_id}/cost")
    async def cost(deployment_id: str, _: None = Depends(require_auth)) -> dict[str, Any]:
        d = _require_deployment(deployment_id)
        return {
            "totals": d.cost.totals(),
            "per_camera_question": d.cost.per_camera_question(),
        }

    @router.get("/deployments/{deployment_id}/health")
    async def health(deployment_id: str, _: None = Depends(require_auth)) -> dict[str, Any]:
        d = _require_deployment(deployment_id)
        return d.health.snapshot(vlm_client=d.vlm)

    @router.get("/deployments/{deployment_id}/observations")
    async def observations(
        deployment_id: str,
        camera_id: Optional[str] = None,
        question_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        _: None = Depends(require_auth),
    ) -> dict[str, Any]:
        d = _require_deployment(deployment_id)
        if d.obs_log is None:
            raise HTTPException(status_code=503, detail="observation log not configured")
        rows = await d.obs_log.query(
            camera_id=camera_id,
            question_id=question_id,
            since=_coerce_aware(since),
            until=_coerce_aware(until),
            limit=limit,
            offset=offset,
        )
        return {"observations": rows}

    @app.post("/probe")
    async def probe(req: ProbeRequest, _: None = Depends(require_auth)) -> dict[str, Any]:
        # Reject anything that isn't an rtsp/rtsps URL — without this OpenCV will
        # cheerfully open file://, http://, etc., which is a SSRF / local-file primitive.
        try:
            validate_rtsp_url(req.rtsp_url)
        except UnsafeUrlError as e:
            raise HTTPException(status_code=400, detail=str(e))
        ok, detail = await probe_rtsp(req.rtsp_url)
        return {"ok": ok, **detail}

    app.include_router(router)
    return app
