#!/usr/bin/env python3
"""testreview.py — rule-based review of the TESTS in a merge request (exit 88 on BLOCK).

    testreview.py --repo <generated-repo> --base <merge-base sha> [--report testreview-report.md]

Run by the `testreview` job of templates/review.yml from the PINNED xp-platform checkout, so an MR
cannot weaken the rules that review it. Four checks:

  testreview/code-needs-tests  a pricer's code changed but none of its test files did      BLOCK
  testreview/golden-value      a pricer has no test comparing against a fixed reference
                               number (BLOCK for pricers touched by the MR, WARN otherwise)
  testreview/no-weakening      vs the merge base: a test file or TEST_CASE removed, fewer
                               assertions, a tolerance widened, a skip/mayfail marker added  BLOCK
  testreview/quarantine        quarantine.txt: format, owner, issue URL, 14-day SLA, max 10
                               entries, every entry names an existing test                    BLOCK

Text analysis only (cppscan.py): seconds per MR, no build needed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cppscan  # noqa: E402
import quarantine_rules  # noqa: E402
from common import BLOCK, INFO, WARN, Finding, Git, print_findings, write_report  # noqa: E402

EXIT_BLOCK = 88
CHECKS = [
    ("testreview/code-needs-tests", "pricer code changed ⇒ its tests changed"),
    ("testreview/golden-value", "every pricer has a golden-value test"),
    ("testreview/no-weakening", "no removed tests, fewer assertions, wider tolerances or skips"),
    ("testreview/quarantine", "quarantine.txt owner + expiry + SLA"),
]
QUARANTINE = "quarantine.txt"


def pricers_at(git: Git, rev: str) -> dict[str, list[str]]:
    """{pricer name: [test file paths]} from pricers/<m>/CMakeLists.txt at a revision."""
    out = {}
    for path in git.files(rev):
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "pricers" and parts[2] == "CMakeLists.txt":
            tests = cppscan.pricer_tests(git.show(rev, path) or "")
            out[parts[1]] = [f"pricers/{parts[1]}/{t}" for t in tests]
    return out


def check_code_needs_tests(changed, head_pricers, base_pricers) -> list[Finding]:
    findings, touched = [], {}
    for _status, path in changed:
        parts = path.split("/")
        if len(parts) >= 3 and parts[0] == "pricers":
            touched.setdefault(parts[1], set()).add(path)
    for pricer, paths in sorted(touched.items()):
        if pricer not in head_pricers:
            continue  # pricer removed entirely: reported by no-weakening
        tests = set(head_pricers[pricer]) | set(base_pricers.get(pricer, []))
        code = {p for p in paths if p not in tests and not p.endswith((".md", ".txt"))
                or p.endswith("CMakeLists.txt")}  # fmt: skip
        if not head_pricers[pricer]:
            findings.append(Finding(CHECKS[0][0], BLOCK, f"pricers/{pricer}",
                                    "pricer declares no TESTS in xp_pricer()"))  # fmt: skip
        elif code and not (paths & tests):
            findings.append(Finding(CHECKS[0][0], BLOCK, f"pricers/{pricer}",
                f"code changed ({', '.join(sorted(Path(p).name for p in code))}) but no test file "
                f"changed — add or update a test in "
                f"{', '.join(Path(t).name for t in head_pricers[pricer])}"))  # fmt: skip
    return findings


def check_golden(git: Git, head_pricers, touched: set[str]) -> list[Finding]:
    findings = []
    for pricer, tests in sorted(head_pricers.items()):
        golden = [m for t in tests for m in cppscan.matchers(git.show("HEAD", t) or "") if m.golden]
        if golden:
            continue
        level = BLOCK if pricer in touched else WARN
        why = "touched by this MR" if level == BLOCK else "not touched by this MR — fix before its next change"
        findings.append(Finding(CHECKS[1][0], level, f"pricers/{pricer}",
            "no golden-value test: add a CHECK_THAT(x, WithinAbs(<reference number>, <tol>)) against a "
            f"closed form or independently computed value, tolerance stated next to it ({why})"))  # fmt: skip
    return findings


def check_no_weakening(git: Git, base: str, head_pricers, base_pricers) -> list[Finding]:
    cid, findings = CHECKS[2][0], []
    for pricer, base_tests in sorted(base_pricers.items()):
        if pricer not in head_pricers:
            findings.append(Finding(cid, WARN, f"pricers/{pricer}",
                                    "pricer removed with all its tests — confirm this is intended"))  # fmt: skip
            continue
        for test in base_tests:
            old, new = git.show(base, test), git.show("HEAD", test)
            if old is None:
                continue
            if new is None:
                findings.append(Finding(cid, BLOCK, test, "test file deleted"))
                continue
            removed = sorted(set(cppscan.test_cases(old)) - set(cppscan.test_cases(new)))
            for name in removed:
                findings.append(Finding(cid, BLOCK, test, f'TEST_CASE "{name}" removed (or renamed)'))
            a_old, a_new = cppscan.assertion_count(old), cppscan.assertion_count(new)
            if a_new < a_old:
                findings.append(Finding(cid, BLOCK, test, f"assertions dropped {a_old} → {a_new}"))
            s_old, s_new = cppscan.skip_marker_count(old), cppscan.skip_marker_count(new)
            if s_new > s_old:
                findings.append(Finding(cid, BLOCK, test,
                    "skip / [!mayfail] / [!shouldfail] / hidden-tag marker added — use quarantine.txt "
                    "(owner + expiry) instead"))  # fmt: skip
            old_tol = {m.key: m.tolerance for m in cppscan.matchers(old)}
            for m in cppscan.matchers(new):
                before = old_tol.get(m.key)
                if before is not None and m.tolerance is not None and m.tolerance > before:
                    findings.append(Finding(cid, BLOCK, test,
                        f"tolerance widened on {m.key}: {before:g} → {m.tolerance:g}"))  # fmt: skip
    return findings


def check_quarantine(git: Git, base: str, head_pricers, today: dt.date) -> list[Finding]:
    cid, findings = CHECKS[3][0], []
    text = git.show("HEAD", QUARANTINE)
    if text is None:
        return findings
    entries, errors = quarantine_rules.parse(text)
    errors += quarantine_rules.sla_errors(entries, today)
    known = {f"unit.{p}.{name}" for p, tests in head_pricers.items()
             for t in tests for name in cppscan.test_cases(git.show("HEAD", t) or "")}  # fmt: skip
    errors += [f"{e.name!r}: no such test (expected unit.<pricer>.<TEST_CASE name>)"
               for e in entries if e.name not in known]  # fmt: skip
    findings += [Finding(cid, BLOCK, QUARANTINE, e) for e in errors]
    before = {e.name for e in quarantine_rules.parse(git.show(base, QUARANTINE) or "")[0]}
    for e in entries:
        if e.name not in before:
            findings.append(Finding(cid, INFO, QUARANTINE,
                f"newly quarantined: {e.name!r} (owner {e.owner}, expires {e.expires}, {e.issue})"))  # fmt: skip
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--base", required=True, help="merge-base sha (CI_MERGE_REQUEST_DIFF_BASE_SHA)")
    ap.add_argument("--report", type=Path, default=Path("testreview-report.md"))
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    args = ap.parse_args(argv)

    git = Git(args.repo.resolve())
    try:
        changed = git.changed(args.base)
        head_pricers, base_pricers = pricers_at(git, "HEAD"), pricers_at(git, args.base)
    except RuntimeError as exc:
        print(f"testreview: infrastructure error: {exc}", file=sys.stderr)
        return 1
    touched = {p.split("/")[1] for _s, p in changed if p.startswith("pricers/") and p.count("/") >= 2}

    findings = (check_code_needs_tests(changed, head_pricers, base_pricers)
                + check_golden(git, head_pricers, touched)
                + check_no_weakening(git, args.base, head_pricers, base_pricers)
                + check_quarantine(git, args.base, head_pricers, args.today))  # fmt: skip
    context = (f"Base `{args.base[:12]}` → HEAD · {len(changed)} files changed · "
               f"pricers: {', '.join(sorted(head_pricers)) or 'none'}")
    write_report(args.report, "testreview", CHECKS, findings, context)
    print_findings("testreview", findings)
    return EXIT_BLOCK if any(f.level == BLOCK for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
