"""AI explanations that are cross-checked against the symbolic engine.

Workflow for a new problem:
1. The engine has already computed and verified the derivative.
2. The model writes a teaching explanation and ends with ``FINAL_ANSWER: ...``.
3. We parse that answer with the safe parser and compare it to the engine's.
4. On mismatch we ask the model to correct itself once; if it still
   disagrees, the AI text is discarded and the engine's own steps are shown.
5. The final-answer and verification sections are always generated from the
   engine, never from the model.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import sympy as sp

from ..math_engine.differentiator import expressions_match
from ..math_engine.parser import ParseError, parse_math
from ..math_engine.solver import (
    Solution,
    final_answer_markdown,
    format_solution_markdown,
    verification_markdown,
)
from . import prompts
from .llm_client import ChatTurn, LLMClient, LLMError

log = logging.getLogger(__name__)

_FINAL_RE = re.compile(r"^\s*\**FINAL[_ ]ANSWER\**\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_SECTION_RE = re.compile(r"^#{1,4}\s*(final answer|verification|answer)\b.*$", re.IGNORECASE | re.MULTILINE)


@dataclass
class CheckResult:
    found: bool
    matches: bool
    candidate: str | None = None


@dataclass
class AIExplanation:
    markdown: str
    used_ai: bool
    warnings: list[str] = field(default_factory=list)


def extract_final_answer(text: str) -> str | None:
    matches = _FINAL_RE.findall(text)
    if not matches:
        return None
    ans = matches[-1].strip().strip("$`").strip()
    ans = re.sub(r"^[a-zA-Z]'*\s*\(\s*[a-z]\s*\)\s*=\s*", "", ans)   # "f'(x) = ..."
    ans = re.sub(r"^d\^?\d*y\s*/\s*dx\^?\d*\s*=\s*", "", ans)        # "dy/dx = ..."
    ans = re.sub(r"^y'+\s*=\s*", "", ans)
    return ans or None


def strip_final_answer(text: str) -> str:
    return _FINAL_RE.sub("", text).rstrip()


def strip_model_answer_sections(text: str) -> str:
    """Remove any 'Final answer'/'Verification' section the model added anyway."""
    m = _SECTION_RE.search(text)
    return text[: m.start()].rstrip() if m else text


def check_against(candidate_text: str | None, reference: sp.Expr, variable: sp.Symbol,
                  alternates: list[sp.Expr] | None = None) -> CheckResult:
    if not candidate_text:
        return CheckResult(found=False, matches=False)
    try:
        candidate = parse_math(candidate_text)
    except ParseError:
        return CheckResult(found=True, matches=False, candidate=candidate_text)
    for ref in [reference, *(alternates or [])]:
        if ref is not None and expressions_match(candidate, ref, variable):
            return CheckResult(found=True, matches=True, candidate=candidate_text)
    return CheckResult(found=True, matches=False, candidate=candidate_text)


def _engine_steps_md(sol: Solution) -> str:
    md = format_solution_markdown(sol)
    start = md.find("### Step-by-step solution")
    end = md.find("### Final answer")
    return md[start:end].strip() if start != -1 else md


def _problem_md(sol: Solution) -> str:
    md = format_solution_markdown(sol)
    start, end = md.find("### Problem"), md.find("### Rules we'll use")
    return md[start:end].strip()


def _compose(sol: Solution, body: str, ai_checked: bool) -> str:
    parts = [body.rstrip(), "", "### Final answer", final_answer_markdown(sol), "", "### Verification",
             verification_markdown(sol)]
    if ai_checked:
        parts.append("- The AI tutor's explanation was compared with the engine's result and reaches the same answer.")
    return "\n".join(parts)


async def explain_with_ai(sol: Solution, client: LLMClient, level_hint: str | None = None) -> AIExplanation:
    user = prompts.explain_user_prompt(_problem_md(sol), sol.answer_latex, sol.derivative_plain,
                                       sol.explanation.rules, _engine_steps_md(sol), level_hint)
    turns = [ChatTurn("user", user)]
    alternates = [sol.result.on_curve_form] if sol.result.on_curve_form is not None else []
    warnings: list[str] = []

    for attempt in range(2):
        try:
            text = await client.complete(prompts.EXPLAIN_SYSTEM, turns)
        except LLMError:
            warnings.append("The AI tutor is unavailable right now, so this explanation comes from the "
                            "built-in step-by-step engine.")
            break
        check = check_against(extract_final_answer(text), sol.result.derivative, sol.result.variable, alternates)
        if check.matches:
            body = strip_model_answer_sections(strip_final_answer(text))
            if sol.assumptions:
                body = "\n".join(f"> {a}" for a in sol.assumptions) + "\n\n" + body
            return AIExplanation(_compose(sol, body, ai_checked=True), used_ai=True, warnings=warnings)
        log.info("AI answer mismatch on attempt %d: %s", attempt + 1, check.candidate)
        turns += [ChatTurn("assistant", text),
                  ChatTurn("user", prompts.correction_prompt(check.candidate or "missing", sol.derivative_plain))]
    else:
        warnings.append("The AI explanation did not match the verified result, so it was replaced by the "
                        "engine's own step-by-step solution.")

    return AIExplanation(format_solution_markdown(sol), used_ai=False, warnings=warnings)
