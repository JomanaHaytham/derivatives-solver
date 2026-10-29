"""Application settings, read from environment variables (and a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # in-browser build has no .env and no python-dotenv
    pass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY") or None)
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"))
    ai_enabled_flag: bool = field(default_factory=lambda: _bool("AI_ENABLED", True))
    ai_max_tokens: int = field(default_factory=lambda: int(os.getenv("AI_MAX_TOKENS", "2500")))
    ai_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("AI_TIMEOUT_SECONDS", "60")))
    math_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("MATH_TIMEOUT_SECONDS", "12")))
    max_history_messages: int = field(default_factory=lambda: int(os.getenv("MAX_HISTORY_MESSAGES", "16")))
    max_message_chars: int = field(default_factory=lambda: int(os.getenv("MAX_MESSAGE_CHARS", "2000")))
    allowed_origins: list[str] = field(default_factory=lambda: [
        o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    ])

    @property
    def ai_enabled(self) -> bool:
        return self.ai_enabled_flag and bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
