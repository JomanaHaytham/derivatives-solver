"""Deterministic, rule-based step-by-step derivations.

Walks the SymPy expression tree, names the differentiation rule used at each
node and records a LaTeX line plus a plain-language explanation. Every
derivative that appears in a step is computed by SymPy, so the steps are
always mathematically correct; this module only decides how to *present*
them.

These steps are shown directly when no AI model is configured, and are given
to the AI model as a verified scaffold when one is.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sympy as sp

from .differentiator import DerivativeResult, best_simplification, tex

MAX_STEPS = 28


@dataclass
class Step:
    title: str
    latex: str
    explanation: str
    rule: str | None = None


@dataclass
class Explanation:
    rules: list[str]
    steps: list[Step]
    rule_reasons: dict[str, str] = field(default_factory=dict)


RULE_REASONS = {
    "Constant rule": "the derivative of a constant is 0 because a constant never changes.",
    "Power rule": "the expression is a variable raised to a constant power: \\(\\frac{d}{dx}x^n = nx^{n-1}\\).",
    "Constant multiple rule": "a constant factor can be pulled out: \\(\\frac{d}{dx}[c\\,f(x)] = c\\,f'(x)\\).",
    "Sum and difference rule": "the expression is a sum/difference of terms, so we differentiate each term separately.",
    "Product rule": "two non-constant functions are multiplied: \\((uv)' = u'v + uv'\\).",
    "Quotient rule": "one non-constant function is divided by another: \\(\\left(\\frac{u}{v}\\right)' = \\frac{u'v - uv'}{v^2}\\).",
    "Chain rule": "a function is applied to an inner expression (a function inside a function): \\(\\frac{d}{dx}f(g(x)) = f'(g(x))\\,g'(x)\\).",
    "Trigonometric derivatives": "the expression contains trigonometric functions with known derivatives.",
    "Inverse trigonometric derivatives": "the expression contains inverse trig functions with known derivatives.",
    "Hyperbolic derivatives": "the expression contains hyperbolic functions with known derivatives.",
    "Exponential rule": "the expression contains an exponential: \\(\\frac{d}{dx}e^x = e^x\\) and \\(\\frac{d}{dx}a^x = a^x\\ln a\\).",
    "Logarithmic rule": "the expression contains a logarithm: \\(\\frac{d}{dx}\\ln x = \\frac{1}{x}\\).",
    "Radicals as fractional powers": "a root can be rewritten as a fractional power, e.g. \\(\\sqrt{x} = x^{1/2}\\), so the power rule applies.",
    "Logarithmic differentiation": "both the base and the exponent contain the variable, so we take ln of both sides first.",
    "Implicit differentiation": "y is mixed into the equation and is not isolated, so we differentiate both sides and treat y as a function of x.",
    "Higher-order derivatives": "a higher derivative is found by differentiating the previous derivative again.",
}

_TRIG = (sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc)
_INV_TRIG = (sp.asin, sp.acos, sp.atan, sp.acot, sp.asec, sp.acsc)
_HYP = (sp.sinh, sp.cosh, sp.tanh)


def L(e) -> str:
    return tex(e)


def P(e) -> str:
    """LaTeX with parentheses when the expression is a sum or negative."""
    s = L(e)
    if isinstance(e, sp.Add) or (isinstance(e, sp.Mul) and e.could_extract_minus_sign()):
        return f"\\left({s}\\right)"
    return s


class StepBuilder:
    def __init__(self, x: sp.Symbol):
        self.x = x
        self.steps: list[Step] = []
        self.rules: list[str] = []
        self.dx = f"\\frac{{d}}{{d{L(x)}}}"

    # -- bookkeeping -------------------------------------------------
    def rule(self, name: str) -> None:
        if name not in self.rules:
            self.rules.append(name)

    def add(self, title: str, latex: str, explanation: str, rule: str | None = None) -> None:
        if rule:
            self.rule(rule)
        if len(self.steps) < MAX_STEPS:
            self.steps.append(Step(title, latex, explanation, rule))

    def D(self, e) -> str:
        return f"{self.dx}\\left[{L(e)}\\right]"

    # -- classification ----------------------------------------------
    def _function_rule(self, f) -> str:
        if isinstance(f, _TRIG):
            return "Trigonometric derivatives"
        if isinstance(f, _INV_TRIG):
            return "Inverse trigonometric derivatives"
        if isinstance(f, _HYP):
            return "Hyperbolic derivatives"
        if isinstance(f, sp.exp):
            return "Exponential rule"
        if isinstance(f, sp.log):
            return "Logarithmic rule"
        return "Standard derivative"

    def simple_rule(self, e) -> str | None:
        """Rule name if `e` can be differentiated in a single obvious line."""
        x = self.x
        if not e.has(x):
            return "Constant rule"
        if e == x:
            return "Power rule"
        if isinstance(e, sp.Pow) and e.base == x and not e.exp.has(x):
            return "Power rule"
        if isinstance(e, sp.Pow) and not e.base.has(x) and e.exp == x:
            return "Exponential rule"
        if isinstance(e, sp.Function) and len(e.args) == 1 and e.args[0] == x:
            return self._function_rule(e)
        if isinstance(e, sp.Mul):
            coeff, rest = e.as_independent(x, as_Add=False)
            if coeff != 1 and rest != e:
                inner = self.simple_rule(rest)
                if inner:
                    return inner
        return None

    def inline_rule(self, e) -> str | None:
        """Like simple_rule, but also accepts short sums of simple terms (x^2 + 1)
        when they appear as a *part* of a bigger problem."""
        r = self.simple_rule(e)
        if r:
            return r
        if isinstance(e, sp.Add) and len(e.args) <= 4 and all(self.simple_rule(t) for t in e.args):
            for t in e.args:
                self.rule(self.simple_rule(t))
            self.rule("Sum and difference rule")
            return "Sum and difference rule"
        return None

    # -- main recursive explainer ------------------------------------
    def explain(self, e, top: bool = False) -> sp.Expr:
        x = self.x
        d = sp.diff(e, x)
        rule = self.simple_rule(e)

        if rule:
            self._simple_step(e, d, rule)
            return d

        if isinstance(e, sp.Add):
            return self._sum(e, d)
        if isinstance(e, sp.Mul):
            return self._mul(e, d)
        if isinstance(e, sp.Pow):
            return self._pow(e, d)
        if isinstance(e, sp.Function) and len(e.args) == 1:
            return self._chain_function(e, d)

        self.add("Differentiate directly", f"{self.D(e)} = {L(d)}",
                 "This expression is differentiated with its standard formula.")
        return d

    def _simple_step(self, e, d, rule: str) -> None:
        x = self.x
        if rule == "Constant rule":
            why = "This is a constant, and the derivative of any constant is 0."
        elif rule == "Power rule":
            coeff, rest = e.as_independent(x, as_Add=False)
            n = rest.exp if isinstance(rest, sp.Pow) else 1
            if coeff != 1:
                self.rule("Constant multiple rule")
            why = (f"Power rule: bring down the exponent \\({L(n)}\\) and subtract 1 from it"
                   + (f", keeping the constant factor \\({L(coeff)}\\)." if coeff != 1 else "."))
            if isinstance(n, sp.Rational) and not n.is_Integer:
                self.rule("Radicals as fractional powers")
        else:
            why = f"This is a standard derivative ({rule.lower()})."
        self.add("Differentiate", f"{self.D(e)} = {L(d)}", why, rule)

    def _sum(self, e, d) -> sp.Expr:
        terms = list(e.as_ordered_terms())
        self.add("Split into terms",
                 f"{self.D(e)} = " + " + ".join(self.D(t) for t in terms).replace("+ \\frac{d}{d" + L(self.x) + "}\\left[-", "- \\frac{d}{d" + L(self.x) + "}\\left["),
                 "By the sum and difference rule, the derivative of a sum is the sum of the derivatives, "
                 "so we handle each term on its own.",
                 "Sum and difference rule")
        simple_lines, results = [], []
        for t in terms:
            r = self.simple_rule(t)
            if r:
                dt = sp.diff(t, self.x)
                self.rule(r)
                if r == "Power rule" and t.as_independent(self.x, as_Add=False)[0] != 1:
                    self.rule("Constant multiple rule")
                simple_lines.append(f"{self.D(t)} &= {L(dt)} && \\text{{({r.lower()})}}")
                results.append(dt)
            else:
                if simple_lines:
                    self._flush_lines(simple_lines)
                    simple_lines = []
                results.append(self.explain(t))
        if simple_lines:
            self._flush_lines(simple_lines)
        combined = sp.Add(*results)
        self.add("Combine the results", f"{self.D(e)} = {L(combined)}",
                 "Add the derivatives of all the terms together.")
        return d

    def _flush_lines(self, lines: list[str]) -> None:
        body = " \\\\ ".join(lines)
        self.add("Differentiate each term",
                 f"\\begin{{aligned}} {body} \\end{{aligned}}",
                 "Each of these terms needs only one basic rule.")

    def _mul(self, e, d) -> sp.Expr:
        x = self.x
        coeff, rest = e.as_independent(x, as_Add=False)
        if coeff != 1:
            self.add("Pull out the constant",
                     f"{self.D(e)} = {L(coeff)}\\,{self.D(rest)}",
                     f"The constant \\({L(coeff)}\\) multiplies the whole expression, "
                     "so we keep it in front and differentiate the rest.",
                     "Constant multiple rule")
            inner = self.explain(rest)
            self.add("Multiply by the constant", f"{L(coeff)} \\cdot {P(best_simplification(inner))} = {L(best_simplification(d))}",
                     "Put the constant back in front of the derivative.")
            return d

        num, den = sp.fraction(e)
        if den.has(x) and num.has(x) and den != 1:
            return self._quotient(num, den, e, d)

        factors = list(e.args)
        u = factors[0]
        v = sp.Mul(*factors[1:])
        return self._product(u, v, e, d)

    @staticmethod
    def _using(rule: str) -> str:
        if rule == "Sum and difference rule":
            return "Differentiate term by term (sum rule with the power and constant rules)."
        if rule.endswith("derivatives"):
            return f"Using the standard {rule.lower()}."
        return f"Using the {rule.lower()}."

    def _derivative_of_part(self, part, name: str) -> sp.Expr:
        """u' or v': one line if simple, otherwise fully explained."""
        dp = sp.diff(part, self.x)
        r = self.inline_rule(part)
        if r:
            self.rule(r)
            self.add(f"Find {name}'", f"{name}' = {self.D(part)} = {L(dp)}",
                     self._using(r))
        else:
            self.add(f"Find {name}'", f"{name}' = {self.D(part)}",
                     f"\\({name}\\) is itself a combination of functions, so we work it out in its own steps.")
            self.explain(part)
            self.add(f"Result for {name}'", f"{name}' = {L(best_simplification(dp))}", "")
        return dp

    def _product(self, u, v, e, d) -> sp.Expr:
        self.add("Identify the product",
                 f"u = {L(u)}, \\qquad v = {L(v)}",
                 "The expression is a product of two functions of the variable, so we use the product rule "
                 "\\((uv)' = u'v + uv'\\).",
                 "Product rule")
        du = self._derivative_of_part(u, "u")
        dv = self._derivative_of_part(v, "v")
        self.add("Apply the product rule",
                 f"{self.D(e)} = {P(du)}\\cdot {P(v)} + {P(u)}\\cdot {P(dv)}",
                 "Substitute \\(u, u', v, v'\\) into \\(u'v + uv'\\).")
        self._simplify_step(du * v + u * dv, d)
        return d

    def _quotient(self, u, v, e, d) -> sp.Expr:
        self.add("Identify the quotient",
                 f"u = {L(u)}, \\qquad v = {L(v)}",
                 "The numerator and denominator both depend on the variable, so we use the quotient rule "
                 "\\(\\left(\\frac{u}{v}\\right)' = \\frac{u'v - uv'}{v^2}\\).",
                 "Quotient rule")
        du = self._derivative_of_part(u, "u")
        dv = self._derivative_of_part(v, "v")
        self.add("Apply the quotient rule",
                 f"{self.D(e)} = \\frac{{{P(du)}\\cdot {P(v)} - {P(u)}\\cdot {P(dv)}}}{{{P(v)}^{{2}}}}",
                 "Substitute \\(u, u', v, v'\\) into \\(\\frac{u'v - uv'}{v^2}\\). Watch the order in the numerator: "
                 "the minus sign makes it matter.")
        self._simplify_step((du * v - u * dv) / v**2, d)
        return d

    def _simplify_step(self, unsimplified, d) -> None:
        simple = best_simplification(d)
        expanded_view = sp.together(unsimplified)
        if L(simple) != L(unsimplified):
            self.add("Simplify", f"= {L(simple)}",
                     "Expand and collect like terms (or factor) to write the result more neatly.")
        del expanded_view

    def _chain(self, e, outer_of_u: sp.Expr, inner, d, outer_rule: str, outer_desc: str) -> sp.Expr:
        u = sp.Symbol("u", real=True) if e.has(sp.Abs) else sp.Symbol("u")
        outer_d = sp.diff(outer_of_u, u)
        inner_d = sp.diff(inner, self.x)
        self.add("Identify inner and outer functions",
                 f"u = {L(inner)}, \\qquad {self.D(e)} = \\frac{{d}}{{du}}\\left[{L(outer_of_u)}\\right]\\cdot \\frac{{du}}{{d{L(self.x)}}}",
                 f"This is a composite function: the outer function is {outer_desc} and the inner function is "
                 f"\\(u = {L(inner)}\\). The chain rule says: differentiate the outside (leaving the inside alone), "
                 "then multiply by the derivative of the inside.",
                 "Chain rule")
        self.rule(outer_rule)
        self.add("Differentiate the outer function",
                 f"\\frac{{d}}{{du}}\\left[{L(outer_of_u)}\\right] = {L(outer_d)} = {L(outer_d.subs(u, inner))}",
                 "Then put \\(u\\) back as the inner expression.")
        r = self.inline_rule(inner)
        if r:
            self.rule(r)
            self.add("Differentiate the inner function",
                     f"\\frac{{du}}{{d{L(self.x)}}} = {self.D(inner)} = {L(inner_d)}",
                     self._using(r))
        else:
            self.add("Differentiate the inner function",
                     f"\\frac{{du}}{{d{L(self.x)}}} = {self.D(inner)}",
                     "The inner function needs its own steps.")
            self.explain(inner)
        product = f"{P(outer_d.subs(u, inner))}\\cdot {P(best_simplification(inner_d))}"
        self.add("Multiply (chain rule)", f"{self.D(e)} = {product} = {L(best_simplification(d))}",
                 "Multiply the outer derivative by the inner derivative.")
        return d

    def _pow(self, e, d) -> sp.Expr:
        x = self.x
        base, ex = e.base, e.exp
        u = sp.Symbol("u")
        if not ex.has(x):
            if isinstance(ex, sp.Rational) and not ex.is_Integer:
                self.rule("Radicals as fractional powers")
                if ex.q in (2, 3):
                    self.add("Rewrite the radical",
                             f"{L(e)} = {P(base)}^{{{L(ex)}}}",
                             "Roots are fractional powers, which lets us use the power rule.")
            return self._chain(e, u**ex, base, d, "Power rule",
                               f"a power \\(u^{{{L(ex)}}}\\) (power rule)")
        if not base.has(x):
            if ex == x:
                self.add("Exponential rule", f"{self.D(e)} = {L(d)}",
                         "For a constant base \\(a\\): \\(\\frac{d}{dx}a^x = a^x \\ln a\\).", "Exponential rule")
                return d
            return self._chain(e, base**u, ex, d, "Exponential rule",
                               f"an exponential \\({L(base)}^u\\)")
        # f(x)^g(x): logarithmic differentiation
        y = sp.Symbol("y")
        g_lnf = ex * sp.log(base)
        self.add("Take ln of both sides",
                 f"y = {L(e)} \\;\\Rightarrow\\; \\ln y = {L(g_lnf)}",
                 "Both base and exponent contain the variable, so neither the power rule nor the exponential "
                 "rule applies directly. Taking ln turns the exponent into a product.",
                 "Logarithmic differentiation")
        self.add("Differentiate both sides",
                 f"\\frac{{1}}{{y}}\\frac{{dy}}{{d{L(x)}}} = {self.D(g_lnf)}",
                 "The left side uses the chain rule because y depends on the variable.")
        self.rule("Chain rule")
        inner = self.explain(g_lnf)
        self.add("Multiply by y", f"\\frac{{dy}}{{d{L(x)}}} = {L(e)}\\cdot {P(best_simplification(inner))}",
                 "Multiply both sides by \\(y\\) and substitute back the original expression.")
        del y
        return d

    def _chain_function(self, e, d) -> sp.Expr:
        u = sp.Symbol("u", real=True) if e.has(sp.Abs) else sp.Symbol("u")
        f = e.func
        inner = e.args[0]
        outer = f(u)
        name = {sp.exp: "the exponential \\(e^u\\)", sp.log: "the natural log \\(\\ln u\\)"}.get(
            f, f"\\({L(outer)}\\)")
        return self._chain(e, outer, inner, d, self._function_rule(e), name)


def explain_derivative(result: DerivativeResult) -> Explanation:
    if result.implicit:
        return _explain_implicit(result)
    x = result.variable
    b = StepBuilder(x)
    current = result.original
    for k in range(1, result.order + 1):
        if result.order > 1:
            label = {1: "first", 2: "second", 3: "third"}.get(k, f"{k}th")
            b.add(f"Find the {label} derivative",
                  f"{'f' + chr(39) * (k - 1) + '(' + L(x) + ')' if k > 1 else 'f(' + L(x) + ')'} = {L(current)}",
                  "Differentiate the previous result again." if k > 1 else
                  "Start by finding the first derivative.",
                  "Higher-order derivatives" if k > 1 else None)
        if k <= 3:
            b.explain(current, top=True)
        nxt = result.intermediate[k - 1]
        primes = "'" * k if k <= 3 else f"^{{({k})}}"
        if result.order > 1:
            b.add(f"Derivative #{k}", f"f{primes}({L(x)}) = {L(nxt)}", "")
        current = nxt
    return Explanation(b.rules, b.steps, {r: RULE_REASONS[r] for r in b.rules if r in RULE_REASONS})


def _implicit_latex(e, yf, x) -> str:
    """LaTeX that shows y(x) as y and y'(x) as dy/dx."""
    dy = sp.Symbol("zzDYDX")  # sorts after y so we print "2y dy/dx"
    s = tex(e.subs(sp.Derivative(yf, x), dy).subs(yf, sp.Symbol(str(yf.func))))
    return s.replace("zzDYDX", "\\frac{dy}{dx}")


