# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import prepare_runtime_xma as prepare
import test_runtime_xma as driver


class ResultGuards(unittest.TestCase):
    def test_leak_and_incomplete_cleanup_are_failures(self):
        text = ("MW3_XMA_POOL_DESTROYED:cycle=0\n"
                "MW3_XMA_COMPLETE:case=launch-failure cycles=1 threads_before=0 threads_after=0\n")
        self.assertTrue(driver.classify("launch-failure", 0, text))
        for bad in (text + "ERROR: LeakSanitizer: detected memory leaks\n",
                    text.replace("threads_after=0", "threads_after=1"),
                    text.replace("MW3_XMA_POOL_DESTROYED:cycle=0\n", ""),
                    text + text, text + "the APU failed to start\n"):
            self.assertFalse(driver.classify("launch-failure", 0, bad))
        self.assertFalse(driver.classify("launch-failure", 1, text))
        self.assertFalse(driver.classify("launch-failure", -999, text))

    def test_repeated_pool_requires_each_distinct_cycle(self):
        text = ("".join(f"MW3_XMA_POOL_DESTROYED:cycle={n}\n" for n in range(4))
                + "MW3_XMA_COMPLETE:case=repeat cycles=4 threads_before=0 threads_after=0\n")
        self.assertTrue(driver.classify("repeat", 0, text))
        self.assertFalse(driver.classify("repeat", 0, text.replace("cycle=2", "cycle=1")))
        self.assertFalse(driver.classify("loaded", 0, text))


class PreparationGuards(unittest.TestCase):
    def test_patch_and_parent_composition_are_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "lock.json"
            parent = Path(directory) / "parent.json"
            parent.write_text("parent")
            fragment = Path(directory) / "packet.patch"
            fragment.write_text("original patch\n", newline="\n")
            lock = dict(commit="reviewed", patch_path=fragment.name,
                        patch_sha256=prepare.common.sha(fragment), parent_stop_lock_sha256=prepare.common.sha(parent))
            lock_path.write_text(json.dumps(lock))
            with patch.object(prepare, "LOCK", lock_path), patch.object(prepare.stop, "LOCK", parent), \
                    patch.object(prepare.stop, "composition", return_value=(b"parent", dict(commit="reviewed"))):
                self.assertEqual(prepare.composition(False)[0], b"parent\noriginal patch\n")
                fragment.write_text("modified patch\n")
                with self.assertRaisesRegex(ValueError, "patch/parent mismatch"):
                    prepare.composition(False)
                fragment.write_text("original patch\n", newline="\n")
                parent.write_text("changed parent")
                with self.assertRaisesRegex(ValueError, "patch/parent mismatch"):
                    prepare.composition(False)

    def test_stale_preparer_receipt_rejected_before_source_access(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "manifest.json"
            value = dict(status="PASS", profile="xma-packet-v1", xma_lock_sha256=prepare.common.sha(prepare.LOCK),
                         script_sha256="0" * 64, core_sanitizers=False)
            report.write_text(json.dumps(value))
            with patch.object(prepare, "source_identity", side_effect=AssertionError("must not touch source")):
                with self.assertRaisesRegex(ValueError, "unreviewed"):
                    prepare.verify_prepared(Path(directory), report)
