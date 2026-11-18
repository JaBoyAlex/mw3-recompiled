# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import test_runtime_threads as driver

class ThreadResultGuards(unittest.TestCase):
    def test_mutation_requires_its_exact_exception_and_one_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'results.xml'
            def document(exception='THREAD_RESULT_MUTATION_DETECTED',failures=1,extra=''):
                return (f'<Catch2TestRun><TestCase name="{driver.CANCELLATION}"><Expression success="false">'
                    f'<Exception>{exception}</Exception></Expression>{extra}<OverallResult success="false"/>'
                    f'</TestCase><OverallResults successes="0" failures="{failures}" skips="0"/></Catch2TestRun>')
            path.write_text(document())
            self.assertEqual(driver.mutation_outcome(42,path,'result','')['status'],'PASS')
            for code,log in ((0,''),(-999,''),(42,'runtime error: overflow')):
                self.assertEqual(driver.mutation_outcome(code,path,'result',log)['status'],'FAIL')
            for xml in (document('unrelated error THREAD_RESULT_MUTATION_DETECTED'),document(failures=2),
                        document(extra='<Exception>another error</Exception>'),document().replace(driver.CANCELLATION,'other')):
                path.write_text(xml)
                self.assertEqual(driver.mutation_outcome(42,path,'result','')['status'],'FAIL')
    def test_deadline_requires_exactly_one_armed_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'results.xml'
            path.write_text(f'<Catch2TestRun><TestCase name="{driver.CANCELLATION}">'
                '<Exception>THREAD_DEADLINE_MUTATION_DETECTED</Exception><OverallResult success="false"/>'
                '</TestCase><OverallResults successes="0" failures="1" skips="0"/></Catch2TestRun>')
            marker='THREAD_DEADLINE_NEGATIVE_ARMED\n'
            for log,status in (('', 'FAIL'),(marker,'PASS'),(marker*2,'FAIL'),(marker+'AddressSanitizer','FAIL')):
                self.assertEqual(driver.mutation_outcome(42,path,'deadline',log)['status'],status)
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
