# SPDX-License-Identifier: GPL-3.0-only
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import benchmark
import inventory
import project


def sample_task(ident="MW3-001", **changes):
    task = dict(id=ident, title="Test task", goal="Test behavior", area="test", size="small", phase=1,
                priority=0, status="todo", depends_on=[], paths=["runtime/test"], acceptance=["Observable result"], validation=["Run test"])
    task.update(changes)
    return task


class FakeGitHub:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.writes = []

    def issues(self):
        return copy.deepcopy(self.rows)

    def call(self, method, path, data=None):
        if method == "GET":
            return []
        self.writes.append((method, path, data))
        if path == "/issues":
            ident = data["title"][1:8]
            row = dict(data, number=len(self.rows) + 1, state="open", assignees=[])
            self.rows[ident] = row
            return row
        if path.startswith("/issues/") and method == "PATCH":
            number = int(path.rsplit("/", 1)[1])
            next(row for row in self.rows.values() if row["number"] == number).update(data)
        return {}


class CatalogTests(unittest.TestCase):
    def load(self, tasks):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tasks").mkdir()
            for task in tasks:
                (root / "tasks" / (task["id"] + ".json")).write_text(json.dumps(task))
            return project.load_tasks(root)

    def test_missing_dependency_and_cycle(self):
        with self.assertRaisesRegex(ValueError, "unknown dependency"):
            self.load([sample_task(depends_on=["MW3-002"])])
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.load([sample_task(depends_on=["MW3-002"]), sample_task("MW3-002", depends_on=["MW3-001"])])

    def test_done_requires_real_dependency_completion_and_evidence(self):
        with self.assertRaisesRegex(ValueError, "done requires evidence"):
            self.load([sample_task(status="done")])
        with self.assertRaisesRegex(ValueError, "completed before"):
            self.load([sample_task(), sample_task("MW3-002", depends_on=["MW3-001"], status="done", evidence=["report"])])

    def test_readiness(self):
        tasks = self.load([sample_task(status="done", evidence=["test log"]), sample_task("MW3-002", depends_on=["MW3-001"])])
        self.assertEqual(project.blockers(tasks["MW3-002"], tasks), [])
        tasks["MW3-001"]["status"] = "todo"
        self.assertEqual(project.blockers(tasks["MW3-002"], tasks), ["MW3-001"])

    def test_prompt_contains_scope_and_acceptance(self):
        text = project.prompt(sample_task())
        self.assertIn("runtime/test", text)
        self.assertIn("Observable result", text)
        self.assertIn("Run test", text)

    def test_sync_dry_run_and_repeat_preserve_live_state(self):
        tasks = {"MW3-001": sample_task()}
        remote = FakeGitHub()
        project.sync(tasks, remote)
        self.assertEqual(remote.writes, [])
        project.sync(tasks, remote, apply=True)
        self.assertEqual(len(remote.rows), 1)
        remote.rows["MW3-001"].update(state="closed", assignees=[{"login": "owner"}])
        remote.writes.clear()
        project.sync(tasks, remote, apply=True)
        self.assertFalse(any(path == "/issues" for _, path, _ in remote.writes))
        self.assertEqual(remote.rows["MW3-001"]["state"], "closed")
        self.assertEqual(remote.rows["MW3-001"]["assignees"], [{"login": "owner"}])

    def test_claim_refuses_unfinished_and_other_owner(self):
        tasks = {"MW3-001": sample_task(), "MW3-002": sample_task("MW3-002", depends_on=["MW3-001"])}
        remote = FakeGitHub({"MW3-001": dict(number=1, state="open", assignees=[]), "MW3-002": dict(number=2, state="open", assignees=[])})
        with self.assertRaisesRegex(ValueError, "unfinished dependencies"):
            project.claim(tasks, remote, "MW3-002", "owner")
        remote.rows["MW3-001"]["assignees"] = [{"login": "someone-else"}]
        with self.assertRaisesRegex(ValueError, "already assigned"):
            project.claim(tasks, remote, "MW3-001", "owner")
        self.assertEqual(remote.writes, [])

    def test_claim_scope_conflicts_and_workflow_only_mutation(self):
        tasks = {"MW3-001": sample_task(), "MW3-002": sample_task("MW3-002", paths=["runtime"])}
        remote = FakeGitHub({"MW3-001": dict(number=1, state="open", assignees=[]), "MW3-002": dict(number=2, state="open", assignees=[{"login": "friend"}])})
        with self.assertRaisesRegex(ValueError, "scope conflicts"):
            project.claim(tasks, remote, "MW3-001", "owner")
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(ValueError, "serialized"):
                project.claim(tasks, remote, "MW3-001", "owner", apply=True)

    def test_release_only_current_owner(self):
        tasks = {"MW3-001": sample_task()}
        remote = FakeGitHub({"MW3-001": dict(number=1, state="open", assignees=[{"login": "friend"}])})
        with self.assertRaisesRegex(ValueError, "current sole assignee"):
            project.claim(tasks, remote, "MW3-001", "owner", action="release")

    def test_repo_input_not_shell_or_url(self):
        for value in ("https://github.com/a/b", "a/b/c", "a/b?x=y", "a/b\n"):
            with self.assertRaises(ValueError):
                project.GitHub(value)


class InventoryTests(unittest.TestCase):
    def test_deterministic_hash_and_no_path_disclosure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "default.xex"
            data = b"XEX2" + bytes(range(256))
            path.write_bytes(data)
            before = path.stat()
            result = inventory.identify(path)
            self.assertEqual(result, inventory.identify(path))
            self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(result["format"], "XEX2")
            self.assertNotIn(directory, json.dumps(result))
            self.assertEqual(before.st_mtime_ns, path.stat().st_mtime_ns)

    def test_output_cannot_overwrite_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "owned.xex"
            data = b"XEX2original"
            path.write_bytes(data)
            result = subprocess.run([sys.executable, str(Path(inventory.__file__)), str(path), "--output", str(path)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_bytes(), data)

    def test_directory_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                inventory.identify(directory)


class BenchmarkTests(unittest.TestCase):
    def data(self):
        return dict(schema_version=1, synthetic=True, scenario="synthetic", content_sha256="none-synthetic",
                    hardware="fake", driver="fake", settings="720p", cache="warm", measurement="cpu-frame",
                    build="a", compiler="test", runs_ms=[[10, 10, 10], [10, 10, 10], [10, 10, 10]])

    def test_percentile_known_values(self):
        self.assertEqual(benchmark.percentile([4, 1, 2, 3], .5), 2.5)
        self.assertEqual(benchmark.percentile([1, 2, 3], .95), 2.9)

    def test_regression_and_noise(self):
        a, b = self.data(), self.data()
        b["runs_ms"] = [[12, 12, 12]] * 3
        self.assertEqual(benchmark.compare(a, b)["decision"], "regression")
        b["runs_ms"] = [[10, 10], [30, 30], [20, 20]]
        self.assertEqual(benchmark.compare(a, b)["decision"], "inconclusive-noisy")

    def test_incomparable_provenance(self):
        for key in benchmark.FIELDS:
            a, b = self.data(), self.data()
            b[key] += "-changed"
            with self.assertRaisesRegex(ValueError, "incomparable"):
                benchmark.compare(a, b)

    def test_invalid_samples_rejected(self):
        for bad in (float("nan"), float("inf"), -1, 0, True, "10"):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "run.json"
                data = self.data()
                data["runs_ms"][0][0] = bad
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    benchmark.load(path)


if __name__ == "__main__":
    unittest.main()
