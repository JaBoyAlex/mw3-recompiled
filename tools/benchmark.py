#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Validate and compare exported frame-time observations. Does not launch MW3."""
import argparse
import json
import math
from pathlib import Path
import statistics

FIELDS = ("scenario", "content_sha256", "hardware", "driver", "settings", "cache", "measurement")


def load(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("synthetic"), bool):
        raise ValueError("schema_version=1 and explicit synthetic boolean required")
    for key in (*FIELDS, "build", "compiler"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"missing metadata: {key}")
    if data["cache"] not in ("cold", "warm"):
        raise ValueError("cache must be cold or warm")
    if not isinstance(data.get("runs_ms"), list) or len(data["runs_ms"]) < 3:
        raise ValueError("at least three independent runs required")
    for run in data["runs_ms"]:
        if not isinstance(run, list) or len(run) < 2 or any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in run):
            raise ValueError("each run requires at least two finite, positive frame samples")
    return data


def percentile(values, fraction):
    ordered = sorted(values)
    at = (len(ordered) - 1) * fraction
    lo, hi = math.floor(at), math.ceil(at)
    return ordered[lo] * (hi - at) + ordered[hi] * (at - lo) if lo != hi else ordered[lo]


def summarize(data):
    # Give each independent run equal weight; do not pool unequal trace lengths.
    medians = [statistics.median(run) for run in data["runs_ms"]]
    return {"runs": len(medians), "samples": sum(map(len, data["runs_ms"])),
            "p50_ms": statistics.median(medians),
            "p95_ms": statistics.median(percentile(run, .95) for run in data["runs_ms"]),
            "p99_ms": statistics.median(percentile(run, .99) for run in data["runs_ms"]),
            "run_median_spread_ms": max(medians) - min(medians)}


def compare(before, after, tolerance_percent=5):
    if any(before[k] != after[k] for k in FIELDS) or before["synthetic"] != after["synthetic"]:
        raise ValueError("incomparable scenario/content/hardware/driver/settings/cache/measurement provenance")
    a, b = summarize(before), summarize(after)
    delta = 100 * (b["p95_ms"] / a["p95_ms"] - 1)
    noisy = max(a["run_median_spread_ms"] / a["p50_ms"], b["run_median_spread_ms"] / b["p50_ms"]) > .05
    return {"synthetic": before["synthetic"], "before": a, "after": b, "p95_change_percent": delta,
            "decision": "inconclusive-noisy" if noisy else "regression" if delta > tolerance_percent else "within-budget"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--tolerance-percent", type=float, default=5)
    args = parser.parse_args()
    try:
        if not math.isfinite(args.tolerance_percent) or args.tolerance_percent < 0:
            raise ValueError("tolerance must be finite and nonnegative")
        result = compare(load(args.before), load(args.after), args.tolerance_percent)
        print(json.dumps(result, indent=2))
        return 1 if result["decision"] != "within-budget" else 0
    except (ValueError, OSError) as e:
        parser.exit(2, f"benchmark failed: {e}\n")


if __name__ == "__main__":
    raise SystemExit(main())
