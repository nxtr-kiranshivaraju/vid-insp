"""`vlm-compile` CLI: paragraph -> validated DSL YAML on stdout.

Auto-approves all stages (non-interactive). Requires the four COMPILER_INTENT_*
and COMPILER_PROMPTGEN_* env vars to be set.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import click
import yaml
from vlm_inspector_shared.dsl.schema import (
    AlertChannel,
    AlertConfig,
    Camera,
    InspectionDSL,
    Intent,
    Metadata,
    Question,
)
from vlm_inspector_shared.dsl.validator import validate_dsl
from vlm_inspector_shared.llm_client import LLMClient

from compiler.stages import stage_a, stage_c, stage_r


async def _compile(
    paragraph: str,
    customer_id: str,
    inspection_id: str,
    name: str,
    camera_id: str,
    camera_name: str,
    channel_id: str,
) -> dict[str, Any]:
    intent_client = LLMClient.from_env(stage_a.ROLE)
    promptgen_client = LLMClient.from_env(stage_c.ROLE)

    intents: list[Intent] = await stage_a.extract_intents(paragraph, client=intent_client)
    if not intents:
        raise click.ClickException("Stage A returned no intents")

    questions: list[Question] = await stage_c.generate_questions(intents, client=promptgen_client)
    rules = stage_r.generate_rules(list(zip(intents, questions, strict=True)))

    # Bind unbound rule cameras to the single camera.
    for r in rules:
        if r.on.camera == stage_r.UNBOUND_CAMERA:
            r.on.camera = camera_id

    dsl = InspectionDSL(
        metadata=Metadata(
            customer_id=customer_id,
            inspection_id=inspection_id,
            name=name,
        ),
        cameras=[Camera(id=camera_id, name=camera_name)],
        questions=questions,
        rules=rules,
        alerts=AlertConfig(
            channels=[AlertChannel(id=channel_id, type="log")],
            default_channel=channel_id,
        ),
    )

    payload = dsl.model_dump(mode="json")
    parsed, errors = validate_dsl(payload)
    if errors:
        raise click.ClickException("validation failed:\n" + "\n".join(errors))
    assert parsed is not None
    return payload


@click.command()
@click.argument("paragraph_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--customer-id", default="default", show_default=True)
@click.option("--inspection-id", default="inspection", show_default=True)
@click.option("--name", default="Inspection", show_default=True)
@click.option("--camera-id", default="cam_main", show_default=True)
@click.option("--camera-name", default="Main camera", show_default=True)
@click.option("--channel-id", default="default", show_default=True)
def main(
    paragraph_file: Path,
    customer_id: str,
    inspection_id: str,
    name: str,
    camera_id: str,
    camera_name: str,
    channel_id: str,
) -> None:
    """Compile PARAGRAPH_FILE into validated DSL YAML on stdout."""
    paragraph = paragraph_file.read_text(encoding="utf-8")
    payload = asyncio.run(
        _compile(
            paragraph,
            customer_id=customer_id,
            inspection_id=inspection_id,
            name=name,
            camera_id=camera_id,
            camera_name=camera_name,
            channel_id=channel_id,
        )
    )
    yaml.safe_dump(payload, sys.stdout, sort_keys=False, default_flow_style=False)


if __name__ == "__main__":
    main()
