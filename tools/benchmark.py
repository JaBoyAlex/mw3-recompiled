#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Validate comparable exported evidence; does not capture or launch MW3."""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re

FIELDS = ("scenario", "content_sha256", "hardware", "driver", "settings", "cache", "measurement")
V2_FIELDS = ("scenario", "file_sha256", "hardware", "os", "driver", "settings", "cache", "measurement",
             "metric", "unit", "view_count", "warmup", "capture_tool", "compiler", "sample_window_ms")
METRICS = {"frame_time": "ms", "cpu_main_time": "ms", "cpu_render_submit": "ms", "gpu_time": "ms",
           "load_time": "ms", "input_latency": "ms", "working_set": "bytes", "commit": "bytes", "vram": "bytes"}


class Evidence(dict):
    """Integrity state comes from load(), never a JSON-supplied trust flag."""
    traces_verified = False
    export_sha256 = None
    fingerprint = None


def number(value, minimum=0):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= minimum
    except OverflowError:
        return False


def digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def text_field(value):
    return isinstance(value, str) and bool(value.strip())


def trace_name(value):
    return (text_field(value) and not value.startswith("/") and not any(c in value for c in ("\\", ":", "\0"))
            and ".." not in PurePosixPath(value).parts and bool(PurePosixPath(value).name) and not value.endswith("/"))


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def change_percent(before, after):
    if not before:
        return 0 if not after else None
    value = (after / before - 1) * 100
    return value if math.isfinite(value) else None


def validate(data):
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or type(data.get("synthetic")) is not bool:
        raise ValueError("integer schema_version and explicit synthetic boolean required")
    if data["schema_version"] == 1:
        if not data["synthetic"]:
            raise ValueError("real evidence requires schema_version=2 and verified raw traces")
        for key in (*FIELDS, "build", "compiler"):
            if not text_field(data.get(key)):
                raise ValueError(f"missing metadata: {key}")
        if data["cache"] not in ("cold", "warm"):
            raise ValueError("cache must be cold or warm")
        runs = data.get("runs_ms")
        if not isinstance(runs, list) or len(runs) < 3:
            raise ValueError("at least three independent runs required")
        for run in runs:
            if not isinstance(run, list) or len(run) < 2 or any(not number(x) or x <= 0 for x in run):
                raise ValueError("each run requires at least two finite, positive frame samples")
        return data
    if data["schema_version"] != 2:
        raise ValueError("unsupported evidence schema")
    required = set(V2_FIELDS) | {"schema_version", "synthetic", "build", "runs"}
    if set(data) - required - {"notes"} or required - set(data):
        raise ValueError("missing or unknown schema-2 fields")
    for key in ("scenario", "os", "driver", "measurement", "capture_tool", "compiler"):
        if not text_field(data[key]):
            raise ValueError(f"missing metadata: {key}")
    if not isinstance(data["build"], dict) or set(data["build"]) != {"id", "artifact_sha256", "source_revision", "flags"}:
        raise ValueError("build requires id, artifact_sha256, source_revision and flags")
    if not digest(data["build"]["artifact_sha256"]) or not all(text_field(data["build"][k]) for k in ("id", "source_revision", "flags")):
        raise ValueError("invalid build identity")
    files = data["file_sha256"]
    if not isinstance(files, dict) or not files or not all(text_field(k) and digest(v) for k, v in files.items()):
        raise ValueError("file_sha256 requires named input/content hashes")
    hw = data["hardware"]
    if not isinstance(hw, dict) or set(hw) != {"cpu", "gpu", "ram_bytes", "machine_id"} or not all(text_field(hw[k]) for k in ("cpu", "gpu", "machine_id")):
        raise ValueError("invalid hardware identity")
    if type(hw["ram_bytes"]) is not int or not 0 < hw["ram_bytes"] < 2**64:
        raise ValueError("invalid hardware RAM")
    if not isinstance(data["settings"], dict) or not data["settings"]:
        raise ValueError("nonempty quality/configuration settings required")
    # Also refuse NaN/infinity in nested settings and keep comparison deterministic.
    try:
        json.dumps(data["settings"], allow_nan=False, sort_keys=True)
    except (ValueError, TypeError) as error:
        raise ValueError("invalid settings metadata") from error
    cache = data["cache"]
    if not isinstance(cache, dict) or set(cache) != {"state", "policy"} or cache["state"] not in ("cold", "warm") or not text_field(cache["policy"]):
        raise ValueError("cache requires cold/warm state and explicit reset/prewarm policy")
    warmup = data["warmup"]
    if not isinstance(warmup, dict) or set(warmup) != {"description", "duration_ms"} or not text_field(warmup["description"]) or not number(warmup["duration_ms"]):
        raise ValueError("invalid warmup policy")
    if cache["state"] == "cold" and warmup["duration_ms"] != 0:
        raise ValueError("cold evidence cannot include a warmup")
    if type(data["view_count"]) is not int or not 1 <= data["view_count"] <= 4 or not number(data["sample_window_ms"]) or data["sample_window_ms"] <= 0:
        raise ValueError("invalid view count or sample window")
    if not isinstance(data["metric"], str) or data["metric"] not in METRICS or data["unit"] != METRICS[data["metric"]]:
        raise ValueError("unsupported metric or mismatched unit")
    runs = data["runs"]
    if not isinstance(runs, list) or len(runs) < 3:
        raise ValueError("at least three independent runs required")
    ids, traces = set(), set()
    for run in runs:
        if not isinstance(run, dict) or set(run) != {"id", "trace_file", "trace_sha256", "samples"}:
            raise ValueError("invalid run fields")
        if not text_field(run["id"]) or run["id"] in ids or not digest(run["trace_sha256"]) or run["trace_sha256"] in traces or not trace_name(run["trace_file"]):
            raise ValueError("duplicate/invalid run or trace identity")
        ids.add(run["id"]); traces.add(run["trace_sha256"])
        samples = run["samples"]
        minimum = 2 if data["metric"] in ("frame_time", "cpu_main_time", "cpu_render_submit", "gpu_time") else 1
        if not isinstance(samples, list) or len(samples) < minimum:
            raise ValueError("insufficient metric samples")
        for value in samples:
            if data["unit"] == "bytes":
                valid = type(value) is int and 0 <= value < 2**64
            else:
                valid = number(value) and value > 0
            if not valid:
                raise ValueError("invalid metric sample")
    return data


