# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import test_rexglue_ppc as driver

class ResultGuards(unittest.TestCase):
    def test_missing_duplicate_or_error_results_cannot_pass(self):
        cases=[dict(id='case-0',out=dict(r3=0))]
        rows=[dict(id='case-0',status='PASS',mismatches=[]),dict(completed=1,failures=0)]
        log='\n'.join(json.dumps(r) for r in rows)
        self.assertTrue(driver.classify(0,log,cases))
        for code,text in [(1,log),(0,log.splitlines()[0]),(0,log+'\n'+log),(0,log+'\nruntime error: overflow')]:
            self.assertFalse(driver.classify(code,text,cases))
    def test_mutation_requires_the_exact_observed_counterexample(self):
        cases=[dict(id='case-0',out=dict(r3=1))]
        row=dict(id='case-0',status='FAIL',mismatches=[dict(register='r3',expected=1,actual=0)])
        def log():return json.dumps(row)+'\n'+json.dumps(dict(completed=1,failures=1))
        self.assertTrue(driver.classify(1,log(),cases,True))
        self.assertFalse(driver.classify(0,log(),cases,True))
        row['mismatches'][0]['register']='ca'
        self.assertFalse(driver.classify(1,log(),cases,True))
