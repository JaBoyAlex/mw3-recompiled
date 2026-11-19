# SPDX-License-Identifier: GPL-3.0-only
"""Original bounded host records: native contracts and real process recovery."""
import os
from pathlib import Path
import queue
import shutil
import struct
import subprocess
import tempfile
import threading
import unittest
import zlib

SOURCE = Path(__file__).resolve().parent


class NativeStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cmake, cls.ctest = shutil.which("cmake"), shutil.which("ctest")
        if not cls.cmake or not cls.ctest:
            raise unittest.SkipTest("CMake/CTest unavailable; run standalone storage contract project")
        cls.temp = tempfile.TemporaryDirectory(prefix="mw3-host-storage-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name).resolve()
        cls.build = cls.root / "build"
        # Windows ASan is run explicitly with its runtime on PATH; public
        # discovery still exercises native Windows when that runtime is absent.
        sanitizers = os.environ.get("MW3_PROFILE_TEST_SANITIZERS", "OFF" if os.name == "nt" else "ON")
        cls.run_command([cls.cmake, "-S", str(SOURCE), "-B", str(cls.build),
                         "-DCMAKE_BUILD_TYPE=Release", f"-DMW3_PROFILE_SANITIZERS={sanitizers}"])
        cls.run_command([cls.cmake, "--build", str(cls.build), "--config", "Release", "--parallel", "2"])
        cls.binary = cls.build / ("Release/profile-tests.exe" if os.name == "nt" else "profile-tests")

    @staticmethod
    def run_command(command, expected=0):
        result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=240)
        if result.returncode != expected:
            raise AssertionError(f"{command}: exit {result.returncode}, expected {expected}\n" + result.stdout + result.stderr)
        return result

    def fixture(self):
        temp = tempfile.TemporaryDirectory(prefix="case-", dir=self.root)
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def native(self, case, root, expected=0):
        return self.run_command([self.binary, case, root], expected)

    def test_native_contracts(self):
        result = self.run_command([self.ctest, "--test-dir", self.build, "-C", "Release", "--output-on-failure"])
        self.assertIn("100% tests passed, 0 tests failed out of 11", result.stdout)

    def test_interruption_before_and_after_publication(self):
        root = self.fixture()
        self.native("child-init", root)
        prior = (root / "profiles/alice/save.0000000000000001.record").read_bytes()
        self.native("child-pending-exit", root, 71)
        pending = root / "profiles/alice/save.0000000000000002.pending"
        staged = pending.read_bytes()
        self.native("child-recover", root)
        self.assertFalse(pending.exists())
        self.assertEqual((pending.with_suffix(".rejected")).read_bytes(), staged)
        self.assertEqual((root / "profiles/alice/save.0000000000000001.record").read_bytes(), prior)
        self.native("child-commit-exit", root, 72)
        self.native("child-expect-new", root)
        self.assertEqual((root / "profiles/alice/save.0000000000000001.record").read_bytes(), prior)

    def test_second_process_writer_and_resource_release(self):
        root = self.fixture()
        self.native("child-init", root)
        owner = subprocess.Popen([str(self.binary), "child-hold", str(root)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            messages = queue.Queue()
            threading.Thread(target=lambda: messages.put(owner.stdout.readline()), daemon=True).start()
            self.assertEqual(messages.get(timeout=30), "READY\n", "owner must actually acquire lock")
            self.native("child-busy", root)
            out, err = owner.communicate("release\n", timeout=30)
            self.assertEqual(owner.returncode, 0, out + err)
            self.native("child-open", root)
        finally:
            if owner.poll() is None:
                owner.kill()  # Only this test's own captured child, never process-name matching.
                owner.communicate(timeout=30)

    def test_envelope_with_independent_crc_and_lengths(self):
        root = self.fixture()
        self.native("child-init", root)
        record = (root / "profiles/alice/save.0000000000000001.record").read_bytes()
        self.assertEqual(record[:8], b"MW3HSV1\0")
        self.assertEqual(record[8:40], b"alice" + bytes(27))
        self.assertEqual(record[40:72], b"save" + bytes(28))
        generation, length, crc = struct.unpack_from("<QII", record, 72)
        self.assertEqual((generation, length, record[88:]), (1, 3, b"old"))
        self.assertEqual(len(record), 88 + length)
        self.assertEqual(crc, zlib.crc32(record[:84] + record[88:]))
        self.assertEqual(zlib.crc32(b"123456789"), 0xCBF43926)

    def test_wrong_expectation_and_invalid_invocation_fail(self):
        root = self.fixture()
        self.native("child-init", root)
        wrong = self.native("child-wrong-expectation", root, 1)
        self.assertIn("ASSERT: negative detector wrong payload", wrong.stderr)
        self.assertNotIn("PASS:", wrong.stdout)
        for args in ([], ["unknown", root], ["child-unknown", root]):
            result = self.run_command([self.binary, *args], 2)
            self.assertNotIn("PASS:", result.stdout)

    @unittest.skipUnless(os.name == "nt", "Windows junction is exercised on native Windows")
    def test_real_windows_junctions(self):
        for case in ("root", "entry", "profile"):
            with self.subTest(case=case):
                root = self.fixture()
                self.native("child-init", root)
                outside = root / "outside"
                outside.mkdir()
                canary = outside / "canary"
                canary.write_bytes(b"outside-unchanged")
                prior = (root / "profiles/alice/save.0000000000000001.record").read_bytes()
                if case == "root":
                    link, target, mode = root / "redirect", outside, "child-unsafe-root"
                elif case == "entry":
                    link, target, mode = root / "profiles/alice/save.0000000000000002.record", outside, "child-unsafe-entry"
                else:
                    target = root / "retained-profile"
                    (root / "profiles/alice").rename(target)
                    link, mode = root / "profiles/alice", "child-unsafe-entry"
                self.run_command(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)])
                self.native(mode, root)
                self.assertEqual(canary.read_bytes(), b"outside-unchanged")
                retained = (target if case == "profile" else root / "profiles/alice") / "save.0000000000000001.record"
                self.assertEqual(retained.read_bytes(), prior)
