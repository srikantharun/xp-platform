#!/usr/bin/env python3
"""review.py — rule-based code review of a merge request (exit 87 on BLOCK).

    review.py --repo <generated-repo> --platform <pinned xp-platform checkout> --tag <platform tag>
              [--base <merge-base sha>] [--report review-report.md]

Run by the `review` job of ci/review.yml from the PINNED xp-platform checkout. Two checks:

  review/guards   the four ownership guards (guards/run_guards.sh, 4a–4d): pricer CMakeLists
                  allow-list, no build files outside platform/, platform/ == pinned tag,
                  thin root CMakeLists.txt                                            BLOCK
  review/semgrep  the platform's semgrep rules (semgrep/cpp-build.yml: fast-math, raw
                  CMAKE_CXX_FLAGS, -Wno-error, absolute paths, catch(...), ...) on the files
                  the MR changed outside platform/ (all files when --base is omitted).
                  Rule severity ERROR = BLOCK, WARNING = WARN, INFO = INFO.

Every finding comes from a versioned rule in xp-platform, so a result is reproducible from the
platform tag alone.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BLOCK, INFO, WARN, Finding, Git, print_findings, write_report  # noqa: E402

EXIT_BLOCK = 87
CHECKS = [
    ("review/guards", "ownership guards 4a–4d"),
    ("review/semgrep", "build-hygiene + C++ house rules"),
]
SEVERITY = {"ERROR": BLOCK, "WARNING": WARN, "INFO": INFO}
SKIP_PREFIXES = ("platform/", "build/")


def check_guards(repo: Path, platform: Path, tag: str) -> list[Finding]:
    proc = subprocess.run(
        ["bash", str(platform / "guards" / "run_guards.sh"), str(repo), str(platform), tag],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    print(proc.stdout, end="")
    findings = []
    for line in proc.stdout.splitlines():
        if line.startswith("FAIL"):
            findings.append(Finding(CHECKS[0][0], BLOCK, "guards", line[4:].strip(" —")))
        elif line.startswith("     ") and findings:  # continuation lines of the last FAIL
            findings[-1].message += f" · {line.strip()}"
    if proc.returncode != 0 and not findings:
        findings.append(Finding(CHECKS[0][0], BLOCK, "guards",
                                f"run_guards.sh exited {proc.returncode}: {proc.stderr.strip()}"))  # fmt: skip
    return findings


def check_semgrep(repo: Path, platform: Path, targets: list[str]) -> list[Finding]:
    if not targets:
        return [Finding(CHECKS[1][0], INFO, "-", "no changed files outside platform/ to scan")]
    semgrep = shutil.which("semgrep")
    if not semgrep:
        raise RuntimeError("semgrep not found on PATH (use the component's review image)")
    proc = subprocess.run(
        [semgrep, "scan", "--config", str(platform / "semgrep" / "cpp-build.yml"), "--json",
         "--metrics=off", "--disable-version-check", "--quiet", *targets],
        cwd=repo, capture_output=True, text=True, check=False,
    )  # fmt: skip
    try:
        results = json.loads(proc.stdout)["results"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError(f"semgrep failed ({proc.returncode}): {proc.stderr.strip()[:400]}") from exc
    return [
        Finding(CHECKS[1][0], SEVERITY.get(r["extra"]["severity"], WARN),
                f"{r['path']}:{r['start']['line']}",
                f"[{r['check_id'].rsplit('.', 1)[-1]}] {' '.join(r['extra']['message'].split())}")
        for r in results
    ]  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--platform", type=Path, required=True, help="pinned xp-platform checkout")
    ap.add_argument("--tag", required=True, help="platform tag the repo is pinned to")
    ap.add_argument("--base", help="merge-base sha; omit to scan every file")
    ap.add_argument("--report", type=Path, default=Path("review-report.md"))
    args = ap.parse_args(argv)
    repo, platform = args.repo.resolve(), args.platform.resolve()

    git = Git(repo)
    try:
        if args.base:
            targets = [p for s, p in git.changed(args.base) if s != "D"]
        else:
            targets = git.files("HEAD")
        targets = [p for p in targets if not p.startswith(SKIP_PREFIXES)]
        findings = check_guards(repo, platform, args.tag) + check_semgrep(repo, platform, targets)
    except RuntimeError as exc:
        print(f"review: infrastructure error: {exc}", file=sys.stderr)
        return 1
    scope = f"base `{args.base[:12]}` → HEAD" if args.base else "all files"
    context = f"Platform `{args.tag}` (pinned checkout) · {scope} · {len(targets)} files scanned"
    write_report(args.report, "review", CHECKS, findings, context)
    print_findings("review", findings)
    return EXIT_BLOCK if any(f.level == BLOCK for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
