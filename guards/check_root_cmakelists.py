#!/usr/bin/env python3
"""check_root_cmakelists.py — guard 4d.

The generated repo's root CMakeLists.txt is platform-owned and must stay a thin wiring
file: it may contain only cmake_minimum_required, the module-path line, include(XpProject),
xp_project(...), and add_subdirectory(...) calls (plus comments). This is an allow-list, so
a quant cannot slip add_compile_options(-O0) / set(CMAKE_CXX_FLAGS ...) into it.

    check_root_cmakelists.py <generated-repo-dir>/CMakeLists.txt
Exit 0 = clean, non-zero = a disallowed statement was found.
"""
from __future__ import annotations
import re
import sys

COMMENT = re.compile(r"#.*$")
ALLOWED = [
    re.compile(r"^cmake_minimum_required\s*\("),
    re.compile(r"^list\s*\(\s*APPEND\s+CMAKE_MODULE_PATH\b"),
    re.compile(r"^include\s*\(\s*XpProject\s*\)"),
    re.compile(r"^xp_project\s*\("),
    re.compile(r"^add_subdirectory\s*\("),
]


def violations(text: str) -> list[str]:
    # join lines, drop comments, then split on ')' boundaries is fragile; instead scan
    # statement-leading lines (CMake statements here are single-line).
    out: list[str] = []
    for raw in text.splitlines():
        line = COMMENT.sub("", raw).strip()
        if not line:
            continue
        if not any(p.match(line) for p in ALLOWED):
            out.append(line)
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: check_root_cmakelists.py <path-to-root-CMakeLists.txt>", file=sys.stderr)
        return 2
    with open(argv[0], encoding="utf-8") as fh:
        bad = violations(fh.read())
    if bad:
        print(f"FAIL guard 4d — disallowed statements in root CMakeLists.txt ({argv[0]}):")
        for b in bad:
            print(f"     - {b}")
        print("     only cmake_minimum_required / CMAKE_MODULE_PATH / include(XpProject) /")
        print("     xp_project(...) / add_subdirectory(...) are allowed here.")
        return 1
    print(f"ok   guard 4d — root CMakeLists.txt is a thin platform-owned wiring file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
