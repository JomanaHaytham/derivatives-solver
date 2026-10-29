"""High-level entry point of the math layer.

``solve(request)`` turns a :class:`ProblemRequest` into a :class:`Solution`
containing the verified derivative, the rule-based steps and a ready-to-show
Markdown rendering. It knows nothing about the AI layer or HTTP.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy as sp

from .differentiator import DerivativeResult, differentiate, differentiate_implicit, tex
from .intent import ProblemRequest
from .parser import ParseError, parse_equation, parse_math
from .steps import Explanation, explain_derivative


class ClarificationNeeded(Exception):
    """The input is ambiguous or incomplete; ask the student instead of guessing."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass
class Solution:
    request: ProblemRequest
    result: DerivativeResult
    explanation: Explanation
    problem_latex: str
    answer_latex: str             # left-hand side included, e.g. f'(x) = 3x^2
    derivative_latex: str         # right-hand side only
    derivative_plain: str         # SymPy string, used to compare against AI output
    original_plain: str
    notation: str                 # e.g. "f'(x)", "dy/dx"
    assumptions: list[str] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        return self.result.verification.verified

    def to_context(self) -> dict:
        """Compact, JSON-safe summary the frontend sends back on follow-ups."""
        return {
            "original": self.original_plain,
            "original_latex": self.problem_latex,
            "variable": str(self.result.variable),
            "order": self.result.order,
            "implicit": self.result.implicit,
            "derivative": self.derivative_plain,
            "derivative_latex": self.derivative_latex,
            "answer_latex": self.answer_latex,
            "rules": self.explanation.rules,
            "verified": self.verified,
            "verification_method": self.result.verification.method,
        }


_PREFERRED_VARS = ["x", "t", "theta", "u", "s", "r", "z"]


def _choose_variable(expr_symbols: set[sp.Symbol], requested: str | None) -> tuple[sp.Symbol, list[str]]:
    names = {str(s): s for s in expr_symbols}
    if requested:
        var = names.get(requested, sp.Symbol(requested))
        notes = []
        others = sorted(n for n in names if n != requested)
        if others:
            notes.append(f"I treated {', '.join('$' + n + '$' for n in others)} as constant(s).")
        return var, notes
    if not names:
        return sp.Symbol("x"), []
    for pref in _PREFERRED_VARS:
        if pref in names:
            others = sorted(n for n in names if n != pref)
            notes = []
            if others:
                notes.append(
                    f"I differentiated with respect to ${pref}$ and treated "
                    f"{', '.join('$' + n + '$' for n in others)} as constant(s). "
                    "Tell me if you meant a different variable.")
            return names[pref], notes
    if len(names) == 1:
        return next(iter(names.values())), []
    raise ClarificationNeeded(
        "Your expression has more than one letter ("
        + ", ".join(f"${n}$" for n in sorted(names))
        + "). Which variable should I differentiate with respect to? "
        "For example: *differentiate ... with respect to t*.")


def _notation(var: sp.Symbol, order: int, fname: str | None, implicit: bool) -> tuple[str, str]:
    v = tex(var)
    if implicit or fname == "y":
        dep = "y"
        if order == 1:
            return f"\\frac{{d{dep}}}{{d{v}}}", f"d{dep}/d{v}"
        return f"\\frac{{d^{{{order}}}{dep}}}{{d{v}^{{{order}}}}}", f"d^{order}{dep}/d{v}^{order}"
    f = fname or "f"
    primes = "'" * order if order <= 3 else f"^{{({order})}}"
    return f"{f}{primes}({v})", f"{f}{primes}({v})"


