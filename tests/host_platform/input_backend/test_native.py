# SPDX-License-Identifier: GPL-3.0-only
"""Original C++20 conversion contracts; no SDL, SDK or hardware is loaded."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cmake, cls.ctest = shutil.which('cmake'), shutil.which('ctest')
        if not cls.cmake or not cls.ctest: raise unittest.SkipTest('CMake/CTest unavailable')
        cls.temp = tempfile.TemporaryDirectory(prefix='mw3-conversion-')
        cls.addClassCleanup(cls.temp.cleanup); cls.build = Path(cls.temp.name) / 'build'
        cls.run_command([cls.cmake, '-S', str(Path(__file__).parent), '-B', str(cls.build), '-DCMAKE_BUILD_TYPE=Release',
                         '-DMW3_INPUT_SANITIZERS=' + ('OFF' if os.name == 'nt' else 'ON')])
        cls.run_command([cls.cmake, '--build', cls.build, '--config', 'Release', '--parallel', '2'])
        cls.binary = cls.build / ('Release/input-conversion-tests.exe' if os.name == 'nt' else 'input-conversion-tests')

    @staticmethod
    def run_command(command):
        result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=180)
        if result.returncode: raise AssertionError(result.stdout + result.stderr)
        return result

    def test_conversion_contracts(self):
        result = self.run_command([self.ctest, '--test-dir', self.build, '-C', 'Release', '--output-on-failure'])
        self.assertIn('100% tests passed, 0 tests failed out of 4', result.stdout)

    def test_incorrect_neutral_is_rejected(self):
        r = subprocess.run([str(self.binary), 'negative-control'], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 1); self.assertEqual(r.stderr.strip(), 'FAIL: deliberate wrong-neutral rejected')
        self.assertNotIn('PASS:', r.stdout)

    def test_argument_errors(self):
        for args, error in (([], 'ERROR: exactly one case required'), (['unknown'], 'ERROR: unknown case')):
            r = subprocess.run([str(self.binary), *args], capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 2); self.assertEqual(r.stderr.strip(), error)
            self.assertNotIn('PASS:', r.stdout)
