# SPDX-License-Identifier: GPL-3.0-only
"""Game-free receipt/admission guards; SDK parent identities below are synthetic."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import prepare_runtime_input as profile
import test_input_users as users
import test_sdk_input as raw

spec = importlib.util.spec_from_file_location("snapshot_lifecycle", Path(__file__).with_name("run.py"))
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class InputProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sdk = self.root / "sdk"
        self.name = profile.replacement(os.name == "nt")
        provider = self.sdk / self.name
        provider.parent.mkdir(parents=True)
        provider.write_bytes(b"original synthetic parent provider")
        (self.sdk / "unchanged.txt").write_text("original synthetic unaffected artifact")
        parent_files = profile.memory.package_files(self.sdk)
        provider.write_bytes(b"original synthetic derived provider")
        self.lock_file = self.root / "lock.json"
        self.lock_file.write_text("original synthetic lock")
        self.patch_file = self.root / "snapshot.patch"
        self.patch_file.write_text("original synthetic patch")
        self.baseline = self.root / "parent.json"
        self.compiler = dict(sha256="a" * 64, version="synthetic compiler")
        self.baseline.write_text(json.dumps(dict(compiler=self.compiler)))
        (self.root / "compile_commands.json").write_text("[]")
        self.parent = dict(core_sanitizers=False, sdk_files=parent_files)
        self.source = {"synthetic-source": {"sha256": "b" * 64}}
        files = profile.memory.package_files(self.sdk)
        self.receipt = dict(status="PASS", profile="input-snapshot-v1",
            script_sha256=profile.common.sha(profile.__file__), lock_sha256=profile.common.sha(self.lock_file),
            patch_sha256=profile.common.sha(self.patch_file), core_sanitizers=False, provider_sanitizers=False,
            baseline_report=str(self.baseline), baseline_report_sha256=profile.common.sha(self.baseline),
            baseline_identity=self.parent, compiler=self.compiler, derived_source=self.source,
            sdk_prefix=str(self.sdk), sdk_files=files, replaced_files={self.name: files[self.name]["sha256"]},
            compile_commands_sha256=profile.common.sha(self.root / "compile_commands.json"))
        self.report = self.root / "manifest.json"
        for context in (patch.object(profile, "LOCK", self.lock_file),
                        patch.object(profile, "configuration", return_value=({"profile": "input-snapshot-v1"}, self.patch_file)),
                        patch.object(profile.xma, "verify_prepared", return_value=(self.root / "parent-sdk", self.parent)),
                        patch.object(profile, "verify_source", return_value=self.source)):
            context.start(); self.addCleanup(context.stop)

    def verify(self, allow=False):
        self.report.write_text(json.dumps(self.receipt))
        return profile.verify_prepared(self.root, self.report, allow_sanitized=allow)

    def test_valid_package_has_exactly_one_replaced_provider(self):
        sdk, identity = self.verify()
        self.assertEqual(sdk, self.sdk)
        self.assertEqual(identity["baseline"], self.parent)

    def test_stale_script_lock_patch_or_compiler_is_rejected(self):
        original = copy.deepcopy(self.receipt)
        for key in ("script_sha256", "lock_sha256", "patch_sha256", "compiler"):
            self.receipt = copy.deepcopy(original); self.receipt[key] = "changed"
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify()

    def test_changed_parent_receipt_and_identity_are_rejected(self):
        self.baseline.write_text("changed parent")
        with self.assertRaisesRegex(ValueError, "parent receipt"): self.verify()
        self.receipt["baseline_report_sha256"] = profile.common.sha(self.baseline)
        self.receipt["baseline_identity"] = {}
        with self.assertRaisesRegex(ValueError, "parent/instrumentation"): self.verify()

    def test_changed_provider_and_unaffected_artifacts_are_rejected(self):
        for name in (self.name, "unchanged.txt"):
            path = self.sdk / name; saved = path.read_bytes()
            path.write_bytes(b"unexpected bytes")
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "artifact changed"): self.verify()
            path.write_bytes(saved)

    def test_rewriting_receipt_cannot_expand_replacement_allowlist(self):
        path = self.sdk / "unchanged.txt"; path.write_text("unexpected replacement")
        self.receipt["sdk_files"] = profile.memory.package_files(self.sdk)
        for widened in (False, True):
            if widened: self.receipt["replaced_files"]["unchanged.txt"] = profile.common.sha(path)
            with self.subTest(widened=widened), self.assertRaisesRegex(ValueError, "artifact changed"): self.verify()

    def test_baseline_provider_cannot_masquerade_as_repaired(self):
        (self.sdk / self.name).write_bytes(b"original synthetic parent provider")
        files = profile.memory.package_files(self.sdk)
        self.receipt.update(sdk_files=files, replaced_files={self.name: files[self.name]["sha256"]})
        with self.assertRaisesRegex(ValueError, "artifact changed"): self.verify()

    def test_instrumentation_requires_matching_parent_and_explicit_opt_in(self):
        self.receipt.update(core_sanitizers=True, provider_sanitizers=True)
        self.parent["core_sanitizers"] = True
        with self.assertRaisesRegex(ValueError, "validation-only"): self.verify()
        self.verify(allow=True)
        self.receipt["provider_sanitizers"] = False
        with self.assertRaises(ValueError): self.verify(allow=True)

    def test_changed_compile_commands_are_rejected(self):
        (self.root / "compile_commands.json").write_text('["changed configuration"]')
        with self.assertRaisesRegex(ValueError, "compile commands"): self.verify()

    def test_source_recipe_missing_extra_and_changed_files_are_rejected(self):
        source = self.root / "source"
        for name in (profile.CPP, profile.HEADER, "CMakeLists.txt"):
            path = source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("original synthetic " + name)
        lock = dict(derived_source_sha256=profile.common.sha(source / profile.CPP),
                    source_files={profile.HEADER: profile.common.sha(source / profile.HEADER)})
        (self.root / "CMakeLists.txt").write_bytes((source / "CMakeLists.txt").read_bytes())
        with patch.object(profile, "verify_source", wraps=self._original_verify_source):
            profile.verify_source(source, lock)
            extra = source / "extra"; extra.write_text("unexpected")
            with self.assertRaises(ValueError): profile.verify_source(source, lock)
            extra.unlink()
            saved = (source / profile.CPP).read_bytes()
            (source / profile.CPP).write_text("unexpected source")
            with self.assertRaises(ValueError): profile.verify_source(source, lock)
            (source / profile.CPP).write_bytes(saved)
            (source / profile.HEADER).unlink()
            with self.assertRaises(ValueError): profile.verify_source(source, lock)

    _original_verify_source = staticmethod(profile.verify_source)

    def test_configuration_binds_patch_parent_and_exact_source_set(self):
        folder = self.root / "configuration"; folder.mkdir()
        original = ROOT / "config/toolchains/rexglue-input-snapshot"
        lock = json.loads((original / "lock.json").read_text())
        (folder / "snapshot.patch").write_bytes((original / "snapshot.patch").read_bytes())
        parent = self.root / "xma-lock.json"
        parent.write_bytes(profile.xma.LOCK.read_bytes())
        lock_path = folder / "lock.json"
        with patch.object(profile, "configuration", wraps=self._original_configuration), \
             patch.object(profile, "LOCK", lock_path), patch.object(profile.xma, "LOCK", parent):
            lock_path.write_text(json.dumps(lock)); profile.configuration()
            for key, value in (("patch_sha256", "wrong"), ("parent_xma_lock_sha256", "wrong"),
                               ("commit", "wrong"), ("source_files", {})):
                changed = copy.deepcopy(lock); changed[key] = value
                lock_path.write_text(json.dumps(changed))
                with self.subTest(key=key), self.assertRaises(ValueError): profile.configuration()

    _original_configuration = staticmethod(profile.configuration)

    def test_lifecycle_requires_complete_nonce_bound_cleanup(self):
        nonce = "a" * 32
        value = dict(schema=1, case="pending-live", nonce=nonce, created=5, cleaned=5,
                     pending=0, sdl_init_after=0, checks=80,
                     loaded=dict(provider="/private/provider", sdl="/private/sdl", base="/private/base"))
        text = lifecycle.PREFIX + json.dumps(value) + "\n"
        self.assertEqual(lifecycle.classify("pending-live", nonce, 0, text), value)
        for key, wrong in (("cleaned", 4), ("pending", 1), ("nonce", "b" * 32),
                           ("created", True), ("loaded", {}), ("checks", 0)):
            changed = copy.deepcopy(value); changed[key] = wrong
            with self.subTest(key=key):
                self.assertIsNone(lifecycle.classify("pending-live", nonce, 0, lifecycle.PREFIX + json.dumps(changed)))
        for code, wrong in ((1, text), (-999, text), (0, ""), (0, text * 2),
                            (0, text + "AddressSanitizer"), (0, text + "MW3_SNAPSHOT_FAILURE:cleanup")):
            self.assertIsNone(lifecycle.classify("pending-live", nonce, code, wrong))

    def test_runner_profile_selection_is_explicit_and_default_is_xma(self):
        for driver in (users, raw):
            for selected in (None, "input"):
                args = [driver.__file__, "--root", "private", "--sdk-report", "bad", "--output-root", "never-created"]
                if selected: args += ["--sdk-profile", selected]
                chosen = driver.input_profile if selected else driver.xma
                other = driver.xma if selected else driver.input_profile
                with self.subTest(driver=driver.__name__, selected=selected), patch.object(sys, "argv", args), \
                     patch.object(chosen, "verify_prepared", side_effect=ValueError("rejected identity")) as verify, \
                     patch.object(other, "verify_prepared", side_effect=AssertionError("wrong profile")), \
                     patch.object(driver.common, "private_cache", side_effect=AssertionError("must not create outputs")):
                    with self.assertRaises(SystemExit) as error: driver.main()
                    self.assertEqual(error.exception.code, 2); verify.assert_called_once()
