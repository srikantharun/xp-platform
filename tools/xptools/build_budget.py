"""`xptools build-budget`: compile-time/size budgets and wall-time/cache regressions.

    xptools build-budget --preset ci-linux-gcc                       # static budgets only
    xptools build-budget --preset ci-linux-gcc --baseline .ci-baseline/ci-linux-gcc.json
    xptools build-budget --preset ci-linux-gcc --baseline B.json --record   # main-branch runs

Static budgets (tools/build-budget.toml; [default] overridden by [preset.<name>]) use
build/<preset>/.ninja_log: slowest TU and summed compile time (= clean serial rebuild cost).

Regression check: build/<preset>/build-metrics.json (written by `run_step.py build`: wall
time + sccache hit rate) is compared with the baseline's samples from previous main-branch
builds. It fails when
    wall_seconds > p95(baseline wall_seconds) * (1 + 0.15)       (slower than normal), or
    hit_rate     < p5(baseline hit_rate)      * (1 - 0.15)       (cache much colder than normal)
and is enforced only once the baseline holds >= --min-samples (default 5). --record appends
the current sample (keeping the newest --keep). Compare builds from one runner class only.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUDGET = ROOT / "tools" / "build-budget.toml"
OBJECT_SUFFIXES = (".o", ".obj")


def read_ninja_log(path: Path) -> dict[str, float]:
    """output -> seconds for the most recent run of each edge (log v5/v6 are append-only)."""
    durations: dict[str, float] = {}
    for line in path.read_text().splitlines():
        fields = line.split("\t")
        if not line.startswith("#") and len(fields) >= 4:
            durations[fields[3]] = (int(fields[1]) - int(fields[0])) / 1000.0
    return durations


def load_budget(path: Path, preset: str) -> dict:
    data = tomllib.loads(path.read_text())
    budget = dict(data.get("default", {}))
    override = data.get("preset", {}).get(preset, {})
    sizes = {**budget.get("max_artifact_mb", {}), **override.get("max_artifact_mb", {})}
    budget.update(override)
    budget["max_artifact_mb"] = sizes
    return budget


def static_budgets(build_dir: Path, budget: dict, top: int) -> dict:
    """Slowest TUs, summed compile time and artifact sizes against tools/build-budget.toml."""
    objects = {
        k: v
        for k, v in read_ninja_log(build_dir / ".ninja_log").items()
        if k.endswith(OBJECT_SUFFIXES)
    }
    slowest = sorted(objects.items(), key=lambda kv: kv[1], reverse=True)
    total = round(sum(objects.values()), 1)
    failures = []
    if total > budget.get("max_total_compile_seconds", math.inf):
        failures.append(f"total compile {total}s > {budget['max_total_compile_seconds']}s")
    max_tu = budget.get("max_tu_seconds", math.inf)
    failures += [f"{tu}: {secs}s > {max_tu}s" for tu, secs in slowest if secs > max_tu]
    sizes = {}
    for artifact, limit in budget["max_artifact_mb"].items():
        path = build_dir / artifact
        if path.is_file():  # absent when e.g. the CLI is disabled, or Multi-Config <Config>/ dirs
            sizes[artifact] = round(path.stat().st_size / 1e6, 2)
            if sizes[artifact] > limit:
                failures.append(f"{artifact}: {sizes[artifact]} MB > {limit} MB")
    return {
        "translation_units": len(objects),
        "total_compile_seconds": total,
        "slowest": [{"tu": tu, "seconds": secs} for tu, secs in slowest[:top]],
        "artifact_mb": sizes,
        "failures": failures,
    }


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (no interpolation: always an observed value)."""
    ordered = sorted(values)
    return ordered[max(1, math.ceil(pct / 100 * len(ordered))) - 1]


