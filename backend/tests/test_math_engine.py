"""Accuracy tests for parsing, intent detection, differentiation and verification."""

import pytest
import sympy as sp

from app.math_engine.differentiator import differentiate, differentiate_implicit, expressions_match
from app.math_engine.intent import Intent, classify
from app.math_engine.parser import ParseError, parse_equation, parse_math
from app.math_engine.practice import practice_problems
from app.math_engine.solver import ClarificationNeeded, format_solution_markdown, solve

x, y, t = sp.symbols("x y t")


# --- parser -----------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ("x^3 + 2x^2 - 5x + 7", x**3 + 2 * x**2 - 5 * x + 7),
    ("sin(x^2)", sp.sin(x**2)),
    ("x^2 sin(x)", x**2 * sp.sin(x)),
    ("sinx", sp.sin(x)),
    ("sin 2x", sp.sin(2 * x)),
    ("e^x", sp.exp(x)),
    ("ln(x)", sp.log(x)),
    ("sqrt(x^2+1)", sp.sqrt(x**2 + 1)),
    ("x^(1/3)", x**sp.Rational(1, 3)),
    ("sin^2(x)", sp.sin(x)**2),
    ("3e^(2x)", 3 * sp.exp(2 * x)),
    ("arctan(x)", sp.atan(x)),
    ("sinh(2x)", sp.sinh(2 * x)),
    ("x sin x cos x", x * sp.sin(x) * sp.cos(x)),
    ("sin x^2", sp.sin(x**2)),
    ("x²", x**2),
    ("2πx", 2 * sp.pi * x),
])
def test_parser_accepts_student_notation(text, expected):
    assert sp.simplify(parse_math(text) - expected) == 0


@pytest.mark.parametrize("text", [
    "__import__('os').system('ls')",
    "lambda: 1",
    "exec(1)",
    "eval(x)",
    "open(x)",
    "x; import os",
    "foo(x)",
    "hello world",
    "x^2 +",
    "(x+1",
    "",
    "x" * 400,
])
def test_parser_rejects_unsafe_or_broken_input(text):
    with pytest.raises(ParseError):
        parse_math(text)


def test_absolute_value_uses_real_variable():
    e = parse_math("|x|")
    assert str(e) == "Abs(x)" and next(iter(e.free_symbols)).is_real
    r = differentiate(e, next(iter(e.free_symbols)))
    assert str(r.derivative) == "sign(x)" and r.verification.verified


def test_capital_letters_mean_the_same_variable():
    assert parse_math("3X + x^2") == 3 * x + x**2
    assert parse_math("Sin(X)") == sp.sin(x)
    sol = solve(classify("differentiate 3X + x^2").request)
    assert sol.result.derivative == 2 * x + 3 and not sol.assumptions


def test_equation_parsing():
    lhs, rhs = parse_equation("x^2 + y^2 = 25")
    assert lhs == x**2 + y**2 and rhs == 25


# --- intent -----------------------------------------------------------------
@pytest.mark.parametrize("text, expr, var, order", [
    ("Find the derivative of f(x) = x^3 + 2x^2 - 5x + 7.", "x^3 + 2x^2 - 5x + 7", "x", 1),
    ("d/dx (x^2 + 3x)", "(x^2 + 3x)", "x", 1),
    ("Differentiate sin(x^2)", "sin(x^2)", None, 1),
    ("Find the derivative of (x^2 + 1)^5", "(x^2 + 1)^5", None, 1),
    ("Differentiate x^2 sin(x)", "x^2 sin(x)", None, 1),
    ("Find the second derivative of x^4 - 3x", "x^4 - 3x", None, 2),
    ("d^2/dx^2 (sin x)", "(sin x)", "x", 2),
    ("Differentiate t^3 + 2t with respect to t", "t^3 + 2t", "t", 1),
    ("f''(x) for f(x)=x^5", "x^5", "x", 2),
])
def test_problem_intent(text, expr, var, order):
    c = classify(text)
    assert c.intent is Intent.PROBLEM
    assert c.request.expression_text == expr
    assert c.request.variable == var
    assert c.request.order == order


@pytest.mark.parametrize("text", [
    "Why did you use the chain rule?",
    "Explain the second step in simpler words.",
    "Can you solve this using another method?",
    "Give me a similar problem to practice.",
    "What is the difference between the product rule and the chain rule?",
])
def test_follow_up_intent(text):
    assert classify(text).intent is Intent.FOLLOW_UP


def test_implicit_intent():
    c = classify("find dy/dx if x^2 + y^2 = 25")
    assert c.intent is Intent.PROBLEM and c.request.implicit


@pytest.mark.parametrize("text", ["integrate x^2", "find the limit of 1/x", "partial derivative of x*y"])
def test_out_of_scope(text):
    assert classify(text).intent is Intent.OUT_OF_SCOPE


