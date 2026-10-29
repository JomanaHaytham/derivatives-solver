"""Conversational follow-ups ("why the chain rule?", "explain step 2 simpler")."""

from __future__ import annotations

from dataclasses import dataclass, field

import sympy as sp

from ..math_engine.differentiator import tex
from ..math_engine.parser import ParseError, parse_math
from . import prompts
from .explainer import check_against, extract_final_answer, strip_final_answer
from .llm_client import ChatTurn, LLMClient, LLMError


@dataclass
class TutorReply:
    markdown: str
    warnings: list[str] = field(default_factory=list)
    checked: bool | None = None  # None = no derivative to check in the reply


def context_reference(context: dict | None) -> tuple[sp.Expr, sp.Symbol] | None:
    """Re-parse the stored derivative (client-supplied data, so use the safe parser)."""
    if not context or not context.get("derivative"):
        return None
    try:
        expr = parse_math(str(context["derivative"]))
    except ParseError:
        return None
    name = str(context.get("variable") or "x")
    var = next((s for s in expr.free_symbols if s.name == name), sp.Symbol(name))
    return expr, var


async def answer_followup(message: str, history: list[ChatTurn], context: dict | None,
                          client: LLMClient) -> TutorReply:
    system = prompts.FOLLOWUP_SYSTEM + "\n\n" + prompts.followup_context_block(context)
    turns = [*history, ChatTurn("user", message)]
    ref = context_reference(context)

    try:
        text = await client.complete(system, turns)
    except LLMError:
        return TutorReply("Sorry — I couldn't reach the AI tutor just now. Please try again in a moment. "
                          "You can still send any derivative problem and the built-in engine will solve it "
                          "step by step.", warnings=["AI tutor unavailable"])

    claimed = extract_final_answer(text)
    if not claimed or ref is None:
        return TutorReply(strip_final_answer(text))

    reference, var = ref
    check = check_against(claimed, reference, var)
    if check.matches:
        return TutorReply(strip_final_answer(text) +
                          "\n\n> ✅ This method gives the same result as the engine-verified answer.", checked=True)

    # One correction round, then fall back to an explicit warning.
    try:
        text2 = await client.complete(system, [*turns, ChatTurn("assistant", text), ChatTurn(
            "user", prompts.correction_prompt(claimed, str(reference)))])
        check2 = check_against(extract_final_answer(text2), reference, var)
        if check2.matches:
            return TutorReply(strip_final_answer(text2) +
                              "\n\n> ✅ This method gives the same result as the engine-verified answer.",
                              checked=True)
    except LLMError:
        pass
    note = (f"\n\n> ⚠️ **Check failed:** the working above ends with a result that does **not** match the "
            "engine-verified derivative\n>\n> $$\n> " + tex(reference) + "\n> $$\n>\n> Please rely on the "
            "verified answer; the explanation above contains a mistake.")
    return TutorReply(strip_final_answer(text) + note, warnings=["Follow-up answer did not match verified result"],
                      checked=False)
