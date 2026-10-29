"""Orchestrates one chat turn: input -> intent -> math engine -> AI -> response.

This is the only place that knows about all three layers. The math engine
never calls the AI, and the AI never computes the answer on its own.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys

from ..ai.explainer import explain_with_ai
from ..ai.llm_client import ChatTurn, LLMClient
from ..ai.tutor import answer_followup
from ..config import Settings
from ..inputs.base import UnsupportedInput, get_adapter
from ..math_engine.intent import Intent, ProblemRequest, classify
from ..math_engine.parser import ParseError
from ..math_engine.solver import ClarificationNeeded, Solution, format_solution_markdown, solve
from ..schemas import ChatRequest, ChatResponse, SolutionContext
from .offline_tutor import offline_followup

log = logging.getLogger(__name__)

_STYLE_HINT = re.compile(r"\b(simple|simpler|simply|easy|beginner|detailed|in detail|like i'?m|eli5|slowly)\b", re.I)
_PROSE = re.compile(r"\b(why|how|what|explain|mean|difference|help|understand)\b", re.I)


class ChatService:
    def __init__(self, settings: Settings, llm: LLMClient | None):
        self.settings = settings
        self.llm = llm

    async def handle(self, req: ChatRequest) -> ChatResponse:
        try:
            text = await get_adapter(req.input_type).to_text(req.message)
        except UnsupportedInput as exc:
            return ChatResponse(content=str(exc), kind="error", source="engine")
        if len(text) > self.settings.max_message_chars:
            return ChatResponse(content="That message is a bit long. Please send one problem at a time.",
                                kind="clarification", source="engine")

        context = req.context.model_dump() if req.context else None
        c = classify(text)

        if c.intent is Intent.OUT_OF_SCOPE:
            return ChatResponse(
                content=(f"This app focuses on **derivatives**, so I can't help with {c.topic} here. "
                         "I can differentiate functions (power, product, quotient and chain rules, trig, "
                         "exponential and log functions, implicit and higher-order derivatives). "
                         "Try something like *Differentiate x^2 sin(x)*."),
                kind="out_of_scope", source="engine", context=req.context)

        if c.intent is Intent.PROBLEM:
            request = c.request
            if request.refers_to_previous:
                if not context:
                    return self._clarify("Which function do you mean? Please type the expression you want "
                                         "me to differentiate.", req)
                request = ProblemRequest(expression_text=context["original"],
                                         variable=request.variable or context.get("variable"),
                                         order=request.order, implicit=bool(context.get("implicit")))
            try:
                if sys.platform == "emscripten":  # in the browser: no threads, the web worker enforces a timeout
                    solution = solve(request)
                else:
                    solution = await asyncio.wait_for(asyncio.to_thread(solve, request),
                                                      timeout=self.settings.math_timeout_seconds)
            except ClarificationNeeded as exc:
                return self._clarify(exc.message, req)
            except ParseError as exc:
                if self.llm and _PROSE.search(text):
                    return await self._followup(text, req, context)  # e.g. "explain why the derivative of ..."
                hint = f"\n\n*Hint:* {exc.hint}" if exc.hint else ""
                return self._clarify(f"I couldn't read that expression reliably: {exc.message}{hint}\n\n"
                                     "Could you rewrite it? For example: *Differentiate (x^2 + 1)^5*.", req)
            except (ValueError, NotImplementedError) as exc:
                return self._clarify(str(exc), req)
            except asyncio.TimeoutError:
                return ChatResponse(content="That expression is too complex for me to simplify reliably in "
                                            "a reasonable time. Could you try a smaller problem or split it "
                                            "into parts?", kind="error", source="engine", context=req.context)
            return await self._present(solution, text)

        return await self._followup(text, req, context)

    # ------------------------------------------------------------------
    async def _present(self, sol: Solution, text: str) -> ChatResponse:
        ctx = SolutionContext(**sol.to_context())
        if self.llm:
            hint = text if _STYLE_HINT.search(text) else None
            ai = await explain_with_ai(sol, self.llm, level_hint=hint)
            return ChatResponse(content=ai.markdown, kind="solution", source="ai" if ai.used_ai else "engine",
                                verified=sol.verified, context=ctx, warnings=ai.warnings)
        return ChatResponse(content=format_solution_markdown(sol), kind="solution", source="engine",
                            verified=sol.verified, context=ctx)

    async def _followup(self, text: str, req: ChatRequest, context: dict | None) -> ChatResponse:
        if not self.llm:
            reply = offline_followup(text, context)
            return ChatResponse(content=reply.markdown, kind="follow_up", source="engine",
                                context=req.context, practice=reply.practice)
        history = [ChatTurn(m.role, m.content[:6000]) for m in req.history[-self.settings.max_history_messages:]]
        reply = await answer_followup(text, history, context, self.llm)
        return ChatResponse(content=reply.markdown, kind="follow_up", source="ai", context=req.context,
                            warnings=reply.warnings,
                            verified=reply.checked if reply.checked is not None else None)

    @staticmethod
    def _clarify(message: str, req: ChatRequest) -> ChatResponse:
        return ChatResponse(content=message, kind="clarification", source="engine", context=req.context)
