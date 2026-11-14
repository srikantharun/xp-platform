#!/usr/bin/env python3
"""Run one CI step and map its failure to a stable exit code.

Used by .gitlab-ci.yml and templates/cpp-build.yml so the step logic lives in one place.
It is Python rather than shell so the Linux and Windows (MSVC) jobs run identical code.

    python tools/ci/run_step.py format
    python tools/ci/run_step.py lint    --preset ci-linux-clang
    python tools/ci/run_step.py build   --preset ci-linux-gcc
    python tools/ci/run_step.py test    --preset ci-linux-gcc   # writes build/<preset>/junit.xml
    python tools/ci/run_step.py package --preset ci-linux-gcc
    python tools/ci/run_step.py budget  --preset ci-linux-gcc   # vs .ci-baseline/<preset>.json

Exit codes (the contract documented in templates/cpp-build.yml):
    81 format   82 lint   83 build   84 test failures   85 zero tests discovered
    86 build budget exceeded (wall time / sccache hit rate regression, TU time, artifact size)
    1  infrastructure/usage error (missing tool, bad arguments, version mismatch)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

EXIT_CODES = {"format": 81, "lint": 82, "build": 83, "test": 84, "zero_tests": 85, "budget": 86}
EXIT_INFRA = 1

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))  # stdlib-only xptools modules, no install needed
CXX_GLOBS = ["*.cpp", "*.hpp", "*.h"]
PY_PATHS = [p for p in ("tools", "python") if (ROOT / p).is_dir()]  # template services: no python/
TIDY_DIRS = ("src/", "tools/", "tests/", "python/")


class StepError(Exception):
    """Raised with the exit code the step should terminate with."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print("$ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, check=False, **kwargs)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise StepError(EXIT_INFRA, f"required tool not found on PATH: {name}")
    return path


def configure_vcpkg_cache() -> None:
    """Derive VCPKG_BINARY_SOURCES from CI variables unless the runner already set it.

    XP_VCPKG_CACHE_DIR    project-local dir persisted by the GitLab cache
    XP_VCPKG_SHARED_CACHE optional runner-mounted shared volume (docs/caching.md)
    XP_VCPKG_CACHE_MODE   read | readwrite (pipeline rules set readwrite on protected refs)
    """
    if "VCPKG_BINARY_SOURCES" in os.environ:
        return
    mode = os.environ.get("XP_VCPKG_CACHE_MODE", "read")
    sources = ["clear"]
    for var in ("XP_VCPKG_CACHE_DIR", "XP_VCPKG_SHARED_CACHE"):
        path = os.environ.get(var)
        if path:
            Path(path).mkdir(parents=True, exist_ok=True)
            sources.append(f"files,{path},{mode}")
    if len(sources) > 1:
        os.environ["VCPKG_BINARY_SOURCES"] = ";".join(sources)
        print(f"VCPKG_BINARY_SOURCES={os.environ['VCPKG_BINARY_SOURCES']}", flush=True)


def tag_version() -> str | None:
    """X.Y.Z from a release tag pipeline (CI_COMMIT_TAG=vX.Y.Z), else None."""
    tag = os.environ.get("CI_COMMIT_TAG", "")
    return tag[1:] if tag.startswith("v") else None


def check_tag_matches_manifest(version: str) -> None:
    manifest = json.loads((ROOT / "vcpkg.json").read_text())["version-semver"]
    if manifest != version:
        raise StepError(
            EXIT_INFRA,
            f"tag v{version} does not match vcpkg.json version {manifest}; "
            "release with `xptools release` so they agree",
        )


def tracked_files(patterns: list[str]) -> list[str]:
    out = run(["git", "ls-files", "--", *patterns], capture_output=True, text=True)
    return [f for f in out.stdout.splitlines() if f]


# --------------------------------------------------------------------------- steps


def step_format(_: argparse.Namespace) -> None:
    clang_format = require_tool("clang-format")
    ruff = require_tool("ruff")
    failed = False
    cxx = tracked_files(CXX_GLOBS)
    if cxx and run([clang_format, "--dry-run", "--Werror", *cxx]).returncode != 0:
        failed = True
    if run([ruff, "format", "--check", *PY_PATHS]).returncode != 0:
        failed = True
    if failed:
        raise StepError(
            EXIT_CODES["format"], "formatting differs: run clang-format -i / ruff format"
        )


def step_lint(args: argparse.Namespace) -> None:
    clang_tidy = require_tool("clang-tidy")
    ruff = require_tool("ruff")
    code = EXIT_CODES["lint"]
    configure_vcpkg_cache()
    if run(["cmake", "--preset", args.preset]).returncode != 0:
        raise StepError(code, f"configure failed for preset {args.preset}")
    db_path = ROOT / "build" / args.preset / "compile_commands.json"
    units = sorted(
        {
            os.path.relpath(entry["file"], ROOT)
            for entry in json.loads(db_path.read_text())
            if os.path.relpath(entry["file"], ROOT).startswith(TIDY_DIRS)
        }
    )
    failed = False
    for unit in units:
        cmd = [clang_tidy, "--quiet", "-p", str(db_path.parent), "--warnings-as-errors=*", unit]
        if run(cmd).returncode != 0:
            failed = True
    if run([ruff, "check", *PY_PATHS]).returncode != 0:
        failed = True
    if failed:
        raise StepError(code, "lint findings (clang-tidy / ruff)")


