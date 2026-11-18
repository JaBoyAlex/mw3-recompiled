# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import test_runtime_threads as driver

class ThreadResultGuards(unittest.TestCase):
    def test_partial_or_nonzero_results_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'results.xml'
            path.write_text('<Catch2TestRun><TestCase name="one"><OverallResult success="true"/></TestCase>'
                            '<OverallResults successes="1" failures="0" skips="0"/></Catch2TestRun>')
            self.assertEqual(driver.outcome(0,path,1)['status'],'PASS')
            self.assertEqual(driver.outcome(1,path,1)['status'],'FAIL')
            self.assertEqual(driver.outcome(0,path,2)['status'],'FAIL')
            with self.assertRaises(ValueError):driver.outcome(0,path,0)
    def test_xml_failure_cannot_pass_by_zero_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'results.xml'
            path.write_text('<Catch2TestRun><TestCase name="one"><OverallResult success="false"/></TestCase>'
                            '<OverallResults successes="0" failures="1" skips="0"/></Catch2TestRun>')
            checked=driver.outcome(0,path,1)
            self.assertEqual(checked['status'],'FAIL');self.assertEqual(checked['failed'],['one'])
    def test_all_skip_remains_a_skip(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'results.xml'
            path.write_text('<Catch2TestRun><TestCase name="one"><Skip>host capability absent</Skip></TestCase>'
                            '<OverallResults successes="0" failures="0" skips="1"/></Catch2TestRun>')
            self.assertEqual(driver.outcome(4,path,1)['status'],'SKIP')
            self.assertEqual(driver.outcome(1,path,1)['status'],'FAIL')
