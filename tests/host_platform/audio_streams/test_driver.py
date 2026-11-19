# SPDX-License-Identifier: GPL-3.0-only
"""Evidence mutations only; these fixtures do not load an SDK or certify audio."""
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
spec = importlib.util.spec_from_file_location("audio_streams_driver", ROOT / "tools/test_audio_streams.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
NONCE = "2" * 32


def records(names=("reuse",), mode="timer"):
    libs = dict(nonce=NONCE, mode=mode, backend="dummy" if mode == "sdl" else "none",
                loaded={key: "/private/" + value for key, value in driver.audio.ROLES.items()})
    if mode == "timer": libs["loaded"]["provider"] = None
    value = dict(schema=1, nonce=NONCE, mode=mode, backend=libs["backend"], channels=6 if mode == "sdl" else 2,
                 threads_before=0, threads_after=0, open_after=0, queued_after=0, sdl_audio_after=0, cases=[])
    for name in names:
        row = dict(name=name, status="PASS", reason="", checks=200, opens=0, closes=0, sdk_submits=0,
                   valid_submits=0, credits=0, stale_blocks=0, owner_blocks=0, instance_blocks=0, frame_blocks=0,
                   queue_refusals=0, raw_checked=False, raw_stale_accepted=False, raw_old=0, raw_new=0,
                   elapsed_us=100, accepted_ns=[], rejected_ns=[], raw_ns=[])
        if name == "reuse":
            row.update(opens=6, closes=6, sdk_submits=5, valid_submits=3, credits=3, stale_blocks=1,
                       raw_checked=True, raw_stale_accepted=True, raw_old=2, raw_new=2, raw_ns=[100, 100])
        elif name == "owners":
            row.update(opens=3, closes=3, sdk_submits=2, valid_submits=2, credits=2, stale_blocks=1, owner_blocks=1, instance_blocks=1)
        elif name == "queue":
            row.update(opens=2, closes=2, sdk_submits=7, valid_submits=6, credits=6, frame_blocks=2, queue_refusals=1)
        else:
            row.update(opens=64, closes=64, sdk_submits=160, valid_submits=160, credits=32, stale_blocks=32)
        row["accepted_ns"] = [100] * row["valid_submits"]
        row["rejected_ns"] = [100] * sum(row[k] for k in ("stale_blocks", "owner_blocks", "instance_blocks", "frame_blocks"))
        value["cases"].append(row)
    return libs, value


def output(pair):
    return driver.audio.LIBRARIES + json.dumps(pair[0]) + "\n" + driver.COMPLETE + json.dumps(pair[1]) + "\n"


class OwnershipEvidenceTests(unittest.TestCase):
    def test_valid_modes_case_orders_and_raw_baseline_is_not_sdk_repair(self):
        for mode in ("timer", "sdl"):
            for names in (driver.CASES, driver.CASES[::-1], *((name,) for name in driver.CASES)):
                result = driver.classify(names, mode, NONCE, 0, output(records(names, mode)))
                self.assertEqual(result["status"], "PASS")
        pair = records(); pair[1]["cases"][0]["raw_stale_accepted"] = False
        self.assertIsNone(driver.classify(("reuse",), "timer", NONCE, 0, output(pair)))

    def test_partial_stale_duplicate_nonzero_and_crash_never_pass(self):
        text = output(records())
        for code in (-11, -999, 1, 2, 42, 43):
            self.assertIsNone(driver.classify(("reuse",), "timer", NONCE, code, text))
        for bad in ("", text[:-3], text * 2, " " + text, text + "AddressSanitizer", text + "MW3_AUDIO_GATE_FATAL:bad"):
            self.assertIsNone(driver.classify(("reuse",), "timer", NONCE, 0, bad))
        self.assertIsNone(driver.classify(("owners",), "timer", NONCE, 0, text))
        self.assertIsNone(driver.classify(("reuse",), "sdl", NONCE, 0, text))
        self.assertIsNone(driver.classify(("reuse",), "timer", "3" * 32, 0, text))
        for args in (((), "timer", NONCE), (("unknown",), "timer", NONCE), (("reuse",), "timer", "bad")):
            with self.assertRaises(ValueError): driver.classify(*args, 0, "")
        duplicated = text.replace('"schema": 1', '"schema": 0, "schema": 1')
        self.assertIsNone(driver.classify(("reuse",), "timer", NONCE, 0, duplicated))

    def test_typed_metrics_bounds_and_resource_mismatches(self):
        for key in ("schema", "channels", "threads_before", "threads_after", "open_after", "queued_after", "sdl_audio_after"):
            for invalid in (True, -1, 1.0, "0", None):
                pair = records(); pair[1][key] = invalid
                self.assertIsNone(driver.classify(("reuse",), "timer", NONCE, 0, output(pair)))
        for key in ("checks", "opens", "closes", "sdk_submits", "valid_submits", "credits", "stale_blocks", "elapsed_us"):
            for invalid in (True, -1, 1.0, "1", None):
                pair = records(); pair[1]["cases"][0][key] = invalid
                self.assertIsNone(driver.classify(("reuse",), "timer", NONCE, 0, output(pair)))
        for key in ("raw_checked", "raw_stale_accepted"):
            pair = records(); pair[1]["cases"][0][key] = 1
            self.assertIsNone(driver.classify(("reuse",), "timer", NONCE, 0, output(pair)))
        for key in ("threads_after", "open_after", "queued_after", "sdl_audio_after"):
            pair = records(); pair[1][key] = 1
            self.assertIsNone(driver.classify(("reuse",), "timer", NONCE, 0, output(pair)))
        pair = records(mode="sdl"); pair[1]["channels"] = 2
        self.assertIsNone(driver.classify(("reuse",), "sdl", NONCE, 0, output(pair)))

    def test_sdk_call_credit_baseline_and_case_accounting_rejected(self):
        fields = {"reuse": {"sdk_submits": 6, "credits": 4, "raw_new": 3, "closes": 5},
                  "owners": {"owner_blocks": 0, "instance_blocks": 0, "sdk_submits": 3},
                  "queue": {"queue_refusals": 0, "sdk_submits": 6, "frame_blocks": 1},
                  "lifecycle": {"valid_submits": 159, "stale_blocks": 31, "opens": 63}}
        for name, changes in fields.items():
            for key, invalid in changes.items():
                pair = records((name,)); pair[1]["cases"][0][key] = invalid
                self.assertIsNone(driver.classify((name,), "timer", NONCE, 0, output(pair)))
        for key in ("accepted_ns", "rejected_ns", "raw_ns"):
            for invalid in ([True], [-1], [1.0], [0] * 513):
                pair = records(); pair[1]["cases"][0][key] = invalid
                self.assertIsNone(driver.classify(("reuse",), "timer", NONCE, 0, output(pair)))
        for target in ("top", "case"):
            pair = records(); value = pair[1] if target == "top" else pair[1]["cases"][0]
            value["extra"] = 1
            self.assertIsNone(driver.classify(("reuse",), "timer", NONCE, 0, output(pair)))

    def test_real_failure_stays_failure_and_controls_are_exact(self):
        pair = records(); pair[1]["cases"][0].update(status="FAIL", reason="stale command reached SDK")
        result = driver.classify(("reuse",), "timer", NONCE, 42, output(pair))
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(driver.control("wrong-result", "timer", NONCE, 42, output(pair)))
        pair[1]["cases"][0]["reason"] = "deliberate-wrong-result"
        self.assertTrue(driver.control("wrong-result", "timer", NONCE, 42, output(pair)))
        pair[1]["cases"][0]["sdk_submits"] = 6
        self.assertFalse(driver.control("wrong-result", "timer", NONCE, 42, output(pair)))

    def test_incomplete_control_requires_real_identity_and_no_completion(self):
        libs, _ = records()
        text = driver.audio.LIBRARIES + json.dumps(libs) + "\nMW3_AUDIO_GATE_INCOMPLETE:" + NONCE + "\n"
        self.assertTrue(driver.control("incomplete", "timer", NONCE, 43, text))
        for code, bad in ((0, text), (-999, text), (43, text * 2), (43, text + output(records())), (43, "")):
            self.assertFalse(driver.control("incomplete", "timer", NONCE, code, bad))

    def test_owned_child_timeout_after_plausible_output_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "run.log"
            script = "import time; print(" + repr(output(records())) + ", flush=True); time.sleep(10)"
            code = driver.audio.run_process([sys.executable, "-c", script], cwd=directory,
                                           env=dict(os.environ), log=log, timeout=0.3)
            self.assertEqual(code, -999)
            self.assertIsNone(driver.classify(("reuse",), "timer", NONCE, code, log.read_text()))

    def test_unapproved_package_stops_before_output_or_build(self):
        args = ["test_audio_streams.py", "--root", "unused", "--sdk-report", "bad", "--output-root", "never-created"]
        with patch.object(sys, "argv", args), \
             patch.object(driver.audio.storage, "verify_package", side_effect=ValueError("unapproved package")), \
             patch.object(driver.common, "private_cache", side_effect=AssertionError("must not create output")), \
             patch.object(subprocess, "run", side_effect=AssertionError("must not build")):
            with self.assertRaises(SystemExit) as error: driver.main()
            self.assertEqual(error.exception.code, 2)
