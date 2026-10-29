"""Follow-up answers that work without any AI model.

Covers the most common questions with curated explanations so the app stays
useful when no API key is configured. Anything else gets an honest message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..math_engine.practice import practice_problems
from ..math_engine.solver import inline_math
from ..math_engine.steps import RULE_REASONS

RULE_GUIDES: dict[str, str] = {
    "chain": """**The chain rule** is for a *function inside another function*, like $\\sin(x^2)$ or $(3x+1)^5$.

$$ \\frac{d}{dx}\\, f\\big(g(x)\\big) = f'\\big(g(x)\\big)\\cdot g'(x) $$

Think of peeling an onion: differentiate the **outer** layer while leaving the inside untouched, then multiply by the derivative of the **inner** layer.

*Example:* $\\frac{d}{dx}\\sin(x^2) = \\cos(x^2)\\cdot 2x$.

**How to spot it:** if you would need to compute something first (the inside) before applying a function to it, you need the chain rule.""",
    "product": """**The product rule** is for *two functions multiplied together*, like $x^2\\sin x$.

$$ (uv)' = u'v + uv' $$

In words: derivative of the first times the second, **plus** the first times the derivative of the second.

*Example:* $\\frac{d}{dx}\\big[x^2\\sin x\\big] = 2x\\sin x + x^2\\cos x$.

A common mistake is writing $(uv)' = u'v'$ — that is **not** true (try it with $u = v = x$).""",
    "quotient": """**The quotient rule** is for *one function divided by another*, like $\\frac{x^2+1}{x-1}$.

$$ \\left(\\frac{u}{v}\\right)' = \\frac{u'v - uv'}{v^2} $$

A memory trick: *"low d-high minus high d-low, over the square of what's below."* The order in the numerator matters because of the minus sign.

If the numerator is just a constant, it is often easier to rewrite $\\frac{c}{v} = c\\,v^{-1}$ and use the chain rule.""",
    "power": """**The power rule** handles a variable raised to a constant power:

$$ \\frac{d}{dx}x^n = n\\,x^{n-1} $$

Bring the exponent down in front and subtract one from it. It works for negative and fractional exponents too, so first rewrite roots and fractions: $\\sqrt{x} = x^{1/2}$, $\\frac{1}{x^3} = x^{-3}$.""",
    "implicit": """**Implicit differentiation** is used when $y$ is mixed into an equation, like $x^2 + y^2 = 25$, instead of being written as $y = \\dots$.

1. Differentiate **both sides** with respect to $x$.
2. Every time you differentiate a term containing $y$, multiply by $\\frac{dy}{dx}$ (that's the chain rule, because $y$ depends on $x$).
3. Collect the $\\frac{dy}{dx}$ terms on one side and solve for $\\frac{dy}{dx}$.

*Example:* $2x + 2y\\frac{dy}{dx} = 0 \\Rightarrow \\frac{dy}{dx} = -\\frac{x}{y}$.""",
    "product_vs_chain": """**Product rule vs. chain rule** — the question is *how* the two functions are combined.

| | Product rule | Chain rule |
|---|---|---|
| Shape | $f(x)\\cdot g(x)$ — side by side, **multiplied** | $f(g(x))$ — one **inside** the other |
| Example | $x^2 \\sin x$ | $\\sin(x^2)$ |
| Formula | $f'g + fg'$ | $f'(g(x))\\cdot g'(x)$ |
| Result for the example | $2x\\sin x + x^2\\cos x$ | $2x\\cos(x^2)$ |

Quick test: can you compute the two parts **separately** and then multiply? → product rule. Do you have to compute one part **first** and feed it into the other? → chain rule. Many problems need both.""",
}


def _match_guide(text: str) -> str | None:
    t = text.lower()
    if ("product" in t and "chain" in t) and re.search(r"differ|vs|versus|compare|between", t):
        return RULE_GUIDES["product_vs_chain"]
    for key in ("chain", "product", "quotient", "implicit", "power"):
        if key in t:
            return RULE_GUIDES[key]
    return None


@dataclass
class OfflineReply:
    markdown: str
    practice: list[str] = field(default_factory=list)


def offline_followup(message: str, context: dict | None) -> OfflineReply:
    reply = _offline(message, context)
    return reply if isinstance(reply, OfflineReply) else OfflineReply(reply)


