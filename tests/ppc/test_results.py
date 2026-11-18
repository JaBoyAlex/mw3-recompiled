# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path
import sys
import tempfile
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
    def test_reference_refuses_failure_stale_source_and_changed_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);(path/'bins').mkdir();(path/'copy').mkdir()
            for n in ('fixtures.o','fixtures.elf','fixtures.bin','fixtures.map'):(path/'bins'/n).write_bytes(b'original synthetic')
            receipt=dict(status='PASS',evidence_class='original-synthetic-ppc-oracle',
                script_sha256=driver.prep.sha(driver.__file__),sources=driver.source_snapshot(),assembly=driver.prep.snapshot(path/'bins'))
            manifest=path/'manifest.json';manifest.write_text(json.dumps(receipt))
            self.assertEqual(driver.reference_bundle(path,path/'copy'),receipt)
            for field,value in [('status','FAIL'),('sources',{}),('script_sha256','0'*64)]:
                bad=dict(receipt);bad[field]=value;manifest.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):driver.reference_bundle(path,path/'copy')
            manifest.write_text(json.dumps(receipt));(path/'bins/fixtures.bin').write_bytes(b'changed')
            with self.assertRaises(ValueError):driver.reference_bundle(path,path/'copy')
