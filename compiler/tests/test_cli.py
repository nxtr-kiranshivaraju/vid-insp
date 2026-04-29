"""`vlm-compile` CLI smoke test."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner
from vlm_inspector_shared.dsl.validator import validate_dsl

from compiler import cli as cli_mod
from compiler.stages import stage_a, stage_c

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_cli_warehouse_produces_valid_yaml(monkeypatch, fake_intent_client, fake_promptgen_client, llm_env):
    """`vlm-compile warehouse_ppe.txt` produces valid YAML that passes G1+G2."""
    # Patch LLMClient.from_env to return our fakes.
    def _from_env(role):
        if role == stage_a.ROLE:
            return fake_intent_client
        if role == stage_c.ROLE:
            return fake_promptgen_client
        raise KeyError(role)

    monkeypatch.setattr(cli_mod.LLMClient, "from_env", classmethod(lambda cls, role: _from_env(role)))

    runner = CliRunner()
    result = runner.invoke(cli_mod.main, [str(FIXTURES / "warehouse_ppe.txt")])
    assert result.exit_code == 0, result.output
    parsed = yaml.safe_load(result.output)
    assert parsed["version"] == "1.0"
    assert "vlm" not in parsed  # acceptance criterion: no vlm: block

    # Round-trip validation.
    dsl, errs = validate_dsl(parsed)
    assert errs == [], errs
    assert dsl is not None
