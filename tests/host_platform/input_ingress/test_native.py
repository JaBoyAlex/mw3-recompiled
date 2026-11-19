# SPDX-License-Identifier: GPL-3.0-only
"""Original game-free C++20 contracts; these do not load an SDK or controller."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parent


class NativeIngressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cmake, cls.ctest = shutil.which("cmake"), shutil.which("ctest")
        if not cls.cmake or not cls.ctest:
            raise unittest.SkipTest("CMake/CTest unavailable; run standalone ingress project")
        cls.temp = tempfile.TemporaryDirectory(prefix="mw3-ingress-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.build = Path(cls.temp.name) / "build"
        cls.run_command([cls.cmake, "-S", str(SOURCE), "-B", str(cls.build), "-DCMAKE_BUILD_TYPE=Release",
                         f"-DMW3_INPUT_SANITIZERS={'OFF' if os.name == 'nt' else 'ON'}"])
        cls.run_command([cls.cmake, "--build", str(cls.build), "--config", "Release", "--parallel", "2"])
        cls.binary = cls.build / ("Release/input-ingress-tests.exe" if os.name == "nt" else "input-ingress-tests")

    @staticmethod
    def run_command(command):
        result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
        if result.returncode: raise AssertionError(result.stdout + result.stderr)
        return result

    def test_native_contracts(self):
        result = self.run_command([self.ctest, "--test-dir", self.build, "-C", "Release", "--output-on-failure"])
        self.assertIn("100% tests passed, 0 tests failed out of 8", result.stdout)

    def test_wrong_expected_route_is_rejected(self):
        result = subprocess.run([str(self.binary), "negative-control"], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stderr.strip(), "FAIL: deliberate wrong-route rejected")
        self.assertNotIn("PASS:", result.stdout)

    def test_missing_and_unknown_cases_are_rejected(self):
        for arguments, error in (([], "ERROR: exactly one case required"), (["unknown"], "ERROR: unknown case")):
            with self.subTest(arguments=arguments):
                result = subprocess.run([str(self.binary), *arguments], capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(result.stderr.strip(), error)
                self.assertNotIn("PASS:", result.stdout)
