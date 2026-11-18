# SPDX-License-Identifier: GPL-3.0-only
"""A crash or diagnostic cannot masquerade as a successful memory test."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
import test_runtime_memory as driver


class MemoryEvidenceTests(unittest.TestCase):
    def test_expected_fault_requires_armed_case_and_actual_platform_signal(self):
        text="MEMORY_FAULT_ARMED:guard-read guest=7000ffff host=0x1234\n"
        self.assertEqual(driver.classify("guard-read",-11,text),"PASS")
        self.assertEqual(driver.classify("guard-read",0xc0000005,text,True),"PASS")
        for code,log in ((0,text),(-11,""),(-11,text.replace("guard-read","released-read")),
                         (-11,text+text),(-11,text+"MEMORY_CONTRACT_PASS"),(-11,text+"ERROR: AddressSanitizer: unrelated")):
            self.assertEqual(driver.classify("guard-read",code,log),"FAIL")
        self.assertEqual(driver.classify("guard-read",-11,text,True),"FAIL")

    def test_positive_and_mutation_cannot_hide_sanitizer_or_wrong_failure(self):
        self.assertEqual(driver.classify("stress",0,"MEMORY_CONTRACT_PASS"),"PASS")
        for text in ("", "MEMORY_CONTRACT_PASS\nruntime error: overflow",
                     "MEMORY_CONTRACT_PASS\nMEMORY_CONTRACT_FAIL:bad"):
            self.assertEqual(driver.classify("stress",0,text),"FAIL")
        text="MEMORY_CONTRACT_FAIL:seeded oracle/content mismatch"
        self.assertEqual(driver.classify("bad-oracle",1,text),"PASS")
        for log in ("MEMORY_CONTRACT_FAIL:other failure",text+"\nERROR: AddressSanitizer: bad"):
            self.assertEqual(driver.classify("bad-oracle",1,log),"FAIL")


if __name__=="__main__":unittest.main()
