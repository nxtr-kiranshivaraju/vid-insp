"""Prompt assets shipped with the shared package."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(name: str) -> str:
    """Load a markdown prompt file by name (without extension)."""
    p = PROMPTS_DIR / f"{name}.md"
    return p.read_text(encoding="utf-8")


__all__ = ["load_prompt", "PROMPTS_DIR"]
