# SPDX-License-Identifier: GPL-3.0-only
"""Synthetic receipt/isolation guards; actual kernel execution is a private matrix."""
import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import prepare_runtime_memory_imports as profile


class PreparationGuards(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = self.root / "attempt"
        self.output.mkdir()
        self.sdk = self.output / "sdk"
        self.name = profile.replacement(sys.platform == "win32")
        self.library = self.sdk / self.name
        self.library.parent.mkdir(parents=True)
        self.library.write_bytes(b"synthetic repaired kernel identity")
        self.unaffected = self.sdk / "include/unchanged.h"
        self.unaffected.parent.mkdir(parents=True)
        self.unaffected.write_bytes(b"unchanged parent header")
        self.compiler = {"version": "synthetic test compiler", "sha256": "c" * 64}
        self.baseline = self.root / "parent.json"
        self.baseline.write_text(json.dumps({"compiler": self.compiler}))
        files = profile.memory.package_files(self.sdk)
        self.parent = {"core_sanitizers": False, "sdk_files": copy.deepcopy(files)}
        self.parent["sdk_files"][self.name]["sha256"] = "b" * 64
        self.identity = {"base_commit": "synthetic", "derived_tree": "verified tree"}
        for name in ("compile_commands.json", "configure.log", "build.log"):
            (self.output / name).write_text("original synthetic " + name)
        self.report_path = self.output / "manifest.json"
        self.receipt = dict(
            schema_version=1, status="PASS", profile="memory-imports-v1",
            owned_title_executed=False, release_package=False, core_sanitizers=False,
            script_sha256=profile.common.sha(profile.__file__), helper_sha256=profile.helpers(),
            memory_imports_lock_sha256=profile.common.sha(profile.LOCK),
            baseline_report=str(self.baseline), baseline_report_sha256=profile.common.sha(self.baseline),
            baseline_identity=copy.deepcopy(self.parent), compiler=self.compiler,
            source=self.identity, sdk_prefix=str(self.sdk), sdk_files=files,
            replaced_files={self.name: files[self.name]["sha256"]},
            compile_commands_sha256=profile.common.sha(self.output / "compile_commands.json"),
            log_sha256={n: profile.common.sha(self.output / n) for n in ("configure.log", "build.log")})
        for target, replacement in ((profile.parent_profile, "verify_prepared"), (profile, "source_identity"),
                                    (profile, "compiler_identity")):
            value = ((self.root / "parent-sdk", self.parent) if replacement == "verify_prepared" else
                     self.identity if replacement == "source_identity" else self.compiler)
            self.enterContext(patch.object(target, replacement, return_value=value))

    def verify(self, receipt=None, allow=False):
        self.report_path.write_text(json.dumps(self.receipt if receipt is None else receipt))
        return profile.verify_prepared(self.root, self.report_path, allow_sanitized=allow)

    def test_coherent_receipt_requires_a_changed_kernel_and_identical_other_files(self):
        sdk, evidence = self.verify()
        self.assertEqual(sdk, self.sdk)
        self.assertEqual(evidence["sdk_files"], self.receipt["sdk_files"])
        self.assertFalse(evidence["core_sanitizers"])
        self.unaffected.write_bytes(b"changed parent header")
        with self.assertRaises(ValueError):
            self.verify()
        self.unaffected.write_bytes(b"unchanged parent header")
        self.parent["sdk_files"][self.name] = copy.deepcopy(self.receipt["sdk_files"][self.name])
        value = copy.deepcopy(self.receipt)
        value["baseline_identity"] = copy.deepcopy(self.parent)
        with self.assertRaises(ValueError):
            self.verify(value)

    def test_missing_changed_or_unlisted_package_artifacts_reject(self):
        self.verify()
        self.library.write_bytes(b"mutated kernel")
        with self.assertRaises(ValueError):
            self.verify()
        self.library.unlink()
        with self.assertRaises((ValueError, KeyError)):
            self.verify()
        self.library.write_bytes(b"synthetic repaired kernel identity")
        (self.sdk / "unexpected.bin").write_bytes(b"unexpected")
        with self.assertRaises(ValueError):
            self.verify()

    def test_receipt_identity_mutations_cannot_admit_a_package(self):
        self.verify()
        mutations = dict(schema_version=True, status="IN_PROGRESS", profile="other",
                         owned_title_executed=True, release_package=True, core_sanitizers=0,
                         script_sha256="0" * 64, memory_imports_lock_sha256="0" * 64,
                         helper_sha256={}, baseline_report_sha256="0" * 64, baseline_identity={},
                         compiler={"version": "wrong"}, source={"derived_tree": "wrong"},
                         sdk_files={}, replaced_files={}, compile_commands_sha256="0" * 64,
                         log_sha256={})
        for field, value in mutations.items():
            with self.subTest(field=field):
                changed = copy.deepcopy(self.receipt)
                changed[field] = value
                with self.assertRaises((ValueError, KeyError)):
                    self.verify(changed)

    def test_current_compiler_and_preparation_artifacts_are_rechecked(self):
        self.verify()
        with patch.object(profile, "compiler_identity", return_value={"version": "different"}):
            with self.assertRaises(ValueError):
                self.verify()
        for name in ("compile_commands.json", "configure.log", "build.log"):
            with self.subTest(name=name):
                path = self.output / name
                before = path.read_bytes()
                path.write_bytes(before + b"changed")
                with self.assertRaises(ValueError):
                    self.verify()
                path.write_bytes(before)

    def test_core_instrumentation_is_explicit_and_cannot_mismatch_parent(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["core_sanitizers"] = True
        with self.assertRaises(ValueError):
            self.verify(receipt)
        with self.assertRaises(ValueError):
            self.verify(receipt, allow=True)
        self.parent["core_sanitizers"] = True
        receipt["baseline_identity"] = copy.deepcopy(self.parent)
        self.verify(receipt, allow=True)

    def test_invalid_parent_is_rejected_before_creating_an_attempt(self):
        args = ["prepare", "--root", str(self.root), "--baseline-report", str(self.baseline)]
        with patch.object(sys, "argv", args), patch.object(profile.parent_profile, "verify_prepared",
                side_effect=ValueError("invalid parent")), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                profile.main()
        self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.root / "memory-imports-preparations").exists())

    def test_changed_patch_parent_lock_or_license_rejects_composition(self):
        folder = self.root / "config"
        shutil.copytree(profile.LOCK.parent, folder)
        with patch.object(profile, "LOCK", folder / "lock.json"):
            profile.composition(sys.platform == "win32")
            for name in ("in-out-words.patch", "LICENSE.ReXGlue"):
                path = folder / name
                before = path.read_bytes()
                path.write_bytes(before + b"changed")
                with self.assertRaises(ValueError):
                    profile.composition(sys.platform == "win32")
                path.write_bytes(before)
            value = json.loads(profile.LOCK.read_text())
            value["parent_xma_lock_sha256"] = "0" * 64
            profile.LOCK.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                profile.composition(sys.platform == "win32")
