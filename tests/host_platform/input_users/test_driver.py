# SPDX-License-Identifier: GPL-3.0-only
"""Synthetic evidence guards; these tests do not load SDL or an SDK."""
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
spec = importlib.util.spec_from_file_location("input_users_driver", ROOT / "tools/test_input_users.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
NONCE = "4" * 32


def record(case="users"):
    cycles = 24 if case == "orders" else 1
    created = 0 if case == "fallback" else 5 if case == "hotplug" else 4 * cycles
    routed = 0 if case == "fallback" else 1 if case == "shared" else 4
    return dict(schema=1, case=case, nonce=NONCE, cycles=cycles, created=created, cleaned=created,
                routed_users=routed, readable_users=1 if case == "fallback" else routed,
                pending=0, blocks=0, sdl_init_after=0, checks=100, sdl_version=3004014,
                loaded=dict(input="/private/input", provider="/private/provider", sdl="/private/sdl", base="/private/base"))


def output(value):
    return driver.PREFIX + json.dumps(value) + "\n"


class InputEvidenceTests(unittest.TestCase):
    def test_fallback_and_shared_policies_cannot_fabricate_four_users(self):
        for case in ("fallback", "shared"):
            value = record(case)
            self.assertIsNotNone(driver.classify(case, NONCE, 0, output(value)))
            for key in ("routed_users", "readable_users"):
                changed = copy.deepcopy(value); changed[key] = 4
                self.assertIsNone(driver.classify(case, NONCE, 0, output(changed)))

    def test_retained_discovery_gap_is_never_a_correctness_pass(self):
        text = ("MW3_USERS_READING:user=0 product=3 buttons=0 x=0 expected_buttons=16384 source_button=1 source_x=3072\n"
                "MW3_USERS_FAILURE:independent user state routed incorrectly\n")
        self.assertTrue(driver.known_discovery_gap(1, text))
        self.assertIsNone(driver.classify("held-discovery", NONCE, 1, text))
        for code, changed in ((0, text), (-999, text), (-11, text),
                              (1, text.replace("source_button=1", "source_button=0")),
                              (1, text.replace("source_x=3072", "source_x=0")),
                              (1, text.replace("expected_buttons=16384", "expected_buttons=4096")),
                              (1, text + text), (1, text + output(record("held-discovery"))),
                              (1, text + "AddressSanitizer")):
            self.assertFalse(driver.known_discovery_gap(code, changed))

    def test_loader_identity_record_is_exact_and_nonce_bound(self):
        value = dict(schema=1, nonce=NONCE, loaded=record()["loaded"])
        text = "MW3_USERS_LOADED:" + json.dumps(value) + "\n"
        self.assertEqual(driver.loading(NONCE, text), value)
        self.assertIsNone(driver.loading("5" * 32, text))
        self.assertIsNone(driver.loading(NONCE, text + text))
        self.assertIsNone(driver.loading(NONCE, ""))
        changed = copy.deepcopy(value); del changed["loaded"]["input"]
        self.assertIsNone(driver.loading(NONCE, "MW3_USERS_LOADED:" + json.dumps(changed)))
        self.assertIsNone(driver.loading(NONCE, text.replace('"schema": 1', '"schema": true')))
        self.assertIsNone(driver.loading(NONCE, text.replace('"schema": 1', '"schema": 0, "schema": 1')))

    def test_complete_cases_and_reconnect_cleanup(self):
        for case in driver.CASES:
            with self.subTest(case=case):
                value = record(case)
                self.assertEqual(driver.classify(case, NONCE, 0, output(value)), value)

    def test_nonzero_timeout_and_missing_completion_never_pass(self):
        for code in (1, 2, -11, -999, 37):
            self.assertIsNone(driver.classify("users", NONCE, code, output(record())))
        for text in ("", "PASS", output(record())[:-3], " " + output(record())):
            self.assertIsNone(driver.classify("users", NONCE, 0, text))

    def test_stale_duplicate_case_and_nonce_rejected(self):
        self.assertIsNone(driver.classify("users", "5" * 32, 0, output(record())))
        self.assertIsNone(driver.classify("hotplug", NONCE, 0, output(record())))
        self.assertIsNone(driver.classify("users", NONCE, 0, output(record()) * 2))
        for case, nonce in (("unknown", NONCE), ("users", "wrong")):
            with self.assertRaises(ValueError): driver.classify(case, nonce, 0, "")

    def test_wrong_metrics_boolean_and_float_coercions_rejected(self):
        for key in ("schema", "cycles", "created", "cleaned", "routed_users", "readable_users", "pending", "blocks", "sdl_init_after", "sdl_version", "checks"):
            for replacement in (-1, True, 1.0, "1", None):
                value = record(); value[key] = replacement
                with self.subTest(key=key, replacement=replacement):
                    self.assertIsNone(driver.classify("users", NONCE, 0, output(value)))
        for key in ("nonce", "case"):
            value = record(); value[key] = "wrong"
            self.assertIsNone(driver.classify("users", NONCE, 0, output(value)))
        value = record(); value["extra"] = "not in the protocol"
        self.assertIsNone(driver.classify("users", NONCE, 0, output(value)))

    def test_loaded_identity_fields_required(self):
        for loaded in ({}, dict(provider="x", sdl="y"), None, [],
                       dict(provider="", sdl="y", base="z"),
                       dict(provider="x\ny", sdl="y", base="z")):
            value = record(); value["loaded"] = loaded
            self.assertIsNone(driver.classify("users", NONCE, 0, output(value)))

    def test_sanitizer_or_failure_diagnostics_override_completion(self):
        for failure in ("AddressSanitizer", "LeakSanitizer", "runtime error:", "MW3_USERS_FAILURE:bad input"):
            self.assertIsNone(driver.classify("users", NONCE, 0, failure + "\n" + output(record())))

    def test_nonobject_malformed_or_missing_fields_rejected(self):
        for text in ("[]", "null", "123", "{invalid}"):
            self.assertIsNone(driver.classify("users", NONCE, 0, driver.PREFIX + text))
        for key in record():
            value = record(); del value[key]
            self.assertIsNone(driver.classify("users", NONCE, 0, output(value)))

    def test_duplicate_json_fields_rejected(self):
        text = output(record()).replace('"routed_users": 4', '"routed_users": 1, "routed_users": 4')
        self.assertIsNone(driver.classify("users", NONCE, 0, text))
        text = output(record()).replace('"provider": "/private/provider"', '"provider": "wrong", "provider": "/private/provider"')
        self.assertIsNone(driver.classify("users", NONCE, 0, text))

    def test_wrong_result_control_requires_exact_failure_and_exit(self):
        message = "MW3_USERS_FAILURE:deliberate wrong-routing rejected\n"
        self.assertTrue(driver.wrong_result(1, "ordinary SDK log\n" + message))
        for code, text in ((0, message), (-11, message), (-999, message), (1, ""),
                           (1, message * 2), (1, message + output(record())),
                           (1, message + "AddressSanitizer"), (1, "MW3_USERS_FAILURE:setup failed")):
            self.assertFalse(driver.wrong_result(code, text))

    def test_library_path_must_match_verified_package(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory) / "sdk"
            folder = sdk / ("bin" if os.name == "nt" else "lib")
            folder.mkdir(parents=True)
            value = record()
            for role, name in (("input", "rexhid"), ("provider", "rexhid-sdl3"), ("sdl", "SDL3"), ("base", "rexbase")):
                path = folder / (name + ".dll" if os.name == "nt" else "lib" + name + ".so" + (".0" if role == "sdl" else ""))
                path.write_bytes(b"original synthetic library identity fixture")
                value["loaded"][role] = str(path)
            identities = driver.loaded_identity(value, sdk, os.name == "nt")
            self.assertEqual(set(identities), {"input", "provider", "sdl", "base"})
            wrong = copy.deepcopy(value)
            other = Path(directory) / "other-library"
            other.write_bytes(b"original synthetic library identity fixture")
            wrong["loaded"]["provider"] = str(other)
            with self.assertRaisesRegex(ValueError, "unexpected loaded"):
                driver.loaded_identity(wrong, sdk, os.name == "nt")

    def test_incomplete_and_late_owned_processes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "process.log"
            code = driver.run_process([sys.executable, "-c", "print('incomplete')"],
                                      cwd=directory, env=dict(os.environ), log=log, timeout=10)
            self.assertEqual(code, 0)
            self.assertIsNone(driver.classify("users", NONCE, code, log.read_text()))
            script = "import time;print(" + repr(output(record())) + ",flush=True);time.sleep(10)"
            code = driver.run_process([sys.executable, "-c", script], cwd=directory,
                                      env=dict(os.environ), log=log, timeout=0.3)
            self.assertEqual(code, -999)
            self.assertIsNone(driver.classify("users", NONCE, code, log.read_text()))

    def test_bad_sdk_receipt_stops_before_output_or_build(self):
        arguments = ["test_input_users.py", "--root", "private", "--sdk-report", "bad", "--output-root", "never-created"]
        with patch.object(sys, "argv", arguments), \
             patch.object(driver.xma, "verify_prepared", side_effect=ValueError("changed receipt")), \
             patch.object(driver.common, "private_cache", side_effect=AssertionError("must not reach output")), \
             patch.object(subprocess, "run", side_effect=AssertionError("must not build")):
            with self.assertRaises(SystemExit) as error: driver.main()
            self.assertEqual(error.exception.code, 2)
