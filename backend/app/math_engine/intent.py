"""Work out what the student is asking for.

Turns free text such as "Find the second derivative of x^3 sin x" or
"find dy/dx if x^2 + y^2 = 25" into a structured :class:`ProblemRequest`.
Nothing here evaluates math; it only slices the text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Intent(str, Enum):
    PROBLEM = "problem"            # a new derivative to compute
    FOLLOW_UP = "follow_up"        # a question about the conversation
    OUT_OF_SCOPE = "out_of_scope"  # integrals, limits, ...


@dataclass
class ProblemRequest:
    expression_text: str
    variable: str | None = None          # None = infer from the expression
    order: int = 1
    implicit: bool = False               # explicit "implicit" keyword or equation in x and y
    refers_to_previous: bool = False     # "second derivative of it"
    function_name: str | None = None     # f in "f(x) = ..."
    notes: list[str] = field(default_factory=list)


@dataclass
class Classification:
    intent: Intent
    request: ProblemRequest | None = None
    topic: str | None = None             # for out-of-scope messages


_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
}

_OUT_OF_SCOPE = [
    (r"\bintegra(l|te|tion)\b|\banti-?derivative\b|∫", "integration"),
    (r"\blimit\b|\blim\b", "limits"),
    (r"\bpartial\b|∂", "partial derivatives"),
    (r"\b(taylor|maclaurin|series)\b", "series expansions"),
    (r"\bmatri(x|ces)\b|\bdeterminant\b", "linear algebra"),
    (r"\bdifferential equation\b|\bode\b", "differential equations"),
]

# Phrases that announce a differentiation problem.
_TRIGGERS = re.compile(
    r"(differentiate|derivative|derive|d\s*/\s*d[a-z]|d\^?\d*\s*/\s*d[a-z]\^?\d*|d[²³]|"
    r"\bd[a-z]\s*/\s*d[a-z]\b|\b[a-z]\s*'+\s*\(|\b[a-z]'+\b|\bdiff\b)",
    re.IGNORECASE,
)

_PRONOUNS = re.compile(
    r"^(it|this|that|this function|that function|the same function|the function|"
    r"the result|the answer|the derivative|its derivative|this one|that one|again)$",
    re.IGNORECASE,
)

# Leading phrases stripped to leave only the math.
_LEADING = [
    r"^(please\s+)?(can you\s+|could you\s+)?(help me\s+)?",
    r"^(find|compute|calculate|determine|evaluate|get|give me|show me|what is|what's|whats|solve)\s+",
    r"^(the\s+)?(\w+\s+)?(order\s+)?derivative(s)?\s+(of|for)\s+",
    r"^(the\s+)?(\w+\s+)?(order\s+)?derivative\s*",
    r"^differentiate\s+",
    r"^diff\s+",
    r"^implicitly\s+",
    r"^d\^?\d*\s*[a-z]?\s*/\s*d[a-z]\^?\d*\s*(of\s+)?",
    r"^d[²³]\s*[a-z]?\s*/\s*d[a-z][²³]\s*(of\s+)?",
    r"^[a-z]'+\s*\(\s*[a-z]\s*\)\s*(for|if|of|when|given|where)?\s*",
    r"^(for|of|if|given|when|where)\s+",
]

_TRAILING = [
    r"\s*(with respect to|w\.?\s*r\.?\s*t\.?|wrt)\s+[a-z]\s*$",
    r"\s*(using|by|with)\s+(the\s+)?[a-z\- ]+(rule|differentiation|method)\s*$",
    r"\s*implicitly\s*$",
    r"\s*(step by step|step-by-step)\s*$",
    r"\s*please\s*$",
]


def _detect_order(text: str) -> int:
    t = text.lower()
    m = re.search(r"\b(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)[\s-]+(order\s+)?derivative", t)
    if m:
        return _ORDINALS[m.group(1)]
    m = re.search(r"\b(\d+)(st|nd|rd|th)[\s-]+(order\s+)?derivative", t)
    if m:
        return int(m.group(1))
    m = re.search(r"d\^(\d+)\s*[a-z]?\s*/\s*d[a-z]\^\1", t) or re.search(r"d(\d)\s*[a-z]\s*/\s*d[a-z]\1", t)
    if m:
        return int(m.group(1))
    if re.search(r"d²", t):
        return 2
    if re.search(r"d³", t):
        return 3
    m = re.search(r"\b[a-z]('+)\s*\(", t) or re.search(r"\b[a-z]('+)(?=\s|$|\W)", t)
    if m:
        return len(m.group(1))
    return 1


def _detect_variable(text: str) -> str | None:
    t = text.lower()
    m = re.search(r"(with respect to|w\.?\s*r\.?\s*t\.?|wrt)\s+([a-z])\b", t)
    if m:
        return m.group(2)
    m = re.search(r"d\^?\d*\s*[a-z]?\s*/\s*d([a-z])", t) or re.search(r"d[²³][a-z]?/d([a-z])", t)
    if m:
        return m.group(1)
    m = re.search(r"\b[a-z]'+\s*\(\s*([a-z])\s*\)", t)
    if m:
        return m.group(1)
    return None


def _strip_phrases(text: str) -> str:
    s = text.strip().rstrip(".?!").strip()
    s = re.sub(r"\s+", " ", s)
    for pattern in _TRAILING:
        s = re.sub(pattern, "", s, flags=re.IGNORECASE)
    changed = True
    while changed:
        changed = False
        for pattern in _LEADING:
            new = re.sub(pattern, "", s, count=1, flags=re.IGNORECASE)
            if new != s:
                s, changed = new.strip(), True
    s = s.strip().rstrip(".?!:").strip()
    s = re.sub(r"^:\s*", "", s)
    return s


def classify(text: str) -> Classification:
    raw = text.strip()
    lower = raw.lower()

    for pattern, topic in _OUT_OF_SCOPE:
        if re.search(pattern, lower):
            return Classification(Intent.OUT_OF_SCOPE, topic=topic)

    has_trigger = bool(_TRIGGERS.search(raw))
    order = _detect_order(raw)
    variable = _detect_variable(raw)
    implicit_word = "implicit" in lower

    body = _strip_phrases(raw)
    body = re.sub(r"\b(using|by)\s+implicit\s+differentiation\b", "", body, flags=re.IGNORECASE).strip()

    if has_trigger and _PRONOUNS.match(body or "it"):
        return Classification(Intent.PROBLEM, ProblemRequest(
            expression_text="", variable=variable, order=order, refers_to_previous=True))

    looks_math = _looks_like_math(body)
    if not looks_math:
        # "Why did you use the chain rule?", "give me a similar problem" ...
        return Classification(Intent.FOLLOW_UP)
    if not has_trigger and _is_question_prose(raw):
        return Classification(Intent.FOLLOW_UP)

    function_name = None
    implicit = implicit_word
    expression_text = body
    if "=" in body:
        lhs, _, rhs = body.partition("=")
        lhs = lhs.strip()
        m = re.fullmatch(r"([a-zA-Z])\s*\(\s*([a-z])\s*\)", lhs)
        if m and "=" not in rhs:
            function_name, variable = m.group(1), variable or m.group(2)
            expression_text = rhs.strip()
        elif re.fullmatch(r"y", lhs) and "y" not in rhs and not implicit_word:
            function_name = "y"
            expression_text = rhs.strip()
        else:
            implicit = True

    return Classification(Intent.PROBLEM, ProblemRequest(
        expression_text=expression_text, variable=variable, order=order,
        implicit=implicit, function_name=function_name))


def _looks_like_math(s: str) -> bool:
    if not s:
        return False
    if re.search(r"[\d^*/+=()]|\b(sin|cos|tan|sec|csc|cot|ln|log|exp|sqrt|e)\b", s):
        return True
    return bool(re.fullmatch(r"([a-z]\s*){1,4}", s.strip()))


def _is_question_prose(s: str) -> bool:
    words = re.findall(r"[A-Za-z]{4,}", s)
    known = {"sqrt", "cbrt", "theta", "alpha", "omega", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh"}
    return len([w for w in words if w.lower() not in known]) >= 2
