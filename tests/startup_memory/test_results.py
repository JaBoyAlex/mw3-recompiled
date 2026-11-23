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



def log(case="basic", status="00000000"):
    return (f"MW3_ALLOC_ARMED:case={case}\n"
            "MW3_ALLOC_CALL:NtAllocateVirtualMemory\n"
            f"MW3_ALLOC_RETURN:NtAllocateVirtualMemory status={status}\n"
            "MW3_ALLOC_CALL:NtFreeVirtualMemory\n"
            "MW3_ALLOC_RETURN:NtFreeVirtualMemory status=00000000\n"
            f"MW3_ALLOC_VERIFIED:case={case}\n"
            f"MW3_ALLOC_COMPLETE:case={case} result=0 verified=1 threads_before=0 threads_after=0\n")


class ResultGuards(unittest.TestCase):
    def test_wrong_results_and_incomplete_processes_cannot_pass(self):
        good = log()
        self.assertTrue(classify("basic", 0, good))
        for text in (log(status="c000000d"), good + good, good + "AddressSanitizer",
                     good.replace("threads_after=0", "threads_after=1"),
                     good.replace("MW3_ALLOC_VERIFIED:case=basic\n", ""),
                     good.replace("verified=1", "verified=2"),
                     good.replace("MW3_ALLOC_RETURN:NtFreeVirtualMemory", "MW3_ALLOC_RETURN:NtAllocateVirtualMemory"),
                     good.replace("MW3_ALLOC_COMPLETE:", "incomplete:"),
                     good + "MW3_ALLOC_CALL:NtFreeVirtualMemory\n"):
            self.assertFalse(classify("basic", 0, text), text)
        for code in (2, -999, -11):
            self.assertFalse(classify("basic", code, good))

    def test_repeated_order_must_be_complete_and_distinct(self):
        steps = driver.steps("repeat")
        self.assertEqual(len(steps), 12)
        parts = ["MW3_ALLOC_ARMED:case=repeat\n"]
        for case in steps:
            names = ["NtAllocateVirtualMemory", "NtFreeVirtualMemory"]
            if case == "lifecycle":
                names = [names[0], names[0], names[1], names[0], names[1]]
            if case == "double-release":
                names.append("NtFreeVirtualMemory")
            for index, name in enumerate(names):
                status = "c0000001" if case == "double-release" and index == 2 else "00000000"
                parts += [f"MW3_ALLOC_CALL:{name}\n", f"MW3_ALLOC_RETURN:{name} status={status}\n"]
            parts.append(f"MW3_ALLOC_VERIFIED:case={case}\n")
        parts.append("MW3_ALLOC_COMPLETE:case=repeat result=0 verified=12 threads_before=0 threads_after=0\n")
        good = "".join(parts)
        self.assertTrue(classify("repeat", 0, good))
        self.assertFalse(classify("repeat", 0, good.replace("case=lifecycle", "case=basic", 1)))
        self.assertFalse(classify("repeat", 0, good.replace("verified=12", "verified=11")))

    def test_mutation_controls_require_exact_arming_and_expected_failure(self):
        for case in driver.MUTATIONS:
            text = log().split("MW3_ALLOC_COMPLETE:")[0].replace("ARMED:case=basic", f"ARMED:case={case}")
            text += f"MW3_ALLOC_MUTATION:{case}\n"
            code = -999 if case == "mutation-late" else 0
            if case == "mutation-result":
                code = 2
                text += ("MW3_ALLOC_FAILURE:intentional wrong result\n"
                         "MW3_ALLOC_COMPLETE:case=mutation-result result=2 verified=1 threads_before=0 threads_after=0\n")
            self.assertTrue(mutation_rejected(case, code, text))
            for bad in (text.replace("MW3_ALLOC_MUTATION:", "unarmed:"), text + text,
                        text + "runtime error: overflow", text.replace("case=basic", "case=other")):
                self.assertFalse(mutation_rejected(case, code, bad))
            self.assertFalse(mutation_rejected(case, -11, text))


    def test_stale_nonce_and_fabricated_mutation_success_are_rejected(self):
        good = bind_nonce(log())
        self.assertTrue(driver.classify("basic", 0, good, NONCE))
        self.assertFalse(driver.classify("basic", 0, good, "b" * 32))
        self.assertFalse(driver.classify("basic", 0, good, ""))
        for case in driver.MUTATIONS:
            text = log().split("MW3_ALLOC_COMPLETE:")[0].replace("ARMED:case=basic", f"ARMED:case={case}")
            text += f"MW3_ALLOC_MUTATION:{case}\n"
            code = -999 if case == "mutation-late" else 0
            if case == "mutation-result":
                code = 2
                text += ("MW3_ALLOC_FAILURE:intentional wrong result\n"
                         "MW3_ALLOC_COMPLETE:case=mutation-result result=2 verified=1 threads_before=0 threads_after=0\n")
            self.assertFalse(driver.mutation_rejected(case, code, bind_nonce(text), "b" * 32))
            for bad in (text.replace("status=00000000", "status=c000000d", 1),
                        text.replace("MW3_ALLOC_RETURN:NtFreeVirtualMemory status=00000000\n", ""),
                        text.replace("threads_after=0", "threads_after=1"),
                        text + "MW3_ALLOC_FAILURE:unrelated live allocation\n",
                        text + "exception: ACCESS_VIOLATION (0xc0000005)\n",
                        text + "==== allocation-contracts crash report, rexglue ====\n",
                        text + "MW3_ALLOC_UNKNOWN:unexpected extra record\n"):
                if bad != text:
                    self.assertFalse(mutation_rejected(case, code, bad), bad)
