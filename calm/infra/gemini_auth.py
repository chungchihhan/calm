# calm/infra/gemini.py
from __future__ import annotations

import os
from pathlib import Path

from .settings import CONFIG_DIR, ensure_600

GEMINI_KEY_PATH: Path = CONFIG_DIR / "gemini.key"

def load_api_key(explicit: str | None = None) -> str | None:
    """Resolve Gemini API key from (1) explicit, (2) env, (3) key file."""
    if explicit and explicit.strip():
        return explicit.strip()
    env = os.getenv("GEMINI_API_KEY")
    if env and env.strip():
        return env.strip()
    if GEMINI_KEY_PATH.exists():
        return GEMINI_KEY_PATH.read_text(encoding="utf-8").strip().splitlines()[0]
    return None

def save_api_key(key: str) -> None:
    GEMINI_KEY_PATH.write_text(key.strip() + "\n", encoding="utf-8")
    ensure_600(GEMINI_KEY_PATH)