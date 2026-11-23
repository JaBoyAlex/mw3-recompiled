# SPDX-License-Identifier: GPL-3.0-only
"""Synthetic SDK selection/isolation guards; actual kernel cases remain separate."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import test_startup_memory as driver


class ProfileSelection(unittest.TestCase):
    def test_only_explicit_reviewed_verifiers_can_be_selected(self):
        self.assertIs(driver.sdk_verifier("xma-packet-v1"), driver.xma_profile)
        self.assertIs(driver.sdk_verifier("memory-imports-v1"), driver.memory_profile)
        for name in ("", "automatic", "unverified", None):
            with self.subTest(profile=name), self.assertRaises(ValueError):
                driver.sdk_verifier(name)

    def test_invalid_repair_receipt_never_falls_back_or_creates_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "private-runs"
            args = ["audit", "--root", str(root), "--sdk-report", str(root / "wrong-parent.json"),
                    "--output-root", str(output), "--sdk-profile", "memory-imports-v1"]
            with patch.object(sys, "argv", args), contextlib.redirect_stderr(io.StringIO()), \
                    patch.object(driver.memory_profile, "verify_prepared", side_effect=ValueError("wrong parent")) as repaired, \
                    patch.object(driver.xma_profile, "verify_prepared") as baseline, \
                    patch.object(driver.subprocess, "run") as build:
                with self.assertRaises(SystemExit) as error:
                    driver.main()
                self.assertEqual(error.exception.code, 2)
                repaired.assert_called_once()
                baseline.assert_not_called()
                build.assert_not_called()
            self.assertFalse(output.exists())

    def test_default_preserves_baseline_and_never_guesses_the_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = ["audit", "--root", str(root), "--sdk-report", str(root / "repair.json"),
                    "--output-root", str(root / "private-runs")]
            with patch.object(sys, "argv", args), contextlib.redirect_stderr(io.StringIO()), \
                    patch.object(driver.xma_profile, "verify_prepared", side_effect=ValueError("wrong profile")) as baseline, \
                    patch.object(driver.memory_profile, "verify_prepared") as repaired:
                with self.assertRaises(SystemExit) as error:
                    driver.main()
                self.assertEqual(error.exception.code, 2)
                baseline.assert_called_once()
                repaired.assert_not_called()
            self.assertFalse((root / "private-runs").exists())

    def test_outputs_cannot_overlap_either_sdk_family_or_maintained_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "cache"
            root.mkdir()
            receipt = root / "memory-imports-preparations/attempt/manifest.json"
            sdk = receipt.parent / "sdk"
            sdk.mkdir(parents=True)
            before = {p.relative_to(root) for p in root.rglob("*")}
            for requested in (root, root.parent, sdk, sdk / "runs", receipt.parent,
                              root / "sources/child", root / "build/child", root / "install/child",
                              root / "memory-preparations/child", root / "stop-preparations/child",
                              root / "xma-preparations/child", driver.SOURCE / "runs",
                              driver.ROOT / "tools/runs", driver.ROOT / "config/runs"):
                with self.subTest(path=requested), self.assertRaises(ValueError):
                    driver.output_directory(root, sdk, receipt, requested)
            self.assertEqual({p.relative_to(root) for p in root.rglob("*")}, before)
            requested = root / "allocation-contract-runs"
            output = driver.output_directory(root, sdk, receipt, requested)
            self.assertEqual(output.parent, requested.resolve())
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
