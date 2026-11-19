# SPDX-License-Identifier: GPL-3.0-only
"""Synthetic protocol/path guards; no SDL, SDK or physical device is loaded."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("input_ingress_driver", ROOT / "tools/test_input_ingress.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
NONCE = "a" * 32


def record(case="held"):
    cycles = 24 if case == "orders" else 2 if case == "restart" else 1
    created = 5 if case == "hotplug" else cycles * 4
    return dict(schema=1, case=case, nonce=NONCE, cycles=cycles, created=created, cleaned=created,
                owners=4, connected_after=0, sources_after=0, pending=0, sdl_init_after=0,
                sdl_version=3004014, checks=100, loaded=dict(provider="/private/provider", sdl="/private/sdl", base="/private/base"))


def output(value, prefix=driver.PREFIX):
    policy = "MW3_INGRESS_POLICY:guide_pending=1 release_ms=250 source_released=1\n" if value.get("case") == "control-map" else ""
    return policy + prefix + json.dumps(value) + "\n"


class IngressEvidenceTests(unittest.TestCase):
    def test_all_cases_require_exact_owner_and_cleanup_records(self):
        for case in driver.CASES:
            value = record(case)
            self.assertEqual(driver.classify(case, NONCE, 0, output(value)), value)
            for field in ("cycles", "created", "cleaned", "owners", "connected_after", "sources_after", "pending", "sdl_init_after"):
                changed = copy.deepcopy(value); changed[field] += 1
                with self.subTest(case=case, field=field):
                    self.assertIsNone(driver.classify(case, NONCE, 0, output(changed)))

    def test_nonzero_partial_late_and_duplicate_output_cannot_pass(self):
        text = output(record())
        for code in (1, 2, -11, -999, 71): self.assertIsNone(driver.classify("held", NONCE, code, text))
        for wrong in ("", "PASS", text[:-3], " " + text, text * 2):
            self.assertIsNone(driver.classify("held", NONCE, 0, wrong))

    def test_schema_counts_versions_and_checks_do_not_coerce_types(self):
        for field in ("schema", "cycles", "created", "cleaned", "owners", "connected_after", "sources_after", "pending", "sdl_init_after", "sdl_version", "checks"):
            for wrong in (True, "1", 1.0, None, -1):
                value = record(); value[field] = wrong
                with self.subTest(field=field, wrong=wrong):
                    self.assertIsNone(driver.classify("held", NONCE, 0, output(value)))
        value = record(); value["extra"] = 1
        self.assertIsNone(driver.classify("held", NONCE, 0, output(value)))
        value = record(); del value["owners"]
        self.assertIsNone(driver.classify("held", NONCE, 0, output(value)))

    def test_stale_case_nonce_duplicate_keys_and_unknown_context_reject(self):
        text = output(record())
        self.assertIsNone(driver.classify("orders", NONCE, 0, text))
        self.assertIsNone(driver.classify("held", "b" * 32, 0, text))
        changed = text.replace('"owners": 4', '"owners": 0, "owners": 4')
        self.assertIsNone(driver.classify("held", NONCE, 0, changed))
        for case, nonce in (("unknown", NONCE), ("held", "bad")):
            with self.assertRaises(ValueError): driver.classify(case, nonce, 0, text)

    def test_sanitizer_and_failure_markers_override_complete_output(self):
        for marker in ("AddressSanitizer", "LeakSanitizer", "runtime error:", "MW3_INGRESS_FAILURE:bad input"):
            self.assertIsNone(driver.classify("held", NONCE, 0, output(record()) + marker))

    def test_guide_release_policy_is_observed_and_bounded(self):
        text = output(record("control-map")); line = text.splitlines()[0] + "\n"
        self.assertEqual(driver.guide_policy(text), dict(guide_pending=1, release_ms=250, source_released=1))
        for wrong in (text.replace(line, ""), text + line, text.replace("guide_pending=1", "guide_pending=2"),
                      text.replace("release_ms=250", "release_ms=1001"), text.replace("source_released=1", "source_released=0")):
            self.assertIsNone(driver.classify("control-map", NONCE, 0, wrong))

    def test_negative_control_requires_exact_failure_and_validated_cleanup(self):
        text = output(record(), driver.REJECTED) + "MW3_INGRESS_FAILURE:deliberate wrong-route rejected\n"
        self.assertEqual(driver.rejected(NONCE, 1, text), record())
        self.assertIsNone(driver.classify("held", NONCE, 0, text))
        for code, wrong in ((0, text), (-11, text), (-999, text), (1, "MW3_INGRESS_FAILURE:deliberate wrong-route rejected\n"),
                            (1, text + text), (1, text + output(record())), (1, text + "AddressSanitizer"),
                            (1, text.replace("deliberate wrong-route rejected", "unrelated error")),
                            (1, text.replace('"cleaned": 4', '"cleaned": 3'))):
            self.assertIsNone(driver.rejected(NONCE, code, wrong))

    def test_loader_records_are_exact_nonce_bound_and_not_coerced(self):
        value = dict(schema=1, nonce=NONCE, loaded=record()["loaded"])
        text = output(value, driver.LOADED)
        self.assertEqual(driver.loading(NONCE, text), value)
        for wrong in ("", text * 2, text.replace('"schema": 1', '"schema": true'),
                      text.replace('"schema": 1', '"schema": 0, "schema": 1')):
            self.assertIsNone(driver.loading(NONCE, wrong))
        self.assertIsNone(driver.loading("b" * 32, text))
        self.assertIsNone(driver.loading("bad", text.replace(NONCE, "bad")))

    def test_all_library_roles_require_nonempty_single_line_paths(self):
        for wrong in ({}, None, [], dict(provider="x", sdl="y"), dict(provider="", sdl="y", base="z"),
                      dict(provider="x\ny", sdl="y", base="z")):
            value = record(); value["loaded"] = wrong
            self.assertIsNone(driver.classify("held", NONCE, 0, output(value)))

    def test_library_paths_must_be_from_verified_sdk(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory) / "sdk"; folder = sdk / ("bin" if os.name == "nt" else "lib"); folder.mkdir(parents=True)
            value = record()
            for role, name in (("provider", "rexhid-sdl3"), ("sdl", "SDL3"), ("base", "rexbase")):
                path = folder / (name + ".dll" if os.name == "nt" else "lib" + name + ".so" + (".0" if role == "sdl" else ""))
                path.write_bytes(b"original synthetic library fixture"); value["loaded"][role] = str(path)
            self.assertEqual(set(driver.loaded_identity(value, sdk, os.name == "nt")), {"provider", "sdl", "base"})
            other = Path(directory) / "other-provider"; other.write_bytes(b"original synthetic library fixture")
            value["loaded"]["provider"] = str(other)
            with self.assertRaisesRegex(ValueError, "unexpected loaded"): driver.loaded_identity(value, sdk, os.name == "nt")

    def test_output_cannot_overlap_sdk_preparation_or_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "cache"; receipt = root / "input-preparations/run/manifest.json"; sdk = receipt.parent / "sdk"
            for destination in (root, sdk, sdk / "output", receipt.parent / "output", root / "sources", root / "sources/child"):
                with self.subTest(destination=destination), self.assertRaises(ValueError):
                    driver.output_root(root, receipt, sdk, destination)
                self.assertFalse(destination.exists())
            valid = Path(directory) / "exclusive-output"
            self.assertEqual(driver.output_root(root, receipt, sdk, valid), valid.resolve())
            self.assertFalse(valid.exists())

    def test_bad_sdk_identity_stops_before_output_or_build(self):
        args = [driver.__file__, "--root", "private", "--sdk-report", "bad", "--output-root", "never-created"]
        with patch.object(sys, "argv", args), patch.object(driver.input_profile, "verify_prepared", side_effect=ValueError("changed identity")), \
             patch.object(driver.common, "private_cache", side_effect=AssertionError("must not create outputs")), \
             patch.object(subprocess, "run", side_effect=AssertionError("must not build")):
            with self.assertRaises(SystemExit) as error: driver.main()
            self.assertEqual(error.exception.code, 2)

    def test_real_incomplete_and_late_owned_children_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "run.log"
            code = driver.run_process([sys.executable, "-c", "print('incomplete')"], cwd=directory, env=dict(os.environ), log=log, timeout=10)
            self.assertIsNone(driver.classify("held", NONCE, code, log.read_text()))
            script = "import time;print(" + repr(output(record())) + ",flush=True);time.sleep(10)"
            code = driver.run_process([sys.executable, "-c", script], cwd=directory, env=dict(os.environ), log=log, timeout=0.3)
            self.assertEqual(code, -999)
            self.assertIsNone(driver.classify("held", NONCE, code, log.read_text()))
