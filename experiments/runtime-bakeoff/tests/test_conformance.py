# SPDX-License-Identifier: GPL-3.0-only
"""Original negative fixtures for comparison evidence, with no SDK dependency."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_conformance import classify,geometry


class ConformanceEvidenceTests(unittest.TestCase):
    def test_exit_code_and_marker_must_agree(self):
        self.assertEqual(classify(0,"CONFORMANCE_PASS\n"),"PASS")
        self.assertEqual(classify(1,"CONFORMANCE_FAIL:original fixture\n"),"FAIL")
        for code,text in [(0,""),(1,""),(0,"CONFORMANCE_FAIL:x"),(1,"CONFORMANCE_PASS"),
                          (0,"CONFORMANCE_PASS\nCONFORMANCE_FAIL:x"),(-11,"CONFORMANCE_PASS")]:
            with self.subTest(code=code,text=text):
                self.assertEqual(classify(code,text),"ERROR")

    def test_sanitizer_failure_cannot_hide_behind_expected_candidate_failure(self):
        for error in ("ERROR: AddressSanitizer", "ERROR: LeakSanitizer", "runtime error:", "UndefinedBehaviorSanitizer:"):
            with self.subTest(error=error):
                self.assertEqual(classify(1,"CONFORMANCE_FAIL:x\n"+error),"ERROR")
                self.assertEqual(classify(0,"CONFORMANCE_PASS\n"+error),"ERROR")

    def test_geometry_binds_summary_and_refuses_invalid_bounds(self):
        value=dict(base=0x82000000,size=0x100000,sections=[dict(code=True,address=0x82090000,size=0x10000)])
        expected=dict(base=value["base"],image_size=value["size"])
        self.assertEqual(geometry(value,expected)["PPC_CODE_SIZE"],0x10000)
        with self.assertRaises(ValueError):geometry(value,dict(expected,base=0))
        for address,size in [(0,4),(0x82090001,4),(0x82090000,0x100000),(0x82090000,-4),(True,4),("bad",4)]:
            changed=copy.deepcopy(value)
            changed["sections"][0].update(address=address,size=size)
            with self.subTest(address=address,size=size),self.assertRaises(ValueError):geometry(changed,expected)


if __name__=="__main__":unittest.main()
