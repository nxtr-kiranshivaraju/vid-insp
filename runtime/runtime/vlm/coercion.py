"""Schema-violation coercion (ARCH-8).

The VLM may return strings where booleans/numbers are expected, extra fields, or
miss optional fields. Coerce what we can; flag what we can't.

Rules:
  1. "true"/"false"/"yes"/"no" strings → bool
  2. Numeric strings → number (int/float)
  3. Extra fields → stripped
  4. Missing optional fields → filled with None
  5. Missing required fields → default for the type, plus an error string
  6. confidence missing → set to 0.0 and flag
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class CoercedResponse:
    data: dict[str, Any]
    coercion_errors: list[str] = field(default_factory=list)
    raw: Any = None


_DEFAULTS: dict[str, Any] = {
    "boolean": False,
    "string": "",
    "number": 0.0,
    "integer": 0,
    "array": [],
    "object": {},
    "null": None,
}


def _default_for_type(field_schema: dict[str, Any]) -> Any:
    t = field_schema.get("type", "string")
    if isinstance(t, list):
        # JSON Schema allows ["string", "null"] etc — pick the first non-null.
        for cand in t:
            if cand != "null":
                t = cand
                break
        else:
            t = "null"
    return _DEFAULTS.get(t, None)


def _coerce_bool(value: Any) -> tuple[bool | None, bool]:
    if isinstance(value, bool):
        return value, True
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "yes", "y", "1"):
            return True, True
        if v in ("false", "no", "n", "0"):
            return False, True
    if isinstance(value, (int, float)):
        return bool(value), True
    return None, False


def _coerce_number(value: Any, integer: bool) -> tuple[Any, bool]:
    if isinstance(value, bool):
        return None, False  # bools are ints in Python — explicit reject
    if isinstance(value, (int, float)):
        return (int(value), True) if integer else (float(value), True)
    if isinstance(value, str):
        s = value.strip()
        try:
            return (int(s), True) if integer else (float(s), True)
        except ValueError:
            try:
                return (int(float(s)), True) if integer else (float(s), True)
            except ValueError:
                return None, False
    return None, False


def _coerce_value(value: Any, field_schema: dict[str, Any]) -> tuple[Any, bool]:
    """Coerce `value` to fit `field_schema`. Returns (coerced_value, ok)."""
    t = field_schema.get("type", "string")
    if isinstance(t, list):
        # accept null + first concrete type
        for cand in t:
            if cand != "null":
                t = cand
                break

    if value is None:
        return None, t in ("null",) or False  # None is acceptable only for nullable types

    if t == "boolean":
        v, ok = _coerce_bool(value)
        return v, ok
    if t == "number":
        return _coerce_number(value, integer=False)
    if t == "integer":
        return _coerce_number(value, integer=True)
    if t == "string":
        return (value if isinstance(value, str) else str(value)), True
    if t == "array":
        return (value if isinstance(value, list) else [value]), True
    if t == "object":
        return (value if isinstance(value, dict) else {}), isinstance(value, dict)
    return value, True  # unknown type — pass through


def coerce_and_validate(raw: Any, schema: dict[str, Any]) -> CoercedResponse:
    """Coerce `raw` (a dict, or JSON string) against `schema` (JSON Schema object).

    `schema` may be either the raw OpenAI `json_schema` payload (with `.schema`) or the
    inner schema with `.properties`/`.required`.
    """
    if isinstance(raw, (str, bytes)):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            return CoercedResponse(
                data={},
                coercion_errors=[f"top-level JSON parse failed: {e}"],
                raw=raw,
            )
    else:
        parsed = raw

    # Unwrap the OpenAI response_format envelope if present.
    if isinstance(schema, dict) and "schema" in schema and "properties" not in schema:
        schema = schema["schema"]

    if not isinstance(parsed, dict):
        return CoercedResponse(
            data={},
            coercion_errors=[f"top-level value is not an object: {type(parsed).__name__}"],
            raw=raw,
        )

    properties = schema.get("properties", {}) or {}
    required = schema.get("required", []) or []

    coerced: dict[str, Any] = {}
    errors: list[str] = []

    for field_name, field_schema in properties.items():
        if field_name in parsed:
            value, ok = _coerce_value(parsed[field_name], field_schema)
            if not ok:
                errors.append(f"could not coerce {field_name!r}={parsed[field_name]!r}")
                value = _default_for_type(field_schema)
            coerced[field_name] = value
        else:
            if field_name in required:
                errors.append(f"missing required field: {field_name}")
                coerced[field_name] = _default_for_type(field_schema)
            else:
                coerced[field_name] = None

    # Special-case: confidence is universally meaningful.
    if "confidence" in properties and (coerced.get("confidence") is None):
        coerced["confidence"] = 0.0
        if "confidence" not in [e.split(":")[-1].strip() for e in errors]:
            errors.append("missing optional field: confidence (defaulted to 0.0)")

    # Extra fields (not in schema) are stripped — we just don't carry them across.

    return CoercedResponse(data=coerced, coercion_errors=errors, raw=raw)
