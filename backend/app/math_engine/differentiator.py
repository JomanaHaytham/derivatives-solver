"""Symbolic differentiation and independent verification with SymPy.

Every result returned from here carries a :class:`Verification` describing
what checks were *actually* run. Callers must never claim more than that.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import mpmath
import sympy as sp

MAX_ORDER = 10


@dataclass
class Verification:
    verified: bool
    method: str            # human-readable description of what was checked
    details: list[str] = field(default_factory=list)


@dataclass
class DerivativeResult:
    original: sp.Expr                 # f(x), or F(x, y) = lhs - rhs for implicit
    variable: sp.Symbol
    order: int
    derivative: sp.Expr               # simplified final answer
    raw_derivative: sp.Expr           # SymPy's direct output before simplifying
    intermediate: list[sp.Expr]       # f', f'', ... (simplified) up to `order`
    verification: Verification
    implicit: bool = False
    dependent: sp.Symbol | None = None
    equation: tuple[sp.Expr, sp.Expr] | None = None
    constants: list[sp.Symbol] = field(default_factory=list)
    on_curve_form: sp.Expr | None = None  # implicit only: result simplified using the equation


def best_simplification(expr: sp.Expr) -> sp.Expr:
    """Pick the shortest equivalent form among a few standard rewrites."""
    candidates = [expr]
    heavy = sp.count_ops(expr) > 60
    # sp.simplify can take a very long time on big expressions; use cheaper rewrites there.
    rewrites = (lambda e: e, sp.factor, sp.expand, sp.together) if heavy else \
        (sp.simplify, sp.factor, sp.expand, sp.together, sp.cancel, sp.trigsimp)
    for fn in rewrites:
        try:
            candidates.append(fn(expr))
        except Exception:  # some rewrites fail on exotic inputs
            continue
    candidates = [c for c in candidates if c is not None]
    expanded = candidates[3] if len(candidates) > 3 else None

    def score(c: sp.Expr) -> tuple:
        # Prefer fewer operations; give the expanded "textbook" form
        # (e.g. 2x sin x + x^2 cos x) a small bonus so we don't over-factor.
        bonus = -0.5 if expanded is not None and c == expanded else 0
        return (sp.count_ops(c) + bonus, len(sp.srepr(c)))

    return min(candidates, key=score)


def tex(e) -> str:
    """LaTeX in school notation (ln instead of log)."""
    return sp.latex(e, ln_notation=True)


def _sample_points(rng: random.Random, n: int) -> list[float]:
    return [rng.uniform(0.35, 2.4) for _ in range(n)]


def numeric_derivative_check(f: sp.Expr, x: sp.Symbol, order: int, candidate: sp.Expr,
                             subs: dict | None = None, points: int = 6) -> Verification:
    """Compare `candidate` against a high-precision numerical derivative of `f`.

    This is independent of SymPy's symbolic differentiation, so it genuinely
    checks the answer rather than repeating the same computation.
    """
    rng = random.Random(1234)
    subs = subs or {}
    f_num = sp.lambdify(x, f.subs(subs), modules="mpmath")
    g_num = sp.lambdify(x, candidate.subs(subs), modules="mpmath")
    agreed, tried = 0, 0
    details: list[str] = []
    mpmath.mp.dps = 30
    for x0 in _sample_points(rng, points * 3):
        if agreed >= points:
            break
        try:
            exact = complex(g_num(mpmath.mpf(x0)))
            approx = complex(mpmath.diff(f_num, mpmath.mpf(x0), order))
        except Exception:
            continue  # outside the domain (e.g. log of a negative number)
        if any(map(lambda v: not mpmath.isfinite(v), (exact.real, approx.real))):
            continue
        if abs(exact.imag) > 1e-12 or abs(approx.imag) > 1e-12:
            continue
        tried += 1
        tol = 1e-8 * max(1.0, abs(exact.real))
        if abs(exact.real - approx.real) <= tol:
            agreed += 1
        else:
            details.append(f"Mismatch at x = {x0:.4f}: formula gives {exact.real:.8g}, numeric derivative {approx.real:.8g}")
            return Verification(False, "numerical comparison", details)
    if agreed >= 3:
        details.append(f"Matched a high-precision numerical derivative at {agreed} random points.")
        return Verification(True, "numerical comparison", details)
    return Verification(False, "numerical comparison",
                        ["Not enough points in the real domain to check numerically."])


def symbolic_equivalence(a: sp.Expr, b: sp.Expr) -> bool | None:
    """True/False when SymPy can decide quickly; None when the expression is too big to simplify."""
    diff = a - b
    try:
        if diff == 0 or sp.expand(diff) == 0:
            return True
        if sp.count_ops(diff) > 120:
            return None
        return sp.simplify(diff) == 0
    except Exception:
        return None


def _constant_values(expr_syms: set[sp.Symbol]) -> dict:
    rng = random.Random(99)
    return {s: sp.Rational(rng.randint(2, 9), rng.randint(2, 5)) for s in expr_syms}


def differentiate(expr: sp.Expr, variable: sp.Symbol, order: int = 1) -> DerivativeResult:
    if order < 1 or order > MAX_ORDER:
        raise ValueError(f"Derivative order must be between 1 and {MAX_ORDER}.")
    intermediate: list[sp.Expr] = []
    current = expr
    for _ in range(order):
        current = best_simplification(sp.diff(current, variable))
        intermediate.append(current)
    raw = sp.diff(expr, variable, order)
    final = intermediate[-1]

    constants = sorted(expr.free_symbols - {variable}, key=str)
    details: list[str] = []
    symbolic_ok = symbolic_equivalence(final, raw)
    if symbolic_ok is True:
        details.append("Simplified form is algebraically identical to SymPy's direct derivative.")
    elif symbolic_ok is None:
        details.append("The expression is too large for a full symbolic comparison; relying on the numerical check.")
    else:
        details.append("Could not confirm the simplified form symbolically.")
    numeric = numeric_derivative_check(expr, variable, order, final, subs=_constant_values(set(constants)))
    details.extend(numeric.details)
    verification = Verification(
        verified=symbolic_ok is not False and numeric.verified,
        method=("symbolic simplification check + independent numerical differentiation" if symbolic_ok
                else "independent numerical differentiation"),
        details=details,
    )
    return DerivativeResult(expr, variable, order, final, raw, intermediate, verification,
                            constants=constants)


def differentiate_implicit(lhs: sp.Expr, rhs: sp.Expr, x: sp.Symbol, y: sp.Symbol,
                           order: int = 1) -> DerivativeResult:
    """dy/dx (and d²y/dx²) for an equation F(x, y) = 0."""
    if order not in (1, 2):
        raise ValueError("Implicit differentiation is supported for first and second derivatives.")
    F = lhs - rhs
    Fx, Fy = sp.diff(F, x), sp.diff(F, y)
    if Fy == 0:
        raise ValueError(f"The equation does not depend on {y}, so d{y}/d{x} is not defined implicitly.")
    dydx = best_simplification(-Fx / Fy)
    intermediate = [dydx]

    # Independent check: differentiate F(x, y(x)) = 0 with y as a function of x,
    # solve the resulting linear equation for y', compare.
    yf = sp.Function(str(y))(x)
    G = F.subs(y, yf)
    dG = sp.diff(G, x)
    yp = sp.Symbol("yp")
    sol1 = sp.solve(dG.subs(sp.Derivative(yf, x), yp), yp)
    details: list[str] = []
    ok1 = bool(sol1) and symbolic_equivalence(sol1[0].subs(yf, y), dydx)
    details.append("Re-derived dy/dx by treating y as y(x) and solving for y'; both methods agree."
                   if ok1 else "The two derivations of dy/dx could not be matched symbolically.")

    final, raw = dydx, -Fx / Fy
    ok2 = True
    if order == 2:
        # Differentiate dy/dx again, substituting y' = dy/dx.
        d2 = sp.diff(dydx.subs(y, yf), x).subs(sp.Derivative(yf, x), dydx.subs(y, yf)).subs(yf, y)
        final = best_simplification(d2)
        intermediate.append(final)
        raw = d2
        # Independent check: differentiate dG again and solve for y''.
        ypp = sp.Symbol("ypp")
        d2G = sp.diff(dG, x).subs(sp.Derivative(yf, (x, 2)), ypp).subs(sp.Derivative(yf, x), dydx.subs(y, yf))
        sol2 = sp.solve(d2G, ypp)
        ok2 = bool(sol2) and symbolic_equivalence(sol2[0].subs(yf, y), final)
        details.append("Second derivative re-derived from the twice-differentiated equation; results agree."
                       if ok2 else "Could not confirm the second derivative by a second method.")

    verification = Verification(ok1 and ok2, "two independent symbolic derivations", details)
    alternate = reduce_on_curve(final, F, x, y)
    constants = sorted(F.free_symbols - {x, y}, key=str)
    return DerivativeResult(F, x, order, final, raw, intermediate, verification,
                            implicit=True, dependent=y, equation=(lhs, rhs), constants=constants,
                            on_curve_form=alternate)


def reduce_on_curve(expr: sp.Expr, F: sp.Expr, x: sp.Symbol, y: sp.Symbol) -> sp.Expr | None:
    """Use the original equation F = 0 to shorten a result (e.g. -(x²+y²)/y³ -> -25/y³)."""
    try:
        num, den = sp.fraction(sp.together(expr))
        if not (num.is_polynomial(x, y) and F.is_polynomial(x, y)):
            return None
        _, rem = sp.reduced(sp.expand(num), [sp.expand(F)], x, y)
        candidate = best_simplification(rem / den)
        if sp.count_ops(candidate) < sp.count_ops(expr) and candidate != expr:
            return candidate
    except Exception:
        return None
    return None


def expressions_match(candidate: sp.Expr, reference: sp.Expr, variable: sp.Symbol,
                      extra: set[sp.Symbol] | None = None) -> bool:
    """True if two formulas are the same function (symbolically or numerically)."""
    by_name = {sym.name: sym for sym in reference.free_symbols | {variable}}
    candidate = candidate.subs({sym: by_name[sym.name] for sym in candidate.free_symbols
                                if sym.name in by_name and by_name[sym.name] != sym})
    if symbolic_equivalence(candidate, reference):
        return True
    syms = (candidate.free_symbols | reference.free_symbols) - {variable}
    rng = random.Random(7)
    subs = {s: sp.Rational(rng.randint(2, 9), rng.randint(2, 5)) for s in syms}
    a = sp.lambdify(variable, candidate.subs(subs), modules="mpmath")
    b = sp.lambdify(variable, reference.subs(subs), modules="mpmath")
    agreed = 0
    for x0 in _sample_points(rng, 12):
        try:
            va, vb = complex(a(mpmath.mpf(x0))), complex(b(mpmath.mpf(x0)))
        except Exception:
            continue
        if abs(va - vb) > 1e-9 * max(1.0, abs(vb)):
            return False
        agreed += 1
    return agreed >= 4
