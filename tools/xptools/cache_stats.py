"""`xptools cache-stats`: size and age of vcpkg binary caches (plus sccache, if present).

    xptools cache-stats                              # caches from VCPKG_BINARY_SOURCES / default
    xptools cache-stats --dir /srv/vcpkg-cache --top 10
    xptools cache-stats --dir /srv/vcpkg-cache --older-than 30            # list prune candidates
    xptools cache-stats --dir /srv/vcpkg-cache --older-than 30 --prune    # delete them

Package names come from the CONTROL file inside each archive, so the largest entries are
reported as e.g. "quantlib 1.44 x64-linux" rather than a hash. Age uses mtime: vcpkg rewrites
nothing on a cache hit, so mtime is the build/upload time.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

DAY = 86400


def default_dirs() -> list[Path]:
    """`files,<path>,...` entries of VCPKG_BINARY_SOURCES, else vcpkg's default location."""
    dirs = []
    for source in os.environ.get("VCPKG_BINARY_SOURCES", "").split(";"):
        parts = source.split(",")
        if parts[0] == "files" and len(parts) > 1:
            dirs.append(Path(parts[1]))
    if dirs:
        return dirs
    if os.environ.get("VCPKG_DEFAULT_BINARY_CACHE"):
        return [Path(os.environ["VCPKG_DEFAULT_BINARY_CACHE"])]
    xdg = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return [xdg / "vcpkg" / "archives"]


def describe(archive: Path) -> str:
    try:
        with zipfile.ZipFile(archive) as z:
            fields = dict(
                line.split(": ", 1)
                for line in z.read("CONTROL").decode().splitlines()
                if ": " in line
            )
        keys = ("Package", "Version", "Architecture")
        return " ".join(fields.get(k, "?") for k in keys)
    except (KeyError, zipfile.BadZipFile, OSError):
        return archive.stem[:12]


def scan(directory: Path, older_than: float | None, top: int) -> dict:
    now = time.time()
    entries = [(p, p.stat()) for p in directory.rglob("*.zip")] if directory.is_dir() else []
    entries.sort(key=lambda e: e[1].st_size, reverse=True)
    stale = [
        p for p, st in entries if older_than is not None and now - st.st_mtime > older_than * DAY
    ]
    ages = [(now - st.st_mtime) / DAY for _, st in entries]
    return {
        "dir": str(directory),
        "exists": directory.is_dir(),
        "archives": len(entries),
        "total_mb": round(sum(st.st_size for _, st in entries) / 1e6, 1),
        "newest_days": round(min(ages), 1) if ages else None,
        "oldest_days": round(max(ages), 1) if ages else None,
        "largest": [
            {"package": describe(p), "mb": round(st.st_size / 1e6, 1)} for p, st in entries[:top]
        ],
        "stale": [str(p) for p in stale],
    }


def sccache_stats() -> dict | None:
    if not shutil.which("sccache"):
        return None
    out = subprocess.run(
        ["sccache", "--show-stats", "--stats-format", "json"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if out.returncode != 0:
        return None
    stats = json.loads(out.stdout).get("stats", {})
    hits = sum(stats.get("cache_hits", {}).get("counts", {}).values())
    misses = sum(stats.get("cache_misses", {}).get("counts", {}).values())
    total = hits + misses
    return {"hits": hits, "misses": misses, "hit_rate": round(hits / total, 3) if total else None}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="xptools cache-stats", description=__doc__.split("\n")[0])
    parser.add_argument("--dir", action="append", type=Path, help="cache dir (repeatable)")
    parser.add_argument("--top", type=int, default=5, help="largest archives to list")
    parser.add_argument(
        "--older-than", type=float, metavar="DAYS", help="report entries older than DAYS"
    )
    parser.add_argument(
        "--prune", action="store_true", help="delete entries older than --older-than"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.prune and args.older_than is None:
        parser.error("--prune requires --older-than")

    reports = [scan(d, args.older_than, args.top) for d in (args.dir or default_dirs())]
    if args.prune:
        for report in reports:
            for path in report["stale"]:
                Path(path).unlink(missing_ok=True)
            report["pruned"] = len(report["stale"])
    result = {"vcpkg": reports, "sccache": sccache_stats()}

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for r in reports:
            if not r["exists"]:
                print(f"{r['dir']}: (missing)")
                continue
            print(f"{r['dir']}: {r['archives']} archives, {r['total_mb']} MB, "
                  f"newest {r['newest_days']} d, oldest {r['oldest_days']} d")  # fmt: skip
            for item in r["largest"]:
                print(f"  {item['mb']:>8} MB  {item['package']}")
            if args.older_than is not None:
                verb = "pruned" if args.prune else "older than"
                print(f"  {len(r['stale'])} archive(s) {verb} {args.older_than} d")
        if result["sccache"]:
            s = result["sccache"]
            print(f"sccache: {s['hits']} hits, {s['misses']} misses, hit rate {s['hit_rate']}")
    return 0 if all(r["exists"] for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
