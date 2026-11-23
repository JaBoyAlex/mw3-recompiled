# SPDX-License-Identifier: GPL-3.0-only
"""Original protocol fixtures; these do not execute SDK services or certify a console."""
import contextlib
import copy
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import test_gpu_display as audit


class DisplayEvidenceTests(unittest.TestCase):
    nonce = 'a' * 32

    def fixture(self, case='ordinary'):
        plan = audit.oracle.plan(audit.SEED)
        before = [0x7000, 0, 0x20000] + list(range(18))
        rows = [dict(service=s, offset=o, bytes=audit.oracle.expected(s).hex(), r3=3 if s == 3 else 0xa51b987600001000,
            before=before[:], after=before[:], external_canary=True, elapsed_ns=100) for s,o in plan]
        value = dict(schema=1,case=case,nonce=self.nonce,pages_before=40,pages_after=40,objects_before=1,objects_after=1,
            runtime_loaded_after=False,sdk_errors=0,sdk_warnings=0,load_ns=100,teardown_ns=100,rows=rows,
            loaded=dict(kernel='private/original-fixture-kernel',base='private/original-fixture-base'),
            exports=[dict(name=n,ordinal=o) for n,o in audit.oracle.SERVICES])
        return plan,value

    def text(self,value):
        return (audit.LIBRARIES+json.dumps(dict(nonce=self.nonce,loaded=value['loaded'],exports=value['exports']))+'\n'+
            'MW3_DISPLAY_READY:'+self.nonce+'\n'+audit.COMPLETE+json.dumps(value)+'\n')

    def test_declared_default_byte_contract_has_explicit_extent_endian_and_guards(self):
        mode = audit.oracle.expected(0)
        self.assertEqual(mode[:16],b'\xa7'*16)
        self.assertEqual(mode[64:],b'\xa7'*64)
        self.assertEqual(struct.unpack('>5I',mode[16:36]),(1280,720,0,1,1))
        self.assertEqual(struct.unpack('>f',mode[36:40]),(60.0,))
        info = audit.oracle.expected(1)[16:104]
        self.assertEqual(len(info),88)
        self.assertEqual(struct.unpack_from('>HH',info,0),(1280,720))
        self.assertEqual(struct.unpack_from('>6H',info,64),(320,180,320,180,1280,720))
        self.assertEqual(info[6:8],b'\0\0')
        gamma=audit.oracle.expected(2)
        self.assertEqual(gamma[16:20],b'\0\0\0\2')
        self.assertEqual(gamma[80:84],struct.pack('>f',2.22222233))

    def test_plan_reversal_heldout_and_bounds_are_real_input_changes(self):
        ordinary=audit.oracle.plan(audit.SEED)
        self.assertEqual(len(ordinary),128)
        self.assertEqual(audit.oracle.plan(audit.SEED,True),list(reversed(ordinary)))
        self.assertNotEqual(audit.oracle.plan(0x5eed051),ordinary)
        self.assertTrue(all(0<=s<4 and o%16==0 and 16<=o<=audit.oracle.SIZE-128 for s,o in ordinary))

    def test_complete_exact_policy_observations_and_one_wrong_result(self):
        plan,value=self.fixture()
        self.assertEqual(audit.complete('ordinary',self.nonce,0,self.text(value),plan)['failures'],[])
        value['case']='wrong-result';raw=bytearray.fromhex(value['rows'][0]['bytes']);raw[16]^=1;value['rows'][0]['bytes']=raw.hex()
        self.assertEqual(audit.complete('wrong-result',self.nonce,0,self.text(value),plan)['failures'],['0:output-extent/endian/canary'])

    def test_nonzero_partial_duplicate_stale_and_sanitizer_output_cannot_pass(self):
        plan,value=self.fixture();text=self.text(value)
        for code,output in ((1,text),(-999,text),(0,text.replace(self.nonce,'b'*32)),(0,text.split(audit.COMPLETE)[0]),
                (0,text+audit.COMPLETE+json.dumps(value)),(0,text+audit.LIBRARIES+'{}'),(0,text+'\nMW3_DISPLAY_FAILURE:failure'),
                (0,text+'\nAddressSanitizer: diagnostic'),(0,text+'\nruntime error: diagnostic')):
            self.assertIsNone(audit.complete('ordinary',self.nonce,code,output,plan))
        self.assertIsNone(audit.complete('ordinary',self.nonce,0,text.replace('"schema": 1','"schema": 1, "schema": 1'),plan))

    def test_resource_lifetime_type_and_export_mutations_are_rejected(self):
        plan,value=self.fixture()
        for key,bad in (('schema',True),('runtime_loaded_after',True),('pages_after',41),('objects_before',True),
                ('sdk_errors',1),('load_ns',True),('rows',[]),('extra',0)):
            changed=copy.deepcopy(value);changed[key]=bad
            self.assertIsNone(audit.complete('ordinary',self.nonce,0,self.text(changed),plan),key)
        for bad in (True,458.0,0):
            changed=copy.deepcopy(value);changed['exports'][0]['ordinal']=bad
            self.assertIsNone(audit.complete('ordinary',self.nonce,0,self.text(changed),plan))

    def test_register_canary_and_flag_deviations_are_failures_not_missing_success(self):
        plan,value=self.fixture()
        value['rows'][0]['after'][4]^=1;value['rows'][1]['external_canary']=False
        value['rows'][3]['r3']=0
        failures=audit.complete('ordinary',self.nonce,0,self.text(value),plan)['failures']
        self.assertEqual(failures,['0:nonvolatile-gpr','1:external-canary','3:flag-return'])
        value['rows'][0]['before'][0]=True
        self.assertIsNone(audit.complete('ordinary',self.nonce,0,self.text(value),plan))

    def test_armed_fault_is_observed_without_compatibility_pass(self):
        text=audit.ARMED+json.dumps(dict(nonce=self.nonce,case='null-mode',service=0,pointer=0))+'\n'
        value=audit.boundary('null-mode',self.nonce,3221225477,text,[])
        self.assertEqual(value['observation'],'TERMINATED_AFTER_ARM')
        self.assertFalse(value['compatibility_passed'])
        with self.assertRaises(ValueError):audit.boundary('null-mode',self.nonce,1,text.replace('"pointer": 0','"pointer": 4'),[])
        with self.assertRaises(ValueError):audit.boundary('null-mode',self.nonce,1,'',[])

    def test_misaligned_return_is_not_console_alignment_compatibility(self):
        plan,value=self.fixture('misaligned-display')
        row=copy.deepcopy(value['rows'][1]);row.update(service=1,offset=16,bytes=audit.oracle.expected(1,17).hex())
        value['rows']=[row]
        armed=audit.ARMED+json.dumps(dict(nonce=self.nonce,case='misaligned-display',service=1,pointer=0x10021))+'\n'
        result=audit.boundary('misaligned-display',self.nonce,0,armed+self.text(value),plan)
        self.assertEqual(result['observation'],'RETURNED')
        self.assertFalse(result['compatibility_passed'])
        self.assertEqual(result['record']['failures'],[])

    def test_loaded_module_path_and_bytes_must_match_approved_package(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sdk=root/'sdk';build=root/'build';build.mkdir()
            sub='bin' if sys.platform=='win32' else 'lib';(sdk/sub).mkdir(parents=True)
            loaded={}
            for role,name in (('kernel','rexkernel'),('base','rexbase')):
                file=name+'.dll' if sys.platform=='win32' else 'lib'+name+'.so'
                path=sdk/sub/file;path.write_bytes(b'non executable fixture');loaded[role]=str(path)
            self.assertEqual(set(audit.loaded_identity(dict(loaded=loaded),sdk,build)),{'kernel','base'})
            staged=build/Path(loaded['kernel']).name;staged.write_bytes(b'changed bytes');loaded['kernel']=str(staged)
            with self.assertRaises(ValueError):audit.loaded_identity(dict(loaded=loaded),sdk,build)

    def test_bytecode_is_excluded_and_source_and_output_overlap_are_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'probe.cpp';source.write_bytes(b'original source');before=audit.snapshot(root)
            (root/'__pycache__').mkdir();(root/'__pycache__/fixture.pyc').write_bytes(b'cache')
            self.assertEqual(audit.snapshot(root),before)
            source.write_bytes(b'changed source');self.assertNotEqual(audit.snapshot(root),before)
            with self.assertRaises(ValueError):audit.private_output(root/'sdk/output',root,root/'sdk',root/'receipt/manifest.json')

    def test_real_late_child_with_plausible_completion_never_passes(self):
        plan,value=self.fixture();text=self.text(value)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);script=root/'child.py';log=root/'run.log'
            script.write_text('import time\nprint('+repr(text)+',flush=True)\ntime.sleep(10)\n',encoding='utf-8')
            code=audit.run_process([sys.executable,str(script)],root,None,log,1)
            self.assertEqual(code,-999)
            self.assertIsNotNone(audit.complete('ordinary',self.nonce,0,log.read_text(),plan))
            self.assertIsNone(audit.complete('ordinary',self.nonce,code,log.read_text(),plan))

    def test_invalid_sdk_fails_before_creating_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);args=['test_gpu_display.py','--root',str(root),'--sdk-report',str(root/'bad.json'),'--output-root',str(root/'output')]
            with mock.patch.object(sys,'argv',args),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:audit.main()
            self.assertEqual(caught.exception.code,2)
            self.assertFalse((root/'output').exists())


if __name__=='__main__':unittest.main()
