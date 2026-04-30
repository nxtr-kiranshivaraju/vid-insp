"""Regenerate `vlm_inspector_shared/dsl/jsonschema.json` from the Pydantic models.

Run:  python shared/scripts/export_jsonschema.py
"""

from __future__ import annotations

import json
from pathlib import Path

from vlm_inspector_shared.dsl.schema import InspectionDSL


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "vlm_inspector_shared" / "dsl" / "jsonschema.json"
    out.write_text(json.dumps(InspectionDSL.model_json_schema(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
