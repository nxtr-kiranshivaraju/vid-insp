"""Alert history sink + in-memory recent buffer for the API."""

from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime
from typing import Any

from runtime.engine.dispatcher import DispatchedAlert

log = logging.getLogger(__name__)


class AlertHistory:
    def __init__(self, pool: Any | None, deployment_id: str, recent_size: int = 200):
        self.pool = pool
        self.deployment_id = deployment_id
        self.recent: deque[dict[str, Any]] = deque(maxlen=recent_size)

    async def record(self, alert: DispatchedAlert) -> None:
        record = {
            "rule_id": alert.rule_id,
            "camera_id": alert.camera_id,
            "severity": alert.severity,
            "dispatched_at": alert.dispatched_at.isoformat(),
            "channel_results": alert.channel_results,
            "payload": alert.payload,
        }
        self.recent.appendleft(record)
        if self.pool is None:
            return
        try:
            await self.pool.execute(
                "INSERT INTO alert_history "
                "(deployment_id, rule_id, camera_id, severity, message, "
                " violator_description, vote_ratio, payload, dispatched_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                self.deployment_id,
                alert.rule_id,
                alert.camera_id,
                alert.severity,
                str(alert.payload.get("message", "")),
                str(alert.payload.get("violator_description", "")),
                float(alert.payload.get("vote_ratio", 0.0)),
                json.dumps(alert.payload),
                alert.dispatched_at,
            )
        except Exception as e:
            log.exception("alert_history_insert_failed", extra={"error": str(e)})

    def list_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(self.recent)[:limit]
