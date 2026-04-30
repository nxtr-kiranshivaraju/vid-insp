"""asyncio entrypoint: boot DSL, start orchestration, run FastAPI."""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

import uvicorn

from runtime.api.routes import build_app
from runtime.boot import load_dsl, run_preflight
from runtime.config import Settings
from runtime.db.pool import apply_migrations, create_pool
from runtime.engine.orchestrator import build_deployment, start_deployment
from runtime.vlm.client import VLMClient

log = logging.getLogger(__name__)


async def serve(
    *,
    dsl_path: str | None,
    customer_id: str | None,
    inspection_id: str | None,
    settings: Settings | None = None,
) -> int:
    settings = settings or Settings.from_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    dsl = load_dsl(dsl_path, customer_id=customer_id, inspection_id=inspection_id)

    semaphore = asyncio.Semaphore(settings.vlm_concurrency)
    vlm = VLMClient.from_env(semaphore=semaphore)

    boot_report = await run_preflight(dsl, settings=settings, vlm_client=vlm)
    log.info("boot_completed", extra={"report": boot_report.as_dict()})

    pool = None
    try:
        pool = await create_pool(
            settings.database_url,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
        )
        await apply_migrations(pool)
    except Exception as e:
        log.warning("db_unavailable", extra={"error": str(e)})

    deployment = build_deployment(
        dsl,
        settings=settings,
        vlm=vlm,
        pool=pool,
        failed_cameras=boot_report.failed_cameras,
    )
    await start_deployment(deployment, settings)

    state: dict[str, Any] = {
        "deployment": deployment,
        "boot_report": boot_report.as_dict(),
        "settings": settings,
    }
    app = build_app(state)

    config = uvicorn.Config(
        app, host=settings.api_host, port=settings.api_port, log_level="info", access_log=False
    )
    server = uvicorn.Server(config)

    stop_event = asyncio.Event()

    def _on_signal(*_):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            # Windows / non-main-thread fallback
            signal.signal(sig, lambda *_: stop_event.set())

    api_task = asyncio.create_task(server.serve(), name="api")

    try:
        await stop_event.wait()
    finally:
        log.info("shutdown_initiated")
        server.should_exit = True
        await deployment.stop()
        try:
            await asyncio.wait_for(api_task, timeout=10)
        except asyncio.TimeoutError:
            api_task.cancel()
        if pool is not None:
            await pool.close()

    return 0