def solve(request: ProblemRequest) -> Solution:
    text = request.expression_text.strip()
    if not text:
        raise ClarificationNeeded("Which function should I differentiate? Please type the expression, "
                                  "for example *d/dx (x^2 + 3x)*.")
    if re.search(r"\.\.\.|\?\?", text):
        raise ClarificationNeeded("Part of the expression seems to be missing. Could you type it in full?")

    assumptions: list[str] = []
    if request.implicit:
        lhs, rhs = parse_equation(text)
        syms = (lhs.free_symbols | rhs.free_symbols)
        names = {str(s): s for s in syms}
        x = names.get(request.variable or "x", sp.Symbol(request.variable or "x"))
        if "y" not in names:
            raise ClarificationNeeded("For implicit differentiation I expect an equation in $x$ and $y$, "
                                      "for example *x^2 + y^2 = 25*.")
        y = names["y"]
        if request.order > 2:
            raise ClarificationNeeded("I can do implicit differentiation for the first and second derivative. "
                                      "Could you ask for $dy/dx$ or $d^2y/dx^2$?")
        result = differentiate_implicit(lhs, rhs, x, y, request.order)
        problem_latex = f"{tex(lhs)} = {tex(rhs)}"
        original_plain = f"{lhs} = {rhs}"
        others = sorted(n for n in names if n not in (str(x), "y"))
        if others:
            assumptions.append(f"I treated {', '.join('$' + n + '$' for n in others)} as constant(s).")
    else:
        expr = parse_math(text)
        x, notes = _choose_variable(expr.free_symbols, request.variable)
        assumptions.extend(notes)
        result = differentiate(expr, x, request.order)
        if expr.has(sp.Abs):
            assumptions.append("An absolute value $|u|$ has derivative $\\operatorname{sign}(u)\\,u'$, which is "
                               "undefined wherever the inside $u$ equals 0.")
        problem_latex = tex(expr)
        original_plain = str(expr)

    lhs_tex, lhs_plain = _notation(x, request.order, request.function_name, request.implicit)
    explanation = explain_derivative(result)
    derivative_latex = tex(result.derivative)
    return Solution(
        request=request, result=result, explanation=explanation,
        problem_latex=problem_latex,
        answer_latex=f"{lhs_tex} = {derivative_latex}",
        derivative_latex=derivative_latex,
        derivative_plain=str(result.derivative),
        original_plain=original_plain,
        notation=lhs_plain,
        assumptions=assumptions,
    )


def display(latex: str) -> str:
    """A display-math block on its own lines (renders reliably in Markdown)."""
    return f"$$\n{latex}\n$$"


def inline_math(text: str) -> str:
    """Convert \\( ... \\) delimiters to $ ... $ for Markdown math."""
    return text.replace("\\(", "$").replace("\\)", "$")


def problem_statement(sol: Solution) -> str:
    v = tex(sol.result.variable)
    if sol.result.implicit:
        what = "dy/dx" if sol.result.order == 1 else "the second derivative $d^2y/dx^2$"
        return f"Find {what} for the equation\n\n" + display(sol.problem_latex)
    order_word = {1: "", 2: "second ", 3: "third "}.get(sol.result.order, f"{sol.result.order}th ")
    name = sol.request.function_name or "f"
    if sol.request.function_name == "y":
        return f"Find the {order_word}derivative of\n\n" + display(f"y = {sol.problem_latex}")
    return f"Find the {order_word}derivative of\n\n" + display(f"{name}({v}) = {sol.problem_latex}")


def alternate_form(sol: Solution) -> sp.Expr | None:
    """A second, equally valid way of writing the answer (expanded / on-curve)."""
    if sol.result.implicit:
        return sol.result.on_curve_form
    d = sol.result.derivative
    try:
        alt = sp.expand(d)
    except Exception:
        return None
    if alt != d and tex(alt) != tex(d) and sp.count_ops(alt) <= sp.count_ops(d) + 4 and len(sp.Add.make_args(alt)) <= 4:
        return alt
    return None


def final_answer_markdown(sol: Solution) -> str:
    out = display(f"\\boxed{{{sol.answer_latex}}}")
    alt = alternate_form(sol)
    if alt is not None:
        how = "using the original equation" if sol.result.implicit else "expanded"
        out += f"\n\nEquivalent form ({how}): ${tex(alt)}$"
    return out


def verification_markdown(sol: Solution) -> str:
    ver = sol.result.verification
    if ver.verified:
        lines = [f"**✅ Verified** by the symbolic math engine ({ver.method})."]
    else:
        lines = ["**⚠️ Not fully verified.** The result comes from the symbolic engine, "
                 "but the independent check did not complete, so please double-check it."]
    lines += [f"- {d}" for d in ver.details]
    return "\n".join(lines)


def format_solution_markdown(sol: Solution) -> str:
    """Complete step-by-step answer produced without any AI model."""
    parts = ["Let's solve this step by step.", "", "### Problem", problem_statement(sol)]
    if sol.assumptions:
        parts += ["", *[f"> {a}" for a in sol.assumptions]]
    parts += ["", "### Rules we'll use"]
    for rule in sol.explanation.rules:
        reason = sol.explanation.rule_reasons.get(rule)
        parts.append(f"- **{rule}**" + (f" — {inline_math(reason)}" if reason else ""))
    parts += ["", "### Step-by-step solution"]
    for i, step in enumerate(sol.explanation.steps, 1):
        parts += ["", f"**Step {i}: {step.title}**", "", display(step.latex)]
        if step.explanation:
            parts += ["", inline_math(step.explanation)]
    parts += ["", "### Final answer", final_answer_markdown(sol)]
    parts += ["", "### Verification", verification_markdown(sol)]
    return "\n".join(parts)


__all__ = ["final_answer_markdown", "solve", "Solution", "ClarificationNeeded", "ParseError",
           "format_solution_markdown", "verification_markdown", "problem_statement", "inline_math"]
