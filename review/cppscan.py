"""cppscan.py — the small amount of C++/CMake reading that review.py and testreview.py share.

Deliberately simple text analysis (no compiler needed, runs in seconds on any MR):
  * which test files a pricer declares   (xp_pricer(... TESTS a.cpp b.cpp ...))
  * TEST_CASE names, assertion counts, skip markers
  * floating-point matchers and their tolerances (WithinAbs / WithinRel / WithinULP / Approx)
  * whether a matcher's expected value is a GOLDEN number (literal-only after resolving
    `constexpr double kX = ...;` constants), as opposed to a value computed by the code under test
"""

from __future__ import annotations

import ast
import math
import re

# ---------------------------------------------------------------- CMake: declared tests
_CMAKE_COMMENT = re.compile(r"#.*$", re.MULTILINE)
_XP_PRICER = re.compile(r"\bxp_pricer\s*\((.*?)\)", re.DOTALL | re.IGNORECASE)
_KEYWORDS = {"NAME", "SOURCES", "HEADERS", "TESTS", "USES"}


def pricer_tests(cmake_text: str) -> list[str]:
    """Test files listed after TESTS in the pricer's xp_pricer() call."""
    m = _XP_PRICER.search(_CMAKE_COMMENT.sub("", cmake_text))
    if not m:
        return []
    tests, in_tests = [], False
    for tok in m.group(1).split():
        if tok.upper() in _KEYWORDS:
            in_tests = tok.upper() == "TESTS"
        elif in_tests:
            tests.append(tok)
    return tests


# ---------------------------------------------------------------- C++ text helpers
def strip_cpp_comments(text: str) -> str:
    """Remove // and /* */ comments, keeping string literals (test names live in strings)."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i : j + 1])
            i = j + 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _split_args(text: str, start: int) -> tuple[list[str], int]:
    """Split the argument list beginning just after '(' at `start`; returns (args, end index)."""
    args, depth, cur, i = [], 0, [], start
    while i < len(text):
        c = text[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                args.append("".join(cur).strip())
                return args, i
            depth -= 1
        elif c == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    return args, i


TEST_CASE = re.compile(r'\b(?:TEST_CASE|SCENARIO)\s*\(\s*"((?:[^"\\]|\\.)*)"')
ASSERTION = re.compile(r"\b(?:REQUIRE|CHECK)(?:_[A-Z_]+)?\s*\(")
SKIP_MARKER = re.compile(r'\[!mayfail\]|\[!shouldfail\]|\[\.|"\.|\bSKIP\s*\(')
_CONST = re.compile(r"\b(?:static\s+)?(?:constexpr|const)\s+(?:double|float|long double|auto)\s+"
                    r"(\w+)\s*=\s*([^;]+);")  # fmt: skip
_MATCHER = re.compile(r"\b(WithinAbs|WithinRel|WithinULP|Approx)\s*\(")
_CHAIN = re.compile(r"\s*\.\s*(margin|epsilon)\s*\(")


def test_cases(text: str) -> list[str]:
    return TEST_CASE.findall(strip_cpp_comments(text))


def assertion_count(text: str) -> int:
    return len(ASSERTION.findall(strip_cpp_comments(text)))


def skip_marker_count(text: str) -> int:
    return len(SKIP_MARKER.findall(strip_cpp_comments(text)))


def constants(text: str) -> dict[str, str]:
    return {name: expr.strip() for name, expr in _CONST.findall(strip_cpp_comments(text))}


# ---------------------------------------------------------------- numbers
_MATH = {"sqrt": math.sqrt, "exp": math.exp, "log": math.log, "pow": math.pow, "fabs": abs}
_CONSTS = {"M_PI": math.pi, "M_E": math.e, "M_SQRT2": math.sqrt(2.0)}


def _normalise(expr: str, consts: dict[str, str], depth: int = 0) -> str:
    expr = re.sub(r"\bstd::", "", expr)
    expr = re.sub(r"(?<=[0-9.])[fFlL]\b", "", expr)  # 1.0f, 2.0L
    if depth < 5:
        for name, value in consts.items():
            expr = re.sub(rf"\b{re.escape(name)}\b", f"({_normalise(value, consts, depth + 1)})", expr)
    return expr


def evaluate(expr: str, consts: dict[str, str]) -> float | None:
    """Value of a literal-only expression (numbers, + - * /, sqrt/exp/log/pow, M_PI), else None."""
    src = _normalise(expr, consts)
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError:
        return None

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = ev(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = ev(node.left), ev(node.right)
            return {ast.Add: a + b, ast.Sub: a - b, ast.Mult: a * b,
                    ast.Div: a / b if b else math.inf}[type(node.op)]  # fmt: skip
        if isinstance(node, ast.Name) and node.id in _CONSTS:
            return _CONSTS[node.id]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in _MATH and not node.keywords):  # fmt: skip
            return float(_MATH[node.func.id](*[ev(a) for a in node.args]))
        raise ValueError(ast.dump(node))

    try:
        return ev(tree)
    except (ValueError, TypeError, OverflowError, ZeroDivisionError):
        return None


# ---------------------------------------------------------------- matchers
class Matcher:
    """One floating-point comparison: kind, expected expression, tolerance (None = default)."""

    def __init__(self, kind: str, expected: str, tolerance: float | None, golden: bool) -> None:
        self.kind, self.expected, self.tolerance, self.golden = kind, expected, tolerance, golden

    @property
    def key(self) -> str:
        return f"{self.kind}({re.sub(r'\s+', '', self.expected)})"


def matchers(text: str) -> list[Matcher]:
    src = strip_cpp_comments(text)
    consts = constants(src)
    found = []
    for m in _MATCHER.finditer(src):
        args, end = _split_args(src, m.end())
        if not args or not args[0]:
            continue
        kind, expected = m.group(1), args[0]
        tol_expr = args[1] if len(args) > 1 else None
        chain = _CHAIN.match(src, end + 1)
        if kind == "Approx" and chain:
            chained, _ = _split_args(src, chain.end())
            tol_expr = chained[0] if chained else None
        tolerance = evaluate(tol_expr, consts) if tol_expr else None
        found.append(Matcher(kind, expected, tolerance, evaluate(expected, consts) is not None))
    return found
