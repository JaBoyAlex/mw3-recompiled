# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import verify_kernel_gate as driver


class LifecycleResultGuards(unittest.TestCase):
    def positive(self):
        return ("MW3_HEADER_ORACLE_CASE_PASS:one\n" * 4
                + "MW3_HEADER_QUERY_PASS:observed\n"
                + "MW3_PROBE_UNREVIEWED_IMPORT:NtAllocateVirtualMemory lr=1234\n"
                + "MW3_LIFECYCLE_THREAD_STOPPED:exit=86 queries=1\n"
                + "MW3_LIFECYCLE_UNLOADED:reservation_released=1\n"
                + "MW3_LIFECYCLE_SHUTDOWN:result=0 threads_before=0 threads_after=0\n"
                + "MW3_LIFECYCLE_COMPLETE:exit=86\n")

    def test_abrupt_exit_cannot_replace_orderly_teardown(self):
        text = self.positive()
        self.assertTrue(driver.classify("positive-0", 86, text))
        for altered in (text.replace("reservation_released=1", "reservation_released=0"),
                        text.replace("threads_after=0", "threads_after=1"),
                        text.replace("MW3_LIFECYCLE_COMPLETE:exit=86", ""),
                        text.replace("NtAllocateVirtualMemory", "AnotherImport"),
                        text + "runtime error: overflow\n"):
            self.assertFalse(driver.classify("positive-0", 86, altered))
        self.assertFalse(driver.classify("positive-0", -999, text))
        self.assertFalse(driver.classify("positive-0", 0, text))

    def test_partial_or_duplicated_evidence_is_rejected(self):
        text = self.positive()
        for altered in (text.replace("MW3_HEADER_ORACLE_CASE_PASS:one\n", "", 1),
                        text + "MW3_LIFECYCLE_COMPLETE:exit=86\n",
                        text + "MW3_LIFECYCLE_REJECT:unrelated\n",
                        text.replace("exit=86 queries=1", "exit=0 queries=1")):
            self.assertFalse(driver.classify("positive-1", 86, altered))

    def test_negative_requires_its_reason_and_cleanup(self):
        text = ("MW3_LIFECYCLE_REJECT:unexpected header pointer\n"
                "MW3_LIFECYCLE_UNLOADED:reservation_released=1\n"
                "MW3_LIFECYCLE_SHUTDOWN:result=0 threads_before=0 threads_after=0\n"
                "MW3_LIFECYCLE_COMPLETE:exit=87\n")
        self.assertTrue(driver.classify("bad-pointer", 87, text))
        self.assertFalse(driver.classify("bad-binding", 87, text))
        self.assertFalse(driver.classify("bad-pointer", 87, text + "MW3_HEADER_QUERY_PASS:wrong\n"))
        self.assertFalse(driver.classify("bad-pointer", 87, text.replace("reservation_released=1", "reservation_released=0")))

    def test_controlled_imports_retain_complete_binding_checks(self):
        def record(name, address, kind):
            return dict(export_name=name, address=address, type=kind,
                        export_kind="kFunction" if kind else "kVariable")
        metadata = dict(import_audit=dict(libraries=[dict(records=[
            record("RtlImageXexHeaderField", 0x1000, 1),
            record("NtAllocateVirtualMemory", 0x2000, 1),
            record("XexExecutableModuleHandle", 0x3000, 0),
        ])]))
        source, address = driver.controlled_traps(metadata, "original_fixture", 2)
        self.assertEqual(address, 0x3000)
        self.assertIn('StopUnreviewedImport("NtAllocateVirtualMemory",ctx)', source)
        self.assertNotIn("std::_Exit", source)
        self.assertIn("runtime.FindFunction(0x2000)", source)
        self.assertIn("MW3_HEADER_TEST_BAD_BINDING", source)
        with self.assertRaises(ValueError):
            driver.controlled_traps(metadata, "original_fixture", 3)
