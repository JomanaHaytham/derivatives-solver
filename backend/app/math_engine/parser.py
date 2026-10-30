"""Safe parsing of student-typed math into SymPy expressions.

SymPy's ``parse_expr`` ultimately evaluates Python code, so the raw text is
NEVER passed through untouched. Every input goes through three gates first:

1. a strict character whitelist (no quotes, underscores, brackets, ``;`` ...),
2. a word whitelist (only known function names, constants and short variable
   names are allowed; Python keywords and unknown words are rejected),
3. a restricted evaluation namespace with ``__builtins__`` removed.

Only after all three pass is the text handed to SymPy.
"""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass

import sympy as sp
from sympy.parsing.sympy_parser import (
    auto_number,
    auto_symbol,
    convert_xor,
    function_exponentiation,
    implicit_application,
    implicit_multiplication,
    parse_expr,
    split_symbols_custom,
)

MAX_EXPRESSION_LENGTH = 300


class ParseError(ValueError):
    """Raised when an expression cannot be parsed safely and reliably."""

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint


# Function names a student may type -> SymPy callable.
FUNCTIONS: dict[str, object] = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "cot": sp.cot, "sec": sp.sec, "csc": sp.csc,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "arcsin": sp.asin, "arccos": sp.acos, "arctan": sp.atan,
    "acot": sp.acot, "asec": sp.asec, "acsc": sp.acsc,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "exp": sp.exp, "log": sp.log, "ln": sp.log,
    "sqrt": sp.sqrt, "cbrt": lambda v: sp.Pow(v, sp.Rational(1, 3)),
    "abs": sp.Abs,
}

CONSTANTS: dict[str, object] = {"pi": sp.pi, "e": sp.E}

# Multi-letter variable names we accept as single symbols.
NAMED_SYMBOLS = {"theta", "alpha", "beta", "phi", "omega"}

_ALLOWED_CHARS = re.compile(r"^[0-9a-zA-Z\s+\-*/^().,=]*$")
_WORD = re.compile(r"[A-Za-z]+")