def step_build(args: argparse.Namespace) -> None:
    code = EXIT_CODES["build"]
    configure_vcpkg_cache()
    cmd = ["cmake", "--preset", args.preset]
    version = tag_version()
    if version:
        check_tag_matches_manifest(version)
        cmd.append(f"-DXP_VERSION={version}")
    if run(cmd).returncode != 0:
        raise StepError(code, f"configure failed for preset {args.preset}")
    if shutil.which("sccache"):
        run(["sccache", "--zero-stats"], capture_output=True)
    started = time.monotonic()
    if run(["cmake", "--build", "--preset", args.preset]).returncode != 0:
        raise StepError(code, f"build failed for preset {args.preset}")
    write_metrics(args.preset, time.monotonic() - started)


def write_metrics(preset: str, wall_seconds: float) -> None:
    """build/<preset>/build-metrics.json: input for `xptools build-budget` regressions."""
    from xptools.cache_stats import sccache_stats  # noqa: PLC0415 - optional dependency path

    metrics = {
        "preset": preset,
        "wall_seconds": round(wall_seconds, 2),
        "sccache": sccache_stats(),
        "sha": os.environ.get("CI_COMMIT_SHA"),
    }
    path = ROOT / "build" / preset / "build-metrics.json"
    path.write_text(json.dumps(metrics, indent=2) + "\n")
    print(f"build metrics: {json.dumps(metrics)}", flush=True)


QUARANTINE_LABEL = "quarantine"  # tests/quarantine.txt via cmake/Quarantine.cmake


def count_tests(preset: str) -> int:
    """Tests the gate will run (quarantined ones excluded)."""
    cmd = ["ctest", "--preset", preset, "-LE", QUARANTINE_LABEL, "--show-only=json-v1"]
    out = run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        print(out.stderr, file=sys.stderr)
        return 0
    return len(json.loads(out.stdout).get("tests", []))


def step_test(args: argparse.Namespace) -> None:
    count = count_tests(args.preset)
    print(f"discovered {count} test(s) for preset {args.preset}", flush=True)
    if count == 0:
        raise StepError(EXIT_CODES["zero_tests"], "zero tests discovered: refusing to pass")
    # --output-junit is relative to the test directory: build/<preset>/junit.xml
    cmd = ["ctest", "--preset", args.preset, "-LE", QUARANTINE_LABEL, "--output-junit", "junit.xml"]
    if run(cmd).returncode != 0:
        raise StepError(EXIT_CODES["test"], "test failures (see junit.xml)")


def step_test_quarantined(args: argparse.Namespace) -> None:
    """Run quarantined tests for the record (junit-quarantine.xml); never fails the job."""
    cmd = ["ctest", "--preset", args.preset, "-L", QUARANTINE_LABEL,
           "--output-junit", "junit-quarantine.xml"]  # fmt: skip
    result = run(cmd)
    state = "all passed (consider un-quarantining)" if result.returncode == 0 else "still failing"
    print(f"quarantined tests: {state}; see tests/quarantine.txt for owners and expiry", flush=True)


def step_package(args: argparse.Namespace) -> None:
    step_build(args)
    if run(["cpack", "--preset", args.preset]).returncode != 0:
        raise StepError(EXIT_INFRA, f"cpack failed for preset {args.preset}")


def step_budget(args: argparse.Namespace) -> None:
    """Compare this build with the baseline; on protected refs also record it (XP_BUDGET_MODE)."""
    from xptools import build_budget  # noqa: PLC0415

    baseline = os.environ.get("XP_BUDGET_BASELINE", f".ci-baseline/{args.preset}.json")
    argv = ["--preset", args.preset, "--baseline", baseline]
    if os.environ.get("XP_BUDGET_MODE") == "record":
        argv.append("--record")
    if build_budget.main(argv) != 0:
        raise StepError(EXIT_CODES["budget"], "build budget exceeded (see report above)")


STEPS = {
    "format": step_format,
    "lint": step_lint,
    "build": step_build,
    "test": step_test,
    "test-quarantined": step_test_quarantined,
    "package": step_package,
    "budget": step_budget,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=sorted(STEPS))
    parser.add_argument("--preset", default="ci-linux-clang", help="CMake preset name")
    args = parser.parse_args(argv)
    try:
        STEPS[args.step](args)
    except StepError as err:
        print(f"::{args.step} failed (exit {err.code}): {err}", file=sys.stderr, flush=True)
        return err.code
    print(f"::{args.step} ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