def _offline(message: str, context: dict | None) -> "str | OfflineReply":
    t = message.lower()

    if re.search(r"similar|practice|another (problem|example|question)|more (problems|examples)|exercise", t):
        rules = (context or {}).get("rules") or []
        problems = practice_problems(rules, count=3, exclude=(context or {}).get("original"))
        lines = ["Here are some practice problems using the same ideas:" if rules else
                 "Here are some practice problems to try:", ""]
        for i, (shown, _plain) in enumerate(problems, 1):
            lines.append(f"{i}. {shown}")
        lines += ["", "Try them on paper first, then send me any of them and I'll show the verified step-by-step solution."]
        return OfflineReply("\n".join(lines), [plain for _shown, plain in problems])

    guide = _match_guide(t)
    if guide:
        return guide + (_in_your_problem(context) if context and re.search(r"\bwhy\b", t) else "")

    main = _main_rule_key(context)

    if context and re.search(r"\bwhy\b|this rule|which rule|what rule", t):
        intro = ("Here's why these rules fit your problem" if main is None else
                 "Here's the key rule in your problem and why it fits")
        body = RULE_GUIDES[main] if main else ""
        return f"{intro}:\n\n{body}{_in_your_problem(context)}".replace(":\n\n\n\n", ":\n\n")

    if context and re.search(r"another (method|way)|different (method|way)|other (method|way)|alternative", t):
        return _another_method(context)

    if context and re.search(r"simpl|easier|don.?t understand|confus|explain|step", t):
        rules = context.get("rules") or []
        reasons = "\n".join(f"- **{r}** — {inline_math(RULE_REASONS[r])}" for r in rules if r in RULE_REASONS)
        tail = ("\n\n" + RULE_GUIDES[main]) if main else ""
        return ("Let's go through the idea in plain words. These are the tools the solution used:\n\n" + reasons +
                tail + "\n\nTip: cover the solution, redo it on paper one step at a time, and compare after "
                "each step. If a specific step still feels unclear, ask me about that rule by name "
                "(for example *\"explain the chain rule\"*).")

    return ("I can solve any derivative you send me, step by step — for example *Differentiate x^2 sin(x)*.\n\n"
            "You can also ask me to explain the **chain**, **product**, **quotient**, **power** or **implicit** "
            "rules, compare two rules (*\"difference between the product rule and the chain rule\"*), or give you "
            "**practice problems**.")


_RULE_KEYS = [("Implicit differentiation", "implicit"), ("Quotient rule", "quotient"),
              ("Product rule", "product"), ("Chain rule", "chain"), ("Power rule", "power")]


def _main_rule_key(context: dict | None) -> str | None:
    rules = (context or {}).get("rules") or []
    return next((key for name, key in _RULE_KEYS if name in rules), None)


def _in_your_problem(context: dict | None) -> str:
    if not context:
        return ""
    rules = context.get("rules") or []
    reasons = [f"- **{r}**: {inline_math(RULE_REASONS[r])}" for r in rules if r in RULE_REASONS]
    if not reasons:
        return ""
    return "\n\n**In your problem** $" + str(context.get("original_latex")) + "$:\n" + "\n".join(reasons)


def _another_method(context: dict) -> str:
    rules = context.get("rules") or []
    ideas = []
    if "Quotient rule" in rules:
        ideas.append("Rewrite the fraction as a product, $\\frac{u}{v} = u\\cdot v^{-1}$, then use the "
                     "**product rule** together with the **chain rule** on $v^{-1}$. You should get the same answer.")
    if "Chain rule" in rules:
        ideas.append("If the inside is a small polynomial raised to a power, you can **expand it first** and then "
                     "use only the power rule — slower, but a good way to check the chain rule.")
    if "Product rule" in rules:
        ideas.append("If both factors are polynomials, **multiply them out first** and differentiate term by term.")
    if "Implicit differentiation" in rules:
        ideas.append("If you can, **solve the equation for y** first and differentiate directly, then compare "
                     "with the implicit result.")
    if "Logarithmic differentiation" in rules or not ideas:
        ideas.append("Take $\\ln$ of both sides and differentiate (**logarithmic differentiation**) — it turns "
                     "products and powers into sums.")
    lines = "\n".join(f"{i}. {idea}" for i, idea in enumerate(ideas, 1))
    return ("Here are other ways to reach the same derivative:\n\n" + lines +
            "\n\nWhichever way you choose, the result must simplify to the verified answer:\n\n$$\n"
            + str(context.get("answer_latex")) + "\n$$")
