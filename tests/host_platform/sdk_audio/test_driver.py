# SPDX-License-Identifier: GPL-3.0-only
"""Synthetic evidence-guard tests; these do not load an SDK/audio device."""
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
spec = importlib.util.spec_from_file_location("sdk_audio_driver", ROOT / "tools/test_sdk_audio.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
NONCE = "6" * 32


def records(mode="timer", names=("capacity",)):
    libraries = dict(nonce=NONCE, mode=mode, backend="none" if mode == "timer" else "dummy",
                     loaded={role: "/private/" + name for role, name in driver.ROLES.items()})
    if mode == "timer":
        libraries["loaded"]["provider"] = None
    value = dict(schema=1, nonce=NONCE, mode=mode, backend=libraries["backend"], channels=6 if mode == "sdl" else 2,
                 threads_before=0, threads_after=0, open_after=0, queued_after=0, sdl_audio_after=0, cases=[])
    for name in names:
        row = dict(name=name, status="PASS", reason="", checks=100, opened=8, accepted=0, callbacks=0,
                   queue_peak=0, old_id=0, new_id=0, stale_ok=False, underruns=0, elapsed_us=100, submit_ns=[])
        if name == "identity":
            row.update(opened=3, accepted=1, callbacks=1, old_id=2, new_id=3, submit_ns=[100, 100])
        if name == "queue":
            row.update(opened=2, accepted=5, callbacks=5, queue_peak=4, underruns=1, submit_ns=[100] * 6)
        if name == "lifecycle":
            row.update(opened=64, accepted=160, callbacks=100, queue_peak=4, submit_ns=[100] * 160)
        value["cases"].append(row)
    return libraries, value


def output(pair):
    libraries, value = pair
    return driver.LIBRARIES + json.dumps(libraries) + "\n" + driver.COMPLETE + json.dumps(value) + "\n"


class AudioEvidenceTests(unittest.TestCase):
    def test_complete_modes_and_case_orders(self):
        for mode in driver.MODES:
            for names in (driver.CASES, driver.CASES[::-1], *( (name,) for name in driver.CASES)):
                with self.subTest(mode=mode, names=names):
                    observed = driver.classify(names, mode, NONCE, 0, output(records(mode, names)))
                    self.assertEqual(observed["status"], "PASS")

    def test_crash_timeout_nonzero_and_partial_never_pass(self):
        text = output(records())
        for code in (1, 2, -11, -999, 43, 44, 42):
            self.assertIsNone(driver.classify(("capacity",), "timer", NONCE, code, text))
        for bad in ("", "PASS", text[:-3], " " + text, text + "AddressSanitizer",
                    text + "runtime error: signed overflow", text + "MW3_AUDIO_FATAL:setup"):
            self.assertIsNone(driver.classify(("capacity",), "timer", NONCE, 0, bad))

    def test_duplicate_stale_wrong_mode_case_and_nonce(self):
        text = output(records())
        for bad in (text + text, text.replace('"schema": 1', '"schema": 0, "schema": 1'),
                    text.replace('"audio": "/private/rexapu"', '"audio": "wrong", "audio": "/private/rexapu"')):
            self.assertIsNone(driver.classify(("capacity",), "timer", NONCE, 0, bad))
        self.assertIsNone(driver.classify(("capacity",), "sdl", NONCE, 0, text))
        self.assertIsNone(driver.classify(("capacity",), "timer", "7" * 32, 0, text))
        self.assertIsNone(driver.classify(("queue",), "timer", NONCE, 0, text))
        for args in (((), "timer", NONCE), (("unknown",), "timer", NONCE), (("capacity",), "bad", NONCE),
                     (("capacity",), "timer", "bad")):
            with self.assertRaises(ValueError): driver.classify(*args, 0, "")

    def test_types_resource_accounting_and_unknown_fields(self):
        for key in ("schema", "channels", "threads_before", "threads_after", "open_after", "queued_after", "sdl_audio_after"):
            for wrong in (True, -1, 1.0, "0", None):
                pair = records(); pair[1][key] = wrong
                self.assertIsNone(driver.classify(("capacity",), "timer", NONCE, 0, output(pair)))
        for key in ("checks", "opened", "accepted", "callbacks", "queue_peak", "old_id", "new_id", "underruns", "elapsed_us"):
            for wrong in (True, -1, 1.0, "0", None):
                pair = records(); pair[1]["cases"][0][key] = wrong
                self.assertIsNone(driver.classify(("capacity",), "timer", NONCE, 0, output(pair)))
        for target in ("top", "case", "library"):
            pair = records()
            value = pair[1] if target == "top" else pair[1]["cases"][0] if target == "case" else pair[0]
            value["extra"] = 1
            self.assertIsNone(driver.classify(("capacity",), "timer", NONCE, 0, output(pair)))
        for key, wrong in (("threads_after", 1), ("open_after", 1), ("queued_after", 1), ("sdl_audio_after", 16)):
            pair = records(); pair[1][key] = wrong
            self.assertIsNone(driver.classify(("capacity",), "timer", NONCE, 0, output(pair)))

    def test_case_specific_wrong_output_and_bounds_rejected(self):
        fallback = records("sdl"); fallback[1]["channels"] = 2
        self.assertIsNone(driver.classify(("capacity",), "sdl", NONCE, 0, output(fallback)))
        mutations = {"capacity": {"opened": 7, "callbacks": 1}, "identity": {"stale_ok": True, "callbacks": 2},
                     "queue": {"queue_peak": 5, "callbacks": 4, "underruns": 0},
                     "lifecycle": {"opened": 63, "accepted": 159, "callbacks": 161}}
        for name, fields in mutations.items():
            for key, wrong in fields.items():
                pair = records(names=(name,)); pair[1]["cases"][0][key] = wrong
                self.assertIsNone(driver.classify((name,), "timer", NONCE, 0, output(pair)))
        for wrong in ([True], [-1], [1.0], [0] * 513, [30_000_000_001]):
            pair = records(); pair[1]["cases"][0]["submit_ns"] = wrong
            self.assertIsNone(driver.classify(("capacity",), "timer", NONCE, 0, output(pair)))

    def test_recorded_ownership_failure_stays_failure(self):
        pair = records(names=("identity",))
        pair[1]["cases"][0].update(status="FAIL", reason="stale-stream-id-retargeted-replacement",
                                     old_id=2, new_id=2, stale_ok=True, accepted=2, callbacks=2)
        result = driver.classify(("identity",), "timer", NONCE, 42, output(pair))
        self.assertEqual(result["status"], "FAIL")
        self.assertIsNone(driver.classify(("identity",), "timer", NONCE, 0, output(pair)))
        self.assertFalse(driver.control("wrong-result", "timer", NONCE, 42, output(pair)))

    def test_wrong_result_control_requires_exact_failure(self):
        pair = records(); pair[1]["cases"][0].update(status="FAIL", reason="deliberate-wrong-result")
        text = output(pair)
        self.assertTrue(driver.control("wrong-result", "timer", NONCE, 42, text))
        for code, bad in ((0, text), (-11, text), (-999, text), (42, text * 2), (42, text + "Sanitizer")):
            self.assertFalse(driver.control("wrong-result", "timer", NONCE, code, bad))
        pair[1]["cases"][0]["reason"] = "fixture setup failed"
        self.assertFalse(driver.control("wrong-result", "timer", NONCE, 42, output(pair)))

    def test_incomplete_and_backend_controls_are_narrow(self):
        libraries, _ = records()
        incomplete = driver.LIBRARIES + json.dumps(libraries) + "\nMW3_AUDIO_INCOMPLETE:" + NONCE + "\n"
        self.assertTrue(driver.control("incomplete", "timer", NONCE, 43, incomplete))
        for code, text in ((0, incomplete), (43, incomplete * 2), (43, incomplete + output(records())), (43, "")):
            self.assertFalse(driver.control("incomplete", "timer", NONCE, code, text))
        backend = "MW3_AUDIO_BACKEND_REJECTED:" + json.dumps(dict(nonce=NONCE,
            message="module 'rexapu' failed to init, no audio driver is available", category=12, shutdown=1,
            threads_before=0, threads_after=0, sdl_audio_after=0)) + "\n"
        self.assertTrue(driver.control("invalid-driver", "sdl", NONCE, 44, backend))
        for mode, code, text in (("timer", 44, backend), ("sdl", 0, backend), ("sdl", 44, backend * 2),
                                 ("sdl", 44, backend.replace("no audio driver", "other failure")),
                                 ("sdl", 44, backend + output(records("sdl")))):
            self.assertFalse(driver.control("invalid-driver", mode, NONCE, code, text))

    def test_real_owned_child_timeout_with_plausible_output_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "child.log"
            script = "import time; print(" + repr(output(records())) + ", flush=True); time.sleep(10)"
            code = driver.run_process([sys.executable, "-c", script], cwd=directory,
                                      env=dict(os.environ), log=log, timeout=0.3)
            self.assertEqual(code, -999)
            self.assertIsNone(driver.classify(("capacity",), "timer", NONCE, code, log.read_text()))

    def test_wrong_or_unapproved_loaded_library_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk, staging, other = (Path(directory) / name for name in ("sdk", "build", "other"))
            folder = sdk / ("bin" if os.name == "nt" else "lib")
            folder.mkdir(parents=True); staging.mkdir(); other.mkdir()
            libraries, _ = records("sdl")
            for role, name in driver.ROLES.items():
                leaf = name + ".dll" if os.name == "nt" else "lib" + name + (".so.0" if role == "sdl" else ".so")
                path = folder / leaf
                path.write_bytes(b"original synthetic library identity")
                libraries["loaded"][role] = str(path)
            self.assertEqual(set(driver.loaded_identity(libraries, sdk, os.name == "nt", staging)), set(driver.ROLES))
            copied = staging / Path(libraries["loaded"]["audio"]).name
            copied.write_bytes(b"original synthetic library identity")
            libraries["loaded"]["audio"] = str(copied)
            driver.loaded_identity(libraries, sdk, os.name == "nt", staging)
            copied.write_bytes(b"changed library")
            with self.assertRaisesRegex(ValueError, "wrong loaded"):
                driver.loaded_identity(libraries, sdk, os.name == "nt", staging)
            external = other / copied.name
            external.write_bytes(b"original synthetic library identity")
            libraries["loaded"]["audio"] = str(external)
            with self.assertRaisesRegex(ValueError, "unexpected loaded"):
                driver.loaded_identity(libraries, sdk, os.name == "nt", staging)

    def test_bad_package_stops_before_output_or_build(self):
        args = ["test_sdk_audio.py", "--root", "unused", "--sdk-report", "bad", "--output-root", "uncreated"]
        with patch.object(sys, "argv", args), \
             patch.object(driver.storage, "verify_package", side_effect=ValueError("changed package")), \
             patch.object(driver.common, "private_cache", side_effect=AssertionError("must not create output")), \
             patch.object(subprocess, "run", side_effect=AssertionError("must not build")):
            with self.assertRaises(SystemExit) as error: driver.main()
            self.assertEqual(error.exception.code, 2)