def load(path, trace_root=None):
    path = Path(path)
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("evidence export exceeds 64 MiB budget")
    raw = path.read_bytes()
    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")
    data = Evidence(validate(json.loads(raw, parse_constant=reject_constant)))
    data.export_sha256 = hashlib.sha256(raw).hexdigest()
    data.fingerprint = fingerprint(data)
    if data["schema_version"] == 2 and not data["synthetic"]:
        if trace_root is None:
            raise ValueError("real evidence requires --trace-root to verify private raw traces")
        root = Path(trace_root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("trace root must be a directory")
        for run in data["runs"]:
            trace = (root / run["trace_file"]).resolve(strict=True)
            if not trace.is_relative_to(root) or not trace.is_file():
                raise ValueError("raw trace outside supplied root or not a file")
            sha = hashlib.sha256()
            with trace.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    sha.update(chunk)
            if sha.hexdigest() != run["trace_sha256"]:
                raise ValueError("raw trace hash mismatch")
        data.traces_verified = True
    return data


def percentile(values, fraction):
    if not values or not number(fraction) or fraction > 1:
        raise ValueError("percentile requires samples and a fraction in [0,1]")
    ordered = sorted(values)
    at = (len(ordered) - 1) * fraction
    lo, hi = math.floor(at), math.ceil(at)
    return ordered[lo] * (hi - at) + ordered[hi] * (at - lo) if lo != hi else ordered[lo]


def summarize(data):
    validate(data)
    if data["schema_version"] == 2:
        runs = [r["samples"] for r in data["runs"]]
        medians = [percentile(r, .5) for r in runs]
        peaks = [max(r) for r in runs]
        noise_values = peaks if data["unit"] == "bytes" else medians
        center = percentile(noise_values, .5)
        spread = max(noise_values) - min(noise_values)
        spread_percent = spread / center * 100 if center else (0 if not spread else None)
        if spread_percent is not None and not math.isfinite(spread_percent): spread_percent = None
        return dict(runs=len(runs), samples=sum(map(len, runs)), unit=data["unit"],
                    p50=percentile(medians, .5), p95=percentile([percentile(r, .95) for r in runs], .5),
                    p99=percentile([percentile(r, .99) for r in runs], .5), worst=max(peaks),
                    run_spread_percent=spread_percent,
                    noisy=spread > .05 * center)
    # Give each independent run equal weight; do not pool unequal trace lengths.
    medians = [percentile(run, .5) for run in data["runs_ms"]]
    return {"runs": len(medians), "samples": sum(map(len, data["runs_ms"])),
            "p50_ms": percentile(medians, .5),
            "p95_ms": percentile([percentile(run, .95) for run in data["runs_ms"]], .5),
            "p99_ms": percentile([percentile(run, .99) for run in data["runs_ms"]], .5),
            "run_median_spread_ms": max(medians) - min(medians)}


def compare(before, after, tolerance_percent=5):
    if not number(tolerance_percent):
        raise ValueError("tolerance must be finite and nonnegative")
    try:
        validate(before); validate(after)
    except ValueError as error:
        raise ValueError(f"incomparable or invalid evidence: {error}") from error
    for data in (before, after):
        if isinstance(data, Evidence) and data.fingerprint != fingerprint(data):
            raise ValueError("evidence changed after load; reload the original export")
    if before["schema_version"] != after["schema_version"]:
        raise ValueError("incomparable evidence schema versions")
    if before["schema_version"] == 2:
        if any(before[k] != after[k] for k in V2_FIELDS) or before["synthetic"] != after["synthetic"]:
            raise ValueError("incomparable schema-2 provenance")
        verified = all(isinstance(d, Evidence) and d.traces_verified for d in (before, after))
        if not before["synthetic"] and not verified:
            raise ValueError("load real evidence with verified raw traces before comparison")
        a, b = summarize(before), summarize(after)
        statistic = "worst" if before["unit"] == "bytes" else "p95"
        baseline, changed = a[statistic], b[statistic]
        delta = change_percent(baseline, changed)
        noisy = a["noisy"] or b["noisy"]
        regression = changed > baseline * (1 + tolerance_percent / 100)
        return dict(schema_version=2, synthetic=before["synthetic"], metric=before["metric"], unit=before["unit"],
                    before_build=before["build"], after_build=after["build"], before=a, after=b,
                    before_export_sha256=getattr(before, "export_sha256", None), after_export_sha256=getattr(after, "export_sha256", None),
                    comparison_statistic=statistic, change_percent=delta, raw_trace_integrity_verified=verified,
                    sample_derivation_verified=False, statistical_confidence="not-estimated",
                    decision="inconclusive-noisy" if noisy else "regression" if regression else "within-budget")
    if any(before[k] != after[k] for k in FIELDS) or before["synthetic"] != after["synthetic"]:
        raise ValueError("incomparable scenario/content/hardware/driver/settings/cache/measurement provenance")
    a, b = summarize(before), summarize(after)
    delta = change_percent(a["p95_ms"], b["p95_ms"])
    noisy = max(a["run_median_spread_ms"] / a["p50_ms"], b["run_median_spread_ms"] / b["p50_ms"]) > .05
    return {"synthetic": before["synthetic"], "before": a, "after": b, "p95_change_percent": delta,
            "decision": "inconclusive-noisy" if noisy else "regression" if b["p95_ms"] > a["p95_ms"] * (1 + tolerance_percent / 100) else "within-budget"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--tolerance-percent", type=float, default=5)
    parser.add_argument("--trace-root", type=Path, help="private raw-trace root; required for real schema-2 exports")
    args = parser.parse_args()
    try:
        if not math.isfinite(args.tolerance_percent) or args.tolerance_percent < 0:
            raise ValueError("tolerance must be finite and nonnegative")
        result = compare(load(args.before, args.trace_root), load(args.after, args.trace_root), args.tolerance_percent)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 1 if result["decision"] != "within-budget" else 0
    except (ValueError, OSError, RecursionError) as e:
        parser.exit(2, f"benchmark failed: {e}\n")


if __name__ == "__main__":
    raise SystemExit(main())
