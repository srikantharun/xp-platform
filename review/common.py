"""common.py — findings, the Markdown report and git access shared by review.py / testreview.py."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

BLOCK, WARN, INFO = "BLOCK", "WARN", "INFO"
_ICON = {BLOCK: "❌", WARN: "⚠️", INFO: "ℹ️"}


@dataclass
class Finding:
    check: str  # stable id, e.g. testreview/code-needs-tests
    level: str  # BLOCK fails the job; WARN / INFO are reported only
    where: str  # file or pricer
    message: str


class Git:
    """Read-only git access to the MR checkout. safe.directory=* because CI images run as a
    different uid from the one that owns the checkout."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo

    def run(self, *args: str, check: bool = True) -> str:
        proc = subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", str(self.repo), *args],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        if check and proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)}: {proc.stderr.strip()}")
        return proc.stdout

    def show(self, rev: str, path: str) -> str | None:
        """File content at a revision, or None if it does not exist there."""
        proc = subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", str(self.repo), "show", f"{rev}:{path}"],
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        return proc.stdout if proc.returncode == 0 else None

    def files(self, rev: str) -> list[str]:
        return self.run("ls-tree", "-r", "--name-only", rev).splitlines()

    def changed(self, base: str, head: str = "HEAD") -> list[tuple[str, str]]:
        """(status letter, path) for every file that differs; renames count as delete + add."""
        out = self.run("diff", "--name-status", "--no-renames", base, head)
        return [(line[0], line.split("\t", 1)[1]) for line in out.splitlines() if "\t" in line]


def write_report(path: Path, title: str, checks: list[tuple[str, str]],
                 findings: list[Finding], context: str) -> None:  # fmt: skip
    """Markdown report (CI artifact, shown on the MR). `checks` = [(id, one-line purpose)]."""
    blocking = [f for f in findings if f.level == BLOCK]
    verdict = "FAIL" if blocking else "PASS"
    lines = [f"# {title}: {verdict}", "", context, "", "| check | result |", "|---|---|"]
    for cid, purpose in checks:
        mine = [f for f in findings if f.check == cid]
        worst = next((lvl for lvl in (BLOCK, WARN, INFO) if any(f.level == lvl for f in mine)), None)
        result = f"{_ICON[worst]} {len(mine)} {worst}" if worst else "✅ ok"
        lines.append(f"| `{cid}` — {purpose} | {result} |")
    if findings:
        lines += ["", "## Findings", ""]
        for f in sorted(findings, key=lambda f: ((BLOCK, WARN, INFO).index(f.level), f.check)):
            lines.append(f"- {_ICON[f.level]} **{f.level}** `{f.check}` · `{f.where}` — {f.message}")
    path.write_text("\n".join(lines) + "\n")


def print_findings(title: str, findings: list[Finding]) -> None:
    for f in findings:
        print(f"{f.level:5} {f.check:34} {f.where}: {f.message}")
    n = sum(f.level == BLOCK for f in findings)
    print(f"== {title}: {'FAIL' if n else 'PASS'} ({n} blocking, {len(findings) - n} other) ==")