def normalize(text: str) -> str:
    """Turn common unicode / textbook notation into plain ASCII math."""
    replacements = {
        "−": "-", "–": "-", "—": "-", "×": "*", "·": "*", "⋅": "*",
        "÷": "/", "²": "^2", "³": "^3", "⁴": "^4", "π": " pi ", "θ": " theta ",
        "α": " alpha ", "β": " beta ", "φ": " phi ", "ω": " omega ", "√": "sqrt",
        "**": "^", "Abs(": "abs(", "{": "(", "}": ")", "[": "(", "]": ")",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # |x| -> abs(x) for the simple, unambiguous single-pair case.
    if text.count("|") == 2:
        text = re.sub(r"\|([^|]+)\|", r"abs(\1)", text)
    # sqrt3 / sqrt x without parentheses is handled by implicit application.
    return text.strip()


def _split_predicate(name: str) -> bool:
    """Allow 'xy' -> x*y, but never split function or constant names."""
    if name in FUNCTIONS or name in CONSTANTS or name in NAMED_SYMBOLS:
        return False
    return name.isalpha() and len(name) > 1


def _validate_words(text: str) -> None:
    for name in re.findall(r"\b([A-Za-z]{3,})\s*\(", text):
        if name.lower() not in FUNCTIONS:
            raise ParseError(
                f"'{name}' isn't a function I know.",
                hint="Supported: sin, cos, tan, sec, csc, cot, arcsin, arccos, arctan, sinh, cosh, tanh, exp, ln, log, sqrt, cbrt, abs.",
            )
    for word in _WORD.findall(text):
        low = word.lower()
        if low in FUNCTIONS or low in CONSTANTS or low in NAMED_SYMBOLS:
            continue
        if keyword.iskeyword(word) or keyword.iskeyword(low):
            raise ParseError(f"'{word}' is not valid in a math expression.")
        if len(word) == 1:
            continue
        # Short letter groups like 'xy' or '2ab' become products of variables.
        # Longer unknown words are almost certainly prose or typos.
        if len(word) <= 3 and not _looks_like_misspelled_function(low):
            continue
        raise ParseError(
            f"I don't recognise '{word}' as part of a math expression.",
            hint="Use standard function names such as sin, cos, tan, ln, log, exp, sqrt.",
        )


def _looks_like_misspelled_function(word: str) -> bool:
    # 'sinx', 'cosx' are handled by the caller's rewrite step; three-letter
    # groups like 'sim' or 'lgo' are suspicious only if they are near a
    # known name. Keep this simple: flag anything that starts with a known
    # function prefix but is not itself a function.
    return any(word.startswith(f) and word != f for f in ("sin", "cos", "tan", "log", "exp"))


def _rewrite_glued_functions(text: str) -> str:
    """'sinx' -> 'sin(x)', 'lnx' -> 'ln(x)', 'sin2x' -> 'sin(2x)'."""
    names = sorted(FUNCTIONS, key=len, reverse=True)
    alt = "|".join(names)
    glued = re.compile(r"\b(" + alt + r")(\d*[a-z])\b")
    text = glued.sub(lambda m: m.group(0) if m.group(0) in FUNCTIONS else f"{m.group(1)}({m.group(2)})", text)
    # 'sin x cos x' means sin(x)·cos(x), not sin(x·cos(x)): bind a function
    # written without parentheses to the single term right after it only.
    spaced = re.compile(r"\b(" + alt + r")\s+(\d*\.?\d*[a-z](?:\^\d+)?)(?![a-z(])")
    return spaced.sub(lambda m: f"{m.group(1)}({m.group(2)})", text)


def _namespace() -> dict:
    ns: dict = {
        "__builtins__": {},
        "Symbol": sp.Symbol,
        "Integer": sp.Integer,
        "Float": sp.Float,
        "Rational": sp.Rational,
        "Function": sp.Function,
    }
    ns.update(FUNCTIONS)
    ns.update(CONSTANTS)
    return ns


_TRANSFORMS = (
    auto_symbol,
    auto_number,
    convert_xor,
    split_symbols_custom(_split_predicate),
    implicit_multiplication,
    implicit_application,
    function_exponentiation,
)


@dataclass
class ParsedExpression:
    expr: sp.Expr
    source: str


def parse_math(text: str) -> sp.Expr:
    """Parse a single expression (no '=') safely. Raises ParseError."""
    raw = normalize(text)
    if not raw:
        raise ParseError("The expression is empty.")
    if len(raw) > MAX_EXPRESSION_LENGTH:
        raise ParseError("That expression is too long for me to handle reliably.")
    if not _ALLOWED_CHARS.match(raw):
        bad = sorted({c for c in raw if not _ALLOWED_CHARS.match(c)})
        raise ParseError(
            f"The expression contains characters I can't interpret: {' '.join(bad)}",
            hint="Use + - * / ^ and parentheses, e.g. (x^2 + 1)^5.",
        )
    if "=" in raw:
        raise ParseError("Unexpected '=' inside an expression.")
    if re.search(r"[+\-*/^.,]\s*$", raw) or re.match(r"^\s*[*/^,]", raw) or re.search(r"\(\s*\)", raw) \
            or re.search(r"[+\-*/^]\s*\)", raw) or re.search(r"[*/^]\s*[*/^+]", raw.replace("**", "^")):
        raise ParseError("The expression looks incomplete — an operator is missing something on one side.",
                         hint="Check the start and end of the expression, e.g. 'x^2 +' needs another term.")
    if raw.count("(") != raw.count(")"):
        raise ParseError("The parentheses are not balanced.", hint="Check that every '(' has a matching ')'.")

    # Students mix cases freely ("3X + x^2", "Sin(x)"), so letters are case-insensitive:
    # X and x are the same variable.
    raw = raw.lower()
    raw = _rewrite_glued_functions(raw)
    _validate_words(raw)
    try:
        expr = parse_expr(raw, local_dict={}, global_dict=_namespace(),
                          transformations=_TRANSFORMS, evaluate=True)
    except ParseError:
        raise
    except Exception as exc:  # SymPy raises many exception types
        raise ParseError(
            "I couldn't read that expression.",
            hint="Try writing it with explicit operators, e.g. x^2*sin(x) or (x^2+1)/(x-1).",
        ) from exc

    if not isinstance(expr, sp.Expr):
        raise ParseError("That doesn't look like a single mathematical expression.")
    if expr.has(sp.Abs):
        # |x| is only differentiable in the familiar way for real variables.
        expr = expr.subs({sym: sp.Symbol(sym.name, real=True) for sym in expr.free_symbols})
    if expr.has(sp.zoo, sp.nan) or expr.has(sp.oo):
        raise ParseError("The expression is undefined (it contains division by zero or infinity).")
    # Any undefined function application (e.g. 'g(x)') is ambiguous.
    undefined = [f for f in expr.atoms(sp.Function) if isinstance(f.func, sp.core.function.UndefinedFunction)]
    if undefined:
        names = ", ".join(sorted({str(f.func) for f in undefined}))
        raise ParseError(
            f"'{names}' isn't a function I know.",
            hint="If you meant multiplication, add a '*', e.g. a*(x+1).",
        )
    return expr


def parse_equation(text: str) -> tuple[sp.Expr, sp.Expr]:
    """Parse 'lhs = rhs' into two expressions."""
    parts = normalize(text).split("=")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise ParseError("An equation needs exactly one '=' with something on each side.")
    return parse_math(parts[0]), parse_math(parts[1])
