"""Read-only HTTP API for the runtime.

Endpoints (matching the contract in Issue 1):
  GET  /deployments/{id}/status
  GET  /deployments/{id}/alerts
  GET  /deployments/{id}/cost
  GET  /deployments/{id}/health
  GET  /deployments/{id}/observations  (paginated, filterable)
  POST /probe                          (used by the UI to validate camera URLs)
  GET  /healthz                        (liveness)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel

from runtime.camera.sampler import probe_rtsp


class ProbeRequest(BaseModel):
    rtsp_url: str


def build_app(state: dict[str, Any]) -> FastAPI:
    """Build the FastAPI app. `state` carries the running Deployment + boot report."""

    app = FastAPI(title="vlm-runtime", version="0.1.0")
    router = APIRouter()

    def _require_deployment(deployment_id: str):
        d = state.get("deployment")
        if d is None or d.deployment_id != deployment_id:
            raise HTTPException(status_code=404, detail="deployment not found")
        return d

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"ok": True, "deployment": (state.get("deployment").deployment_id
                                            if state.get("deployment") else None)}

    @router.get("/deployments/{deployment_id}/status")
    async def status(deployment_id: str) -> dict[str, Any]:
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
    async def alerts(deployment_id: str, limit: int = 100) -> dict[str, Any]:
        d = _require_deployment(deployment_id)
        return {"alerts": d.alerts.list_recent(limit=limit)}

    @router.get("/deployments/{deployment_id}/cost")
    async def cost(deployment_id: str) -> dict[str, Any]:
        d = _require_deployment(deployment_id)
        return {
            "totals": d.cost.totals(),
            "per_camera_question": d.cost.per_camera_question(),
        }

    @router.get("/deployments/{deployment_id}/health")
    async def health(deployment_id: str) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        d = _require_deployment(deployment_id)
        if d.obs_log is None:
            raise HTTPException(status_code=503, detail="observation log not configured")
        rows = await d.obs_log.query(
            camera_id=camera_id,
            question_id=question_id,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )
        return {"observations": rows}

    @app.post("/probe")
    async def probe(req: ProbeRequest) -> dict[str, Any]:
        ok, detail = await probe_rtsp(req.rtsp_url)
        return {"ok": ok, **detail}

    app.include_router(router)
    return app
