#!/usr/bin/env python3
"""pre-commit hook: every find_package() must be declared where its dependency comes from.

    python tools/hooks/check_find_package.py <CMake files...>

A package is accepted if it is
  * a vcpkg.json dependency (name normalised: QuantLib -> quantlib, Catch2 -> catch2), or
  * a Python build requirement in python/pyproject.toml (pybind11), or
  * provided by CMake / the toolchain itself (SYSTEM below).
Anything else means the build depends on something the repo does not declare -> fail.
Checks whole files, so it also covers find_package calls added before the hook existed.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIND_PACKAGE = re.compile(
    r"^\s*find_package\s*\(\s*([A-Za-z0-9_.+-]+)", re.MULTILINE | re.IGNORECASE
)
# Provided by CMake modules or the build host, never by vcpkg.
SYSTEM = {"python", "python3", "git", "threads", "pkgconfig", "openmp", "doxygen"}
# CMake package name -> vcpkg port, where lower-casing is not enough.
ALIASES: dict[str, str] = {}


def normalise(name: str) -> str:
    return ALIASES.get(name, name.lower().replace("_", "-"))


def declared() -> set[str]:
    manifest = json.loads((ROOT / "vcpkg.json").read_text())
    names = {d if isinstance(d, str) else d["name"] for d in manifest.get("dependencies", [])}
    for feature in manifest.get("features", {}).values():
        names |= {d if isinstance(d, str) else d["name"] for d in feature.get("dependencies", [])}
    py = ROOT / "python" / "pyproject.toml"  # optional: services from template/ may have none
    requires = tomllib.loads(py.read_text())["build-system"]["requires"] if py.is_file() else []
    names |= {re.split(r"[<>=!~;\[ ]", r, maxsplit=1)[0].lower() for r in requires}
    return names


def strip_comments(text: str) -> str:
    return re.sub(r"#.*", "", text)


def main(argv: list[str]) -> int:
    allowed = declared()
    failures = []
    for path in map(Path, argv):
        for name in FIND_PACKAGE.findall(strip_comments(path.read_text())):
            key = normalise(name)
            if key not in allowed and key not in SYSTEM:
                failures.append(
                    f"{path}: find_package({name}) has no entry in vcpkg.json (port '{key}')"
                )
    for failure in failures:
        print(failure, file=sys.stderr)
    if failures:
        print(
            "add the port to vcpkg.json (with version>=) or justify it in SYSTEM/ALIASES",
            file=sys.stderr,
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
