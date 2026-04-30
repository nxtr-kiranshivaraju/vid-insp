"""Command-line interface for the runtime service."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Optional

import click

from runtime.boot import load_dsl, run_preflight
from runtime.config import Settings


@click.group()
def main() -> None:
    """vlm-runtime — DSL → VLM perception → temporal rules → alerts."""


@main.command()
@click.option("--dsl", "dsl_path", default=None, help="Path to a local DSL YAML file.")
@click.option("--customer", "customer_id", default=None, help="Customer ID (registry mode).")
@click.option("--inspection", "inspection_id", default=None, help="Inspection ID (registry mode).")
def run(dsl_path: Optional[str], customer_id: Optional[str], inspection_id: Optional[str]) -> None:
    """Run the runtime service: boot, gates, then live execution."""
    from runtime.main import serve

    rc = asyncio.run(
        serve(dsl_path=dsl_path, customer_id=customer_id, inspection_id=inspection_id)
    )
    sys.exit(rc)


@main.command()
@click.option("--dsl", "dsl_path", required=True, help="Path to a local DSL YAML file.")
@click.option("--no-vlm", is_flag=True, help="Skip G3/G7 (use only when VLM unavailable in CI).")
def preflight(dsl_path: str, no_vlm: bool) -> None:
    """Run gates only; print the report and exit."""
    settings = Settings.from_env()
    dsl = load_dsl(dsl_path)

    async def _go():
        if no_vlm:
            from runtime.gates import (
                gate_g4_cost_estimate,
                gate_g5_rtsp_reachability,
                gate_g6_notification_ping,
            )
            results = []
            results.append(await gate_g4_cost_estimate(dsl))
            results.append(await gate_g5_rtsp_reachability(dsl.cameras))
            results.append(await gate_g6_notification_ping(dsl.alerts.channels))
            return {"gates": [
                {"name": r.name, "ok": r.ok, "detail": r.detail, "message": r.message}
                for r in results
            ]}
        from runtime.vlm.client import VLMClient

        sem = asyncio.Semaphore(settings.vlm_concurrency)
        vlm = VLMClient.from_env(semaphore=sem)
        report = await run_preflight(dsl, settings=settings, vlm_client=vlm)
        return report.as_dict()

    try:
        report = asyncio.run(_go())
    except Exception as e:
        click.echo(f"PREFLIGHT FAILED: {e}", err=True)
        sys.exit(2)
    click.echo(json.dumps(report, indent=2, default=str))
    aborted = report.get("aborted", False)
    sys.exit(1 if aborted else 0)


@main.command()
@click.option("--rtsp", "rtsp_url", required=True, help="RTSP URL to probe.")
def probe(rtsp_url: str) -> None:
    """Probe an RTSP URL: open, grab one frame, report resolution + fps estimate."""
    from runtime.camera.sampler import probe_rtsp

    async def _go():
        return await probe_rtsp(rtsp_url)

    ok, detail = asyncio.run(_go())
    click.echo(json.dumps({"ok": ok, **detail}, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