def _explain_implicit(result: DerivativeResult) -> Explanation:
    x, y = result.variable, result.dependent
    lhs, rhs = result.equation
    b = StepBuilder(x)
    yf = sp.Function(str(y))(x)
    b.rule("Implicit differentiation")
    b.add("Differentiate both sides",
          f"\\frac{{d}}{{dx}}\\left[{L(lhs)}\\right] = \\frac{{d}}{{dx}}\\left[{L(rhs)}\\right]",
          f"\\({L(y)}\\) is not isolated, so we differentiate every term with respect to \\({L(x)}\\) "
          f"and remember that \\({L(y)}\\) is a function of \\({L(x)}\\).",
          "Implicit differentiation")
    lines = []
    uses_product = False
    for side in (lhs, rhs):
        for t in sp.Add.make_args(side):
            dt = sp.diff(t.subs(y, yf), x)
            note = ""
            if t.has(y) and t.has(x) and isinstance(t, sp.Mul):
                note, uses_product = "product rule", True
            elif t.has(y):
                note = "chain rule: multiply by dy/dx"
            elif t.has(x):
                note = "ordinary derivative"
            else:
                note = "constant"
            lines.append(f"\\frac{{d}}{{dx}}\\left[{L(t)}\\right] &= {_implicit_latex(dt, yf, x)} && \\text{{({note})}}")
    b.rule("Chain rule")
    if uses_product:
        b.rule("Product rule")
    b.add("Differentiate term by term",
          "\\begin{aligned} " + " \\\\ ".join(lines) + " \\end{aligned}",
          f"Whenever we differentiate something containing \\({L(y)}\\), the chain rule gives an extra factor "
          f"of \\(\\frac{{dy}}{{dx}}\\).")
    F = lhs - rhs
    Fx, Fy = sp.diff(F, x), sp.diff(F, y)
    b.add("Collect the dy/dx terms",
          f"{P(best_simplification(Fy))}\\,\\frac{{dy}}{{dx}} = {L(best_simplification(-Fx))}",
          "Move every term containing dy/dx to one side and everything else to the other side.")
    b.add("Solve for dy/dx",
          f"\\frac{{dy}}{{dx}} = {L(result.intermediate[0])}",
          "Divide both sides by the coefficient of dy/dx.")
    if result.order == 2:
        b.rule("Higher-order derivatives")
        b.add("Differentiate again",
              f"\\frac{{d^2y}}{{dx^2}} = \\frac{{d}}{{dx}}\\left[{L(result.intermediate[0])}\\right]",
              "Differentiate dy/dx with respect to x (quotient/chain rule, still treating y as a function of x), "
              "then substitute the expression for dy/dx found above.")
        b.add("Second derivative", f"\\frac{{d^2y}}{{dx^2}} = {L(result.derivative)}",
              "After substituting dy/dx and simplifying.")
        if result.on_curve_form is not None:
            b.add("Use the original equation", f"\\frac{{d^2y}}{{dx^2}} = {L(result.on_curve_form)}",
                  f"Replacing part of the numerator using \\({L(lhs)} = {L(rhs)}\\) gives a shorter form.")
    return Explanation(b.rules, b.steps, {r: RULE_REASONS[r] for r in b.rules if r in RULE_REASONS})
