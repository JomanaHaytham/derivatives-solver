"""Entry point used by the static website, where this code runs in the browser (Pyodide).

The web worker calls ``await handle(json_string)`` and gets a JSON string back
with the same shape as the HTTP API's ``/api/chat`` response. The AI layer is
off here, because an API key must never be shipped to the browser.
"""

from __future__ import annotations

import json

from .config import Settings
from .schemas import ChatRequest, HistoryMessage, SolutionContext
from .services.chat_service import ChatService

_service = ChatService(Settings(anthropic_api_key=None, ai_enabled_flag=False), None)


def _request(data: dict) -> ChatRequest:
    message = str(data.get("message") or "")[:4000]
    history = [HistoryMessage(role=h["role"], content=str(h.get("content", ""))[:20000])
               for h in data.get("history") or [] if h.get("role") in ("user", "assistant")]
    ctx = data.get("context")
    context = SolutionContext(**ctx) if isinstance(ctx, dict) and ctx.get("derivative") else None
    return ChatRequest(message=message, input_type=data.get("input_type", "text"), history=history,
                       context=context)


async def handle(payload: str) -> str:
    try:
        req = _request(json.loads(payload))
        if not req.message.strip():
            raise ValueError("empty message")
        resp = await _service.handle(req)
        return json.dumps(resp.model_dump())
    except Exception:
        return json.dumps({"content": "Something went wrong while solving that. Please try rephrasing the problem.",
                           "kind": "error", "source": "engine", "verified": None, "context": None,
                           "warnings": [], "practice": []})


def warm_up() -> None:
    """Import SymPy and solve one problem so the student's first question is fast."""
    from .math_engine.intent import classify
    from .math_engine.solver import solve

    solve(classify("Differentiate x^2 sin(x)").request)
