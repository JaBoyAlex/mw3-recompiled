# SPDX-License-Identifier: GPL-3.0-only
"""Original measurement/trace fixtures only; no MW3 timing or collector is tested."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("benchmark_v2", ROOT / "tools/benchmark.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def fixture():
    return dict(schema_version=2, synthetic=True, scenario="original-synthetic-case",
                file_sha256={"executable": sha("original synthetic executable identity")},
                build=dict(id="synthetic-a", artifact_sha256=sha("original host fixture"), source_revision="fixture-only", flags="synthetic"),
                compiler="fixture compiler 1", hardware=dict(cpu="synthetic CPU", gpu="synthetic GPU", ram_bytes=1024, machine_id="synthetic-machine"),
                os="synthetic OS", driver="synthetic driver", settings={"resolution": "synthetic", "quality": "fixture"},
                cache=dict(state="warm", policy="fixture prewarm"), measurement="synthetic present intervals", metric="frame_time", unit="ms",
                view_count=1, warmup=dict(description="synthetic warmup", duration_ms=100), capture_tool="original fixture exporter 1",
                sample_window_ms=1000,
                runs=[dict(id=f"run-{i}", trace_file=f"run-{i}.trace", trace_sha256=sha(f"original trace {i}"), samples=[10, 10, 10]) for i in range(3)])


class EvidenceTests(unittest.TestCase):
    def test_known_statistics_weight_runs_equally(self):
        data = fixture()
        for run, samples in zip(data["runs"], ([10]*100, [20, 20], [30, 30])):
            run["samples"] = samples
        summary = benchmark.summarize(data)
        self.assertEqual((summary["p50"], summary["p95"], summary["samples"]), (20, 20, 104))
        self.assertTrue(summary["noisy"])

    def test_build_change_is_allowed_but_provenance_changes_are_not(self):
        before, after = fixture(), fixture()
        after["build"] = dict(id="synthetic-b", artifact_sha256=sha("new fixture"), source_revision="new fixture source", flags="changed build flags")
        self.assertEqual(benchmark.compare(before, after)["decision"], "within-budget")
        changes = dict(scenario="other", file_sha256={"executable": sha("other")}, hardware=dict(before["hardware"], cpu="other"),
                       os="other", driver="other", settings={"quality": "other"}, cache=dict(before["cache"], policy="other"),
                       measurement="other", metric="gpu_time", unit="bytes", view_count=2,
                       warmup=dict(before["warmup"], duration_ms=200), capture_tool="other", compiler="other", sample_window_ms=2000)
        for key, value in changes.items():
            changed = fixture(); changed[key] = value
            if key == "unit": changed["metric"] = "vram"
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "incomparable"):
                benchmark.compare(before, changed)

    def test_memory_uses_worst_peak_and_zero_baseline_has_no_infinity(self):
        before, after = fixture(), fixture()
        for data in (before, after): data.update(metric="vram", unit="bytes")
        for run in before["runs"]: run["samples"] = [0, 0, 100]
        for run in after["runs"]: run["samples"] = [0, 0, 110]
        result = benchmark.compare(before, after)
        self.assertEqual((result["comparison_statistic"], result["decision"]), ("worst", "regression"))
        for run in before["runs"]: run["samples"] = [0]
        result = benchmark.compare(before, after)
        self.assertIsNone(result["change_percent"])
        json.dumps(result, allow_nan=False)

    def test_load_latency_scalar_samples_and_noise(self):
        for metric in ("load_time", "input_latency"):
            data = fixture(); data["metric"] = metric
            for run in data["runs"]: run["samples"] = [10]
            self.assertEqual(benchmark.compare(data, data)["decision"], "within-budget")
        data = fixture()
        for run, value in zip(data["runs"], (10, 20, 30)): run["samples"] = [value, value]
        self.assertEqual(benchmark.compare(data, data)["decision"], "inconclusive-noisy")

    def test_missing_and_invalid_metadata(self):
        for key in fixture():
            data = fixture(); del data[key]
            with self.subTest(key=key), self.assertRaises(ValueError): benchmark.validate(data)
        for key, value in (("schema_version", True), ("synthetic", 1), ("metric", []), ("unit", "fps"),
                           ("view_count", True), ("sample_window_ms", float("inf")), ("settings", {"bad": float("nan")}),
                           ("file_sha256", {"exe": "not-a-hash"}), ("build", {"id": "missing"})):
            data = fixture(); data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): benchmark.validate(data)
        data = fixture(); data["hardware"]["ram_bytes"] = True
        with self.assertRaises(ValueError): benchmark.validate(data)
        data = fixture(); data["cache"]["state"] = "cold"
        with self.assertRaisesRegex(ValueError, "warmup"): benchmark.validate(data)
        data = fixture(); data["traces_verified"] = True
        with self.assertRaisesRegex(ValueError, "unknown"): benchmark.validate(data)

    def test_samples_repeated_traces_and_paths(self):
        for value in (float("nan"), float("inf"), -1, 0, True, "10", 10**400):
            data = fixture(); data["runs"][0]["samples"][0] = value
            with self.assertRaises(ValueError): benchmark.validate(data)
        for value in (-1, 1.5, True, 2**64):
            data = fixture(); data.update(metric="vram", unit="bytes"); data["runs"][0]["samples"][0] = value
            with self.assertRaises(ValueError): benchmark.validate(data)
        for key in ("id", "trace_sha256"):
            data = fixture(); data["runs"][1][key] = data["runs"][0][key]
            with self.assertRaisesRegex(ValueError, "duplicate"): benchmark.validate(data)
        for path in ("../outside", "/absolute", "C:/outside", "..\\outside", "bad\0name"):
            data = fixture(); data["runs"][0]["trace_file"] = path
            with self.assertRaises(ValueError): benchmark.validate(data)

    def test_tolerances_and_percentile_edges(self):
        for value in (-1, float("inf"), float("nan"), True):
            with self.assertRaises(ValueError): benchmark.compare(fixture(), fixture(), value)
        for values, fraction in (([], .5), ([1], -1), ([1], 2), ([1], float("nan"))):
            with self.assertRaises(ValueError): benchmark.percentile(values, fraction)
        self.assertEqual(benchmark.percentile([1, 2, 3], 0), 1)
        self.assertEqual(benchmark.percentile([1, 2, 3], 1), 3)

    def create_real_validation_fixture(self, folder):
        # Simulated files exercise the *real-data validation path*, not game capture.
        data = fixture(); data["synthetic"] = False
        for i, run in enumerate(data["runs"]):
            payload = json.dumps(dict(original_fixture=i, samples=run["samples"]))
            (folder / run["trace_file"]).write_text(payload)
            run["trace_sha256"] = sha(payload)
        path = folder / "evidence.json"; path.write_text(json.dumps(data))
        return data, path

    def test_real_validation_requires_private_files_and_refuses_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); data, path = self.create_real_validation_fixture(root)
            with self.assertRaisesRegex(ValueError, "trace-root"): benchmark.load(path)
            loaded = benchmark.load(path, root)
            result = benchmark.compare(loaded, loaded)
            self.assertTrue(result["raw_trace_integrity_verified"])
            self.assertFalse(result["sample_derivation_verified"])
            self.assertEqual(result["before_export_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError, "verified raw"): benchmark.compare(dict(loaded), dict(loaded))
            changed = benchmark.load(path, root)
            changed["runs"][0]["samples"] = [1, 1, 1]
            with self.assertRaisesRegex(ValueError, "changed after load"): benchmark.compare(loaded, changed)
            (root / data["runs"][0]["trace_file"]).write_text("tampered")
            with self.assertRaisesRegex(ValueError, "hash mismatch"): benchmark.load(path, root)

    def test_large_finite_samples_do_not_produce_nonfinite_reports(self):
        before, after = fixture(), fixture()
        for run in before["runs"]: run["samples"] = [1e-308, 1e-308]
        for run in after["runs"]: run["samples"] = [1e308, 1e308]
        result = benchmark.compare(before, after)
        self.assertEqual(result["decision"], "regression")
        self.assertIsNone(result["change_percent"])
        json.dumps(result, allow_nan=False)

    def test_symlink_escape_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp); root = parent / "private"; root.mkdir()
            data, path = self.create_real_validation_fixture(root)
            outside = parent / "outside.trace"; outside.write_text("original outside fixture")
            link = root / "escape.trace"
            try: link.symlink_to(outside)
            except OSError: self.skipTest("host cannot create file symlinks")
            data["runs"][0].update(trace_file="escape.trace", trace_sha256=sha(outside.read_text()))
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "outside"): benchmark.load(path, root)

    def test_legacy_real_and_mixed_schema_are_refused(self):
        legacy = json.loads((ROOT / "qa/benchmarks/synthetic.json").read_text())
        legacy["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "schema_version=2"): benchmark.validate(legacy)
        legacy["synthetic"] = True
        with self.assertRaisesRegex(ValueError, "schema versions"): benchmark.compare(legacy, fixture())

    def test_cli_decisions_and_explicit_synthetic_label(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); before = root / "before.json"; after = root / "after.json"
            data = fixture(); before.write_text(json.dumps(data)); after.write_text(json.dumps(data))
            command = [sys.executable, str(ROOT / "tools/benchmark.py"), str(before), str(after)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["synthetic"]); self.assertFalse(report["raw_trace_integrity_verified"])
            for run in data["runs"]: run["samples"] = [20, 20, 20]
            after.write_text(json.dumps(data))
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
            data["metric"] = "fps"; after.write_text(json.dumps(data))
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)

    def test_committed_schema2_example_remains_synthetic(self):
        data = benchmark.load(ROOT / "qa/benchmarks/synthetic-v2.json")
        report = benchmark.compare(data, data)
        self.assertTrue(report["synthetic"])
        self.assertFalse(report["raw_trace_integrity_verified"])
        self.assertEqual(report["decision"], "within-budget")


if __name__ == "__main__":
    unittest.main()
