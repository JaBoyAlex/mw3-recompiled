# SPDX-License-Identifier: GPL-3.0-only
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('ppc_math',Path(__file__).with_name('oracle.py'))
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
class OracleTests(unittest.TestCase):
    def test_round_ties_and_fused_cancellation(self):
        f=oracle.Fraction
        self.assertEqual(oracle.rounded32(f(1)+f(1,1<<24)),0x3f800000)
        self.assertEqual(oracle.rounded32(f(1)+f(3,1<<24)),0x3f800002)
        self.assertEqual(oracle.rounded32(-f(1,1<<46)),0xa8800000)
        self.assertEqual(oracle.rounded32(f(1,1<<149)),1)
        self.assertEqual(oracle.rounded32(f(1,1<<150)),0)
    def test_seeded_reproducibility_and_edges(self):
        a=oracle.cases(count=3)
        self.assertEqual(a,oracle.cases(count=3))
        self.assertNotEqual(a,oracle.cases(seed=7,count=3))
        self.assertEqual(len(a),len({r['id'] for r in a}))
        self.assertEqual({r['function'] for r in a},{'test_'+n for n in ('addc','adde','subf','rotate','memory','branch','call','loop','fadd','fmadd','vadd','vxor','vmadd')})
        self.assertTrue(any(r['out'].get('ca')==1 for r in a))
    def test_32_bit_execution_flags_with_64_bit_gprs(self):
        self.assertEqual(oracle.cr(0x100000000,0),2)
        self.assertEqual(oracle.cr(0x80000000,1),9)
        row=next(r for r in oracle.cases(count=0) if r['function']=='test_addc' and r['in']['r4']==1 and r['in']['r5']==0xffffffff)
        self.assertEqual(row['out']['r3'],0x100000000)
        self.assertEqual(row['out']['ca'],1)