def check_regression(metrics: dict, samples: list[dict], max_reg: float, min_samples: int) -> dict:
    """Wall time vs baseline p95 (+max_reg) and sccache hit rate vs baseline p5 (-max_reg)."""
    current_hit = (metrics.get("sccache") or {}).get("hit_rate")
    result: dict = {
        "samples": len(samples),
        "enforced": len(samples) >= min_samples,
        "current": {"wall_seconds": metrics.get("wall_seconds"), "hit_rate": current_hit},
        "failures": [],
    }
    if not result["enforced"]:
        return result
    walls = [s["wall_seconds"] for s in samples if s.get("wall_seconds") is not None]
    limit = round(percentile(walls, 95) * (1 + max_reg), 2)
    result["wall_limit_seconds"] = limit
    if (metrics.get("wall_seconds") or 0) > limit:
        result["failures"].append(
            f"wall time {metrics['wall_seconds']}s > {limit}s (p95 +{max_reg:.0%})"
        )
    hits = [s["hit_rate"] for s in samples if s.get("hit_rate") is not None]
    if hits and current_hit is not None:
        floor = round(percentile(hits, 5) * (1 - max_reg), 3)
        result["hit_rate_floor"] = floor
        if current_hit < floor:
            result["failures"].append(
                f"sccache hit rate {current_hit} < {floor} (p5 -{max_reg:.0%})"
            )
    return result


def record_sample(path: Path, metrics: dict, keep: int) -> None:
    data = json.loads(path.read_text()) if path.is_file() else {"samples": []}
    data["samples"].append(
        {
            "wall_seconds": metrics.get("wall_seconds"),
            "hit_rate": (metrics.get("sccache") or {}).get("hit_rate"),
            "sha": metrics.get("sha"),
            "recorded": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    data["samples"] = data["samples"][-keep:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def print_report(report: dict, args: argparse.Namespace) -> None:
    tus, total = report["translation_units"], report["total_compile_seconds"]
    print(f"{args.preset}: {tus} TUs, {total}s total compile")
    for item in report["slowest"]:
        print(f"  {item['seconds']:>7.1f}s  {item['tu']}")
    for artifact, mb in report["artifact_mb"].items():
        print(
            f"  {mb:>7} MB  {artifact} (budget {report['budget']['max_artifact_mb'][artifact]} MB)"
        )
    reg = report["regression"]
    if reg is not None:
        cur = reg["current"]
        print(f"  wall {cur['wall_seconds']}s, sccache hit rate {cur['hit_rate']}")
        if reg["enforced"]:
            floor = reg.get("hit_rate_floor", "n/a")
            print(f"  limits: wall <= {reg['wall_limit_seconds']}s, hit rate >= {floor}")
        else:
            print(f"  baseline has {reg['samples']} < {args.min_samples} samples: not enforced yet")
        if args.record:
            print(f"  recorded sample in {args.baseline}")
    print("\n".join(f"OVER BUDGET: {f}" for f in report["failures"]) or "within budget")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="xptools build-budget", description=__doc__.split("\n")[0]
    )
    parser.add_argument("--preset", required=True)
    parser.add_argument("--budget", type=Path, default=DEFAULT_BUDGET)
    parser.add_argument("--build-dir", type=Path, help="default: build/<preset>")
    parser.add_argument("--top", type=int, default=5, help="slowest translation units to show")
    parser.add_argument("--baseline", type=Path, help="baseline JSON of previous build samples")
    parser.add_argument("--metrics", type=Path, help="default: build/<preset>/build-metrics.json")
    parser.add_argument("--record", action="store_true", help="append this build to --baseline")
    parser.add_argument("--max-regression", type=float, default=0.15)
    parser.add_argument("--min-samples", type=int, default=5)
    parser.add_argument("--keep", type=int, default=30, help="baseline samples to retain")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    build_dir = args.build_dir or Path.cwd() / "build" / args.preset  # project root, not platform/
    if not (build_dir / ".ninja_log").is_file():
        print(f"{build_dir / '.ninja_log'} not found: build the preset first", file=sys.stderr)
        return 2
    budget = load_budget(args.budget, args.preset)
    report = {
        "preset": args.preset,
        "budget": budget,
        **static_budgets(build_dir, budget, args.top),
    }
    report["regression"] = None
    if args.baseline:
        metrics_path = args.metrics or build_dir / "build-metrics.json"
        if not metrics_path.is_file():
            print(f"{metrics_path} not found: build with tools/ci/run_step.py", file=sys.stderr)
            return 2
        metrics = json.loads(metrics_path.read_text())
        samples = (
            json.loads(args.baseline.read_text())["samples"] if args.baseline.is_file() else []
        )
        report["regression"] = check_regression(
            metrics, samples, args.max_regression, args.min_samples
        )
        report["failures"] += report["regression"]["failures"]
        if args.record:
            record_sample(args.baseline, metrics, args.keep)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report, args)
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
