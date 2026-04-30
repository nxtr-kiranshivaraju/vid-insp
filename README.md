# vid-insp

Video inspection compiler service. Translates plain-English inspection requirements
into validated, versioned DSL documents for the runtime.

## Layout

- `shared/` — `vlm_inspector_shared` package: DSL schema, validator, LLM client,
  prompt engineering rules. Used by the compiler and (in Issue 3) the runtime.
- `compiler/` — FastAPI service that runs Stage A → C → R, validates, and commits
  to the Postgres registry. Ships the `vlm-compile` CLI.

## Quickstart

```bash
docker compose up -d           # Postgres + compiler at http://localhost:8001
```

Run tests:

```bash
cd shared && pip install -e '.[dev]' && pytest
cd ../compiler && pip install -e '.[dev]' && pytest
```

CLI:

```bash
export COMPILER_INTENT_BASE_URL=...
export COMPILER_INTENT_API_KEY=...
export COMPILER_INTENT_MODEL=claude-sonnet-4-6
export COMPILER_PROMPTGEN_BASE_URL=...
export COMPILER_PROMPTGEN_API_KEY=...
export COMPILER_PROMPTGEN_MODEL=claude-opus-4-7
vlm-compile compiler/tests/fixtures/warehouse_ppe.txt > inspection.yaml
```
