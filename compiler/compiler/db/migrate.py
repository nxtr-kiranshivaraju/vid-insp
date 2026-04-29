"""One-shot migration runner. Applies SQL files in order against a sync URL.

Run on container start, in CI, and from tests.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import psycopg2

from compiler.config import get_settings

# Migrations live in two places: the shared package owns the registry/secrets
# tables (because the runtime also reads dsl_registry); the compiler package
# owns the sessions table.
SHARED_MIGRATIONS = ["vlm_inspector_shared.dsl.migrations:001_initial.sql"]
COMPILER_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _load_shared(name: str) -> str:
    pkg, fname = name.split(":")
    with resources.files(pkg).joinpath(fname).open("r", encoding="utf-8") as f:
        return f.read()


def collect_migrations() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for ref in SHARED_MIGRATIONS:
        out.append((ref, _load_shared(ref)))
    for path in sorted(COMPILER_MIGRATIONS_DIR.glob("*.sql")):
        out.append((str(path.name), path.read_text(encoding="utf-8")))
    return out


def run(dsn: str | None = None) -> None:
    target = dsn or get_settings().sync_url()
    conn = psycopg2.connect(target)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            for name, sql in collect_migrations():
                print(f"applying migration: {name}")
                cur.execute(sql)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
