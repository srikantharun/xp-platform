#!/usr/bin/env python3
"""check_pricer_cmakelists.py — the allow-list guard for pricer build files (gap 3).

A pricer's CMakeLists.txt is the ONE build file a quant legitimately owns, so CODEOWNERS
cannot take it away from them. The missing FLAGS argument on xp_pricer() narrows the hole
but does not close it: a quant can still write, right after the call, in the SAME file,

    target_compile_options(black_scholes PRIVATE -fno-exceptions)
    set_target_properties(black_scholes PROPERTIES CXX_STANDARD 17)

Semgrep's deny-list catches -ffast-math and CMAKE_CXX_FLAGS but not those. A deny-list
cannot predict every bad flag. So this is an ALLOW-LIST: a pricers/*/CMakeLists.txt may
contain exactly one xp_pricer(...) call and comments/blank lines — nothing else. Anything
else fails CI.

Usage:
    check_pricer_cmakelists.py <file-or-glob> [more...]   # check given files
    check_pricer_cmakelists.py --selftest                 # run built-in ok/bad cases
Exit 0 = all clean, non-zero = at least one violation (or a failed selftest).
"""
from __future__ import annotations
import glob
import re
import sys

COMMENT = re.compile(r"#.*$")


def _strip(text: str) -> str:
    """Remove comments and whitespace, leaving only executable CMake tokens."""
    no_comments = "\n".join(COMMENT.sub("", line) for line in text.splitlines())
    return no_comments.strip()


def violations(text: str) -> list[str]:
    """Return a list of reasons the file is not a single bare xp_pricer() call."""
    body = _strip(text)
    if not body:
        return ["empty: expected exactly one xp_pricer(...) call"]
    # Must begin with xp_pricer( and the FIRST balanced (...) must consume the whole body.
    m = re.match(r"xp_pricer\s*\(", body)
    if not m:
        return [f"first statement is not xp_pricer(...): {body.splitlines()[0]!r}"]
    depth, end = 0, None
    for i, ch in enumerate(body):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        return ["unbalanced parentheses in xp_pricer(...)"]
    trailing = body[end + 1 :].strip()
    if trailing:
        # This is the gap-3 bypass: a second statement after the call.
        return [
            "extra content after the xp_pricer(...) call — only xp_pricer() and comments "
            f"are allowed here; found: {trailing.splitlines()[0]!r}"
        ]
    return []


def check_file(path: str) -> bool:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    errs = violations(text)
    if errs:
        print(f"FAIL {path}")
        for e in errs:
            print(f"     - {e}")
        return False
    print(f"ok   {path}")
    return True


OK_CASE = """\
# the only build declaration a quant writes
xp_pricer(
  NAME     black_scholes
  SOURCES  black_scholes.cpp
  TESTS    test_black_scholes.cpp
  USES     QuantLib::QuantLib
)
"""

BAD_CASE = """\
xp_pricer(NAME black_scholes SOURCES black_scholes.cpp)
target_compile_options(black_scholes PRIVATE -fno-exceptions)  # gap-3 bypass
"""


def selftest() -> int:
    ok = not violations(OK_CASE)
    bad = bool(violations(BAD_CASE))
    print(f"selftest: ok-case accepted={ok}  bad-case rejected={bad}")
    return 0 if (ok and bad) else 1


def main(argv: list[str]) -> int:
    if not argv or argv == ["--selftest"]:
        return selftest()
    files: list[str] = []
    for arg in argv:
        files.extend(sorted(glob.glob(arg, recursive=True)) or [arg])
    clean = all(check_file(f) for f in files)
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
