"""quarantine_rules.py — format + SLA rules for a generated repo's quarantine.txt.

Reused from xp-pricer tools/xptools/quarantine.py (parse / sla_errors, same 14-day SLA and
10-entry cap); only the file location differs: <repo>/quarantine.txt.

    <ctest name> | <owner> | <issue URL> | <added YYYY-MM-DD> | <expires YYYY-MM-DD>
    unit.black_scholes.put-call parity holds | @jdoe | https://gitlab/.../issues/12 | 2026-11-14 | 2026-11-28
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

MAX_DAYS = 14  # SLA: quarantine is a 2-week loan, not a parking lot
MAX_ENTRIES = 10  # more than this and the suite is not trustworthy: stop and fix
OWNER = re.compile(r"^@[\w.-]+(/[\w.-]+)*$")
DATE = "%Y-%m-%d"


@dataclass
class Entry:
    name: str
    owner: str
    issue: str
    added: dt.date
    expires: dt.date


def parse(text: str) -> tuple[list[Entry], list[str]]:
    entries, errors = [], []
    for no, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        fields = [f.strip() for f in raw.split("|")]
        if len(fields) != 5 or not all(fields):
            errors.append(f"line {no}: expected 5 '|'-separated fields: {raw!r}")
            continue
        name, owner, issue, added, expires = fields
        try:
            entry = Entry(name, owner, issue, dt.datetime.strptime(added, DATE).date(),
                          dt.datetime.strptime(expires, DATE).date())  # fmt: skip
        except ValueError:
            errors.append(f"line {no}: dates must be YYYY-MM-DD: {raw!r}")
            continue
        if not OWNER.match(owner):
            errors.append(f"line {no}: owner must be a GitLab @user or @group: {owner!r}")
        if not issue.startswith(("https://", "http://")):
            errors.append(f"line {no}: issue must be a URL: {issue!r}")
        entries.append(entry)
    return entries, errors


def sla_errors(entries: list[Entry], today: dt.date) -> list[str]:
    errors = []
    for e in entries:
        if (e.expires - e.added).days > MAX_DAYS:
            errors.append(
                f"{e.name!r}: quarantined for more than {MAX_DAYS} days ({e.added}..{e.expires})"
            )
        if e.expires < today:
            errors.append(
                f"{e.name!r}: quarantine expired {e.expires} (owner {e.owner}): fix or delete"
            )
    names = [e.name for e in entries]
    errors += [f"{n!r}: listed twice" for n in sorted({n for n in names if names.count(n) > 1})]
    if len(entries) > MAX_ENTRIES:
        errors.append(
            f"{len(entries)} quarantined tests (max {MAX_ENTRIES}): the suite needs fixing"
        )
    return errors
