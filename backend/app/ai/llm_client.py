"""Thin, swappable wrapper around the LLM provider.

The rest of the app only depends on the :class:`LLMClient` protocol, so a
different provider (or a fake in tests) can be dropped in without touching
the explanation logic. The API key lives only on the server.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from ..config import Settings

log = logging.getLogger(__name__)


@dataclass
class ChatTurn:
    role: str      # "user" | "assistant"
    content: str


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    name: str

    async def complete(self, system: str, messages: list[ChatTurn], max_tokens: int | None = None) -> str: ...


class AnthropicClient:
    """Claude via the official Anthropic Python SDK."""

    def __init__(self, settings: Settings):
        from anthropic import AsyncAnthropic  # imported lazily so tests don't need it

        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=settings.ai_timeout_seconds,
                                      max_retries=2)
        self._model = settings.anthropic_model
        self._max_tokens = settings.ai_max_tokens
        self.name = f"anthropic:{self._model}"

    async def complete(self, system: str, messages: list[ChatTurn], max_tokens: int | None = None) -> str:
        payload = _merge_consecutive(messages)
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens or self._max_tokens,
                system=system,
                messages=[{"role": m.role, "content": m.content} for m in payload],
            )
        except Exception as exc:  # network, auth, rate limit ...
            log.warning("LLM request failed: %s", exc)
            raise LLMError(str(exc)) from exc
        text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        if not text.strip():
            raise LLMError("The model returned an empty response.")
        return text


def _merge_consecutive(messages: list[ChatTurn]) -> list[ChatTurn]:
    """The Messages API wants alternating roles starting with 'user'."""
    merged: list[ChatTurn] = []
    for m in messages:
        if merged and merged[-1].role == m.role:
            merged[-1] = ChatTurn(m.role, merged[-1].content + "\n\n" + m.content)
        else:
            merged.append(ChatTurn(m.role, m.content))
    while merged and merged[0].role != "user":
        merged.pop(0)
    return merged


def build_client(settings: Settings) -> LLMClient | None:
    if not settings.ai_enabled:
        return None
    return AnthropicClient(settings)
