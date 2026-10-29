"""Generate practice problems that exercise the same rules as a solved problem.

Problems are built from templates with random coefficients, then run through
the real solver so every generated problem is guaranteed to be solvable.
"""

from __future__ import annotations

import random

import sympy as sp

from .differentiator import tex

x = sp.Symbol("x")

_TEMPLATES: dict[str, list] = {
    "Power rule": [lambda a, b, c: a * x**b + c * x, lambda a, b, c: a * x**sp.Rational(b, 2) - c / x],
    "Constant multiple rule": [lambda a, b, c: a * x**b],
    "Sum and difference rule": [lambda a, b, c: x**b - a * x**2 + c * x - b],
    "Product rule": [lambda a, b, c: x**b * sp.sin(x), lambda a, b, c: (a * x + c) * sp.exp(x),
                     lambda a, b, c: x**a * sp.log(x)],
    "Quotient rule": [lambda a, b, c: (x**2 + a) / (x - c), lambda a, b, c: sp.sin(x) / (x**b),
                      lambda a, b, c: (a * x + 1) / (x**2 + c)],
    "Chain rule": [lambda a, b, c: (a * x**2 + c)**b, lambda a, b, c: sp.sin(a * x**2),
                   lambda a, b, c: sp.exp(a * x**b), lambda a, b, c: sp.sqrt(a * x**2 + c)],
    "Trigonometric derivatives": [lambda a, b, c: a * sp.sin(x) - c * sp.cos(x), lambda a, b, c: sp.tan(a * x),
                                  lambda a, b, c: sp.cos(x)**b],
    "Exponential rule": [lambda a, b, c: a * sp.exp(b * x), lambda a, b, c: sp.Integer(a)**x + x**b],
    "Logarithmic rule": [lambda a, b, c: sp.log(a * x**2 + c), lambda a, b, c: x * sp.log(x) - a * x],
    "Radicals as fractional powers": [lambda a, b, c: sp.sqrt(x) + a * x**sp.Rational(1, 3),
                                      lambda a, b, c: sp.sqrt(a * x + c)],
    "Implicit differentiation": [lambda a, b, c: f"x^2 + {a}y^2 = {b + c}", lambda a, b, c: f"x^3 + xy + y^2 = {a}",
                                 lambda a, b, c: f"sin(y) + x^{b} = {a}"],
    "Higher-order derivatives": [lambda a, b, c: ("second", x**(b + 2) - a * sp.sin(x)),
                                 lambda a, b, c: ("second", sp.exp(a * x) * x)],
}

_PRIORITY = ["Implicit differentiation", "Higher-order derivatives", "Quotient rule", "Product rule",
             "Chain rule", "Logarithmic rule", "Exponential rule", "Trigonometric derivatives",
             "Radicals as fractional powers", "Sum and difference rule", "Power rule",
             "Constant multiple rule"]


def _to_prompt(item) -> tuple[str, str]:
    """(markdown shown to student, plain text they can send back)."""
    if isinstance(item, str):  # implicit equation
        return f"Find $\\frac{{dy}}{{dx}}$ if ${item}$", f"Find dy/dx if {item}"
    if isinstance(item, tuple):
        word, expr = item
        return (f"Find the {word} derivative of $f(x) = {tex(expr)}$",
                f"Find the {word} derivative of {sp.sstr(expr).replace('**', '^')}")
    return (f"Differentiate $f(x) = {tex(item)}$",
            f"Differentiate {sp.sstr(item).replace('**', '^')}")


def practice_problems(rules: list[str] | None, count: int = 3, seed: int | None = None,
                      exclude: str | None = None) -> list[tuple[str, str]]:
    """`exclude` is the original problem (SymPy string) so we never hand it back."""
    rng = random.Random(seed)
    rules = rules or []
    focus = [r for r in _PRIORITY if r in rules] or ["Chain rule", "Product rule", "Power rule"]
    focus = focus[:2] or focus
    problems: list[tuple[str, str]] = []
    seen: set[str] = set()
    used_templates: set[int] = set()
    attempts = 0
    while len(problems) < count and attempts < 40:
        attempts += 1
        rule = focus[len(problems) % len(focus)]
        options = [t for t in _TEMPLATES[rule] if id(t) not in used_templates] or _TEMPLATES[rule]
        tmpl = rng.choice(options)
        used_templates.add(id(tmpl))
        a, b, c = rng.randint(2, 6), rng.randint(2, 5), rng.randint(1, 7)
        try:
            item = tmpl(a, b, c)
        except Exception:
            continue
        if exclude and not isinstance(item, (str, tuple)) and sp.sstr(item) == exclude:
            continue
        shown, plain = _to_prompt(item)
        if plain not in seen:
            seen.add(plain)
            problems.append((shown, plain))
    return problems
