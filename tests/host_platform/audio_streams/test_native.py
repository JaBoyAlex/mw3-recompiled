# SPDX-License-Identifier: GPL-3.0-only
"""Original model contracts only; actual SDK observations use the private runner."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parent


class NativeAudioOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cmake, cls.ctest = shutil.which("cmake"), shutil.which("ctest")
        if not cls.cmake or not cls.ctest:
            raise unittest.SkipTest("CMake/CTest unavailable; run standalone audio ownership project")
        cls.temp = tempfile.TemporaryDirectory(prefix="mw3-audio-lifetimes-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.build = Path(cls.temp.name).resolve() / "build"
        sanitizers = os.environ.get("MW3_AUDIO_STREAM_TEST_SANITIZERS", "OFF" if os.name == "nt" else "ON")
        cls.run_command([cls.cmake, "-S", SOURCE, "-B", cls.build, "-DCMAKE_BUILD_TYPE=Release",
                         f"-DMW3_AUDIO_STREAM_SANITIZERS={sanitizers}"])
        cls.run_command([cls.cmake, "--build", cls.build, "--config", "Release", "--parallel", "2"])
        cls.binary = cls.build / ("Release/audio-streams-tests.exe" if os.name == "nt" else "audio-streams-tests")

    @staticmethod
    def run_command(command, expected=0):
        result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=240)
        if result.returncode != expected:
            raise AssertionError(result.stdout + result.stderr)
        return result

    def test_original_model_contracts(self):
        result = self.run_command([self.ctest, "--test-dir", self.build, "-C", "Release", "--output-on-failure"])
        self.assertIn("100% tests passed, 0 tests failed out of 9", result.stdout)

    def test_wrong_result_never_passes(self):
        result = self.run_command([self.binary, "wrong-result"], 1)
        self.assertEqual(result.stderr.strip(), "FAIL: deliberate wrong-result rejected")
        self.assertNotIn("PASS:", result.stdout)

    def test_missing_and_unknown_cases_are_rejected(self):
        for arguments in ([], ["unknown"]):
            result = self.run_command([self.binary, *arguments], 2)
            self.assertNotIn("PASS:", result.stdout)