# --- differentiation accuracy (one case per supported topic) ----------------
CASES = [
    ("7", 0),                                                      # constant rule
    ("x^5", 5 * x**4),                                             # power rule
    ("x^3 + 2x^2 - 5x + 7", 3 * x**2 + 4 * x - 5),                 # sum/difference
    ("x^2 sin(x)", 2 * x * sp.sin(x) + x**2 * sp.cos(x)),          # product rule
    ("(x^2+1)/(x-1)", (x**2 - 2 * x - 1) / (x - 1)**2),            # quotient rule
    ("(x^2 + 1)^5", 10 * x * (x**2 + 1)**4),                       # chain rule
    ("sin(x^2)", 2 * x * sp.cos(x**2)),                            # trig + chain
    ("tan(x)", sp.sec(x)**2),                                      # trig
    ("e^(3x)", 3 * sp.exp(3 * x)),                                 # exponential
    ("2^x", 2**x * sp.log(2)),                                     # exponential base a
    ("ln(x^2+1)", 2 * x / (x**2 + 1)),                             # logarithmic
    ("sqrt(x)", 1 / (2 * sp.sqrt(x))),                             # radical
    ("x^(2/3)", sp.Rational(2, 3) * x**sp.Rational(-1, 3)),        # fractional power
    ("sqrt(3x^2+1)", 3 * x / sp.sqrt(3 * x**2 + 1)),               # composite radical
    ("ln(sin(x))", sp.cot(x)),                                     # composite
    ("x^x", x**x * (sp.log(x) + 1)),                               # logarithmic differentiation
    ("arctan(2x)", 2 / (1 + 4 * x**2)),                            # inverse trig
]


@pytest.mark.parametrize("text, expected", CASES)
def test_first_derivatives_are_correct_and_verified(text, expected):
    r = differentiate(parse_math(text), x)
    assert sp.simplify(r.derivative - expected) == 0
    assert r.verification.verified


def test_higher_order():
    r = differentiate(parse_math("x^5"), x, 3)
    assert r.derivative == 60 * x**2 and r.verification.verified
    r = differentiate(parse_math("e^(2x) sin(x)"), x, 2)
    assert sp.simplify(r.derivative - sp.exp(2 * x) * (3 * sp.sin(x) + 4 * sp.cos(x))) == 0


def test_implicit_first_and_second():
    lhs, rhs = parse_equation("x^2 + y^2 = 25")
    r1 = differentiate_implicit(lhs, rhs, x, y, 1)
    assert sp.simplify(r1.derivative + x / y) == 0 and r1.verification.verified
    r2 = differentiate_implicit(lhs, rhs, x, y, 2)
    assert r2.verification.verified
    assert sp.simplify(r2.on_curve_form + 25 / y**3) == 0


def test_numeric_check_catches_a_wrong_answer():
    from app.math_engine.differentiator import numeric_derivative_check
    v = numeric_derivative_check(sp.sin(x**2), x, 1, sp.cos(x**2))  # missing the 2x factor
    assert not v.verified


def test_expressions_match():
    assert expressions_match(parse_math("2x cos(x^2)"), 2 * x * sp.cos(x**2), x)
    assert not expressions_match(parse_math("cos(x^2)"), 2 * x * sp.cos(x**2), x)
    assert expressions_match(parse_math("sec(x)^2"), 1 + sp.tan(x)**2, x)


# --- solver & formatting ----------------------------------------------------
def test_solution_markdown_has_required_sections():
    sol = solve(classify("Find the derivative of f(x) = x^3 + 2x^2 - 5x + 7").request)
    md = format_solution_markdown(sol)
    for heading in ("### Problem", "### Rules we'll use", "### Step-by-step solution",
                    "### Final answer", "### Verification"):
        assert heading in md
    assert "Power rule" in sol.explanation.rules
    assert "3 x^{2} + 4 x - 5" in md
    assert "Verified" in md


@pytest.mark.parametrize("text, rule", [
    ("Differentiate x^2 sin(x)", "Product rule"),
    ("Differentiate (x^2+1)/(x-1)", "Quotient rule"),
    ("Differentiate (x^2 + 1)^5", "Chain rule"),
    ("Differentiate sqrt(x^2+1)", "Radicals as fractional powers"),
    ("find dy/dx if x^2 + xy + y^2 = 7", "Implicit differentiation"),
    ("Differentiate x^x", "Logarithmic differentiation"),
])
def test_rule_identification(text, rule):
    assert rule in solve(classify(text).request).explanation.rules


def test_ambiguous_variable_asks_for_clarification():
    with pytest.raises(ClarificationNeeded):
        solve(classify("differentiate a b").request)


def test_other_letters_are_constants_with_x():
    sol = solve(classify("differentiate a x^2").request)
    assert sol.result.derivative == 2 * sp.Symbol("a") * x
    assert sol.assumptions


def test_practice_problems_are_solvable():
    for shown, plain in practice_problems(["Chain rule", "Product rule"], count=4, seed=1):
        c = classify(plain)
        assert c.intent is Intent.PROBLEM
        assert solve(c.request).verified
