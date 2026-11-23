# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import test_startup_memory as driver

NONCE = "a" * 32


def bind_nonce(text):
    return "\n".join(line + (" nonce=" + NONCE if line.startswith(("MW3_ALLOC_ARMED:", "MW3_ALLOC_COMPLETE:")) else "")
                     for line in text.splitlines()) + "\n"


def classify(case, code, text):
    return driver.classify(case, code, bind_nonce(text), NONCE)


def mutation_rejected(case, code, text):
    return driver.mutation_rejected(case, code, bind_nonce(text), NONCE)



class AllocationResultGuards(unittest.TestCase):
    def test_stub_success_and_incomplete_teardown_are_rejected(self):
        text = ("MW3_ALLOC_ARMED:case=basic\n"
                "MW3_ALLOC_CALL:NtAllocateVirtualMemory\n"
                "MW3_ALLOC_RETURN:NtAllocateVirtualMemory status=00000000\n"
                "MW3_ALLOC_CALL:NtFreeVirtualMemory\n"
                "MW3_ALLOC_RETURN:NtFreeVirtualMemory status=00000000\n"
                "MW3_ALLOC_VERIFIED:case=basic\n"
                "MW3_ALLOC_COMPLETE:case=basic result=0 verified=1 threads_before=0 threads_after=0\n")
        self.assertTrue(classify("basic", 0, text))
        for altered in (text.replace("MW3_ALLOC_RETURN:NtFreeVirtualMemory status=00000000\n", ""),
                        text.replace("threads_after=0", "threads_after=1"),
                        text.replace("MW3_ALLOC_COMPLETE:", "MISSING_COMPLETE:"),
                        text + "runtime error: reference binding to null pointer\n",
                        text + "MW3_ALLOC_FAILURE:actual allocation remained live\n", text + text):
            self.assertFalse(classify("basic", 0, altered))
        self.assertFalse(classify("basic", -999, text))
        self.assertFalse(classify("basic", -11, text))

    def test_invalid_input_must_return_failure_and_complete(self):
        text = ("MW3_ALLOC_ARMED:case=free-null-base\n"
                "MW3_ALLOC_CALL:NtAllocateVirtualMemory\n"
                "MW3_ALLOC_RETURN:NtAllocateVirtualMemory status=00000000\n"
                "MW3_ALLOC_CALL:NtFreeVirtualMemory\n"
                "MW3_ALLOC_RETURN:NtFreeVirtualMemory status=c000000d\n"
                "MW3_ALLOC_CALL:NtFreeVirtualMemory\n"
                "MW3_ALLOC_RETURN:NtFreeVirtualMemory status=00000000\n"
                "MW3_ALLOC_VERIFIED:case=free-null-base\n"
                "MW3_ALLOC_COMPLETE:case=free-null-base result=0 verified=1 threads_before=0 threads_after=0\n")
        self.assertTrue(classify("free-null-base", 0, text))
        self.assertFalse(classify("free-null-base", 0, text.replace("c000000d", "00000000")))
        self.assertFalse(classify("free-null-base", 1, text))

    def test_large_reservation_cannot_omit_release_on_success(self):
        prefix = "MW3_ALLOC_ARMED:case=negative-intmin\nMW3_ALLOC_CALL:NtAllocateVirtualMemory\n"
        end = ("MW3_ALLOC_VERIFIED:case=negative-intmin\n"
               "MW3_ALLOC_COMPLETE:case=negative-intmin result=0 verified=1 threads_before=0 threads_after=0\n")
        self.assertTrue(classify("negative-intmin", 0,
            prefix + "MW3_ALLOC_RETURN:NtAllocateVirtualMemory status=c0000017\n" + end))
        self.assertFalse(classify("negative-intmin", 0,
            prefix + "MW3_ALLOC_RETURN:NtAllocateVirtualMemory status=00000000\n" + end))
