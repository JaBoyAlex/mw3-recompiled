# SPDX-License-Identifier: GPL-3.0-only
"""Original protocol fixtures and bounded child controls; these do not execute a GPU."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import test_gpu_bootstrap as gpu


class GPUEvidenceTests(unittest.TestCase):
    nonce = 'a' * 32

    def fixture(self, case='bootstrap'):
        inputs = gpu.cases(gpu.SEED)
        cycles = 3 if case == 'lifetime' else 1
        paths = {role: 'private/' + file for role, file in gpu.ROLES.items()}
        device = dict(name='original protocol fixture; no device loaded', vendor=0x10de, device=1, luid_low=2, luid_high=0,
            dedicated_bytes=0, software=False, driver_version=None, driver_version_hresult=1,
            initialization_ns=1, cleanup_ns=1, debug_warnings=0)
        readbacks = [dict(width=w, height=h, pixel_hash=gpu.pixel_hash(w, h, color), pixels=w*h,
            row_pitch=((w*4 + 255)//256)*256, fence=1, completion_ns=1) for w,h,color in inputs] * cycles
        value = dict(schema=1, case=case, nonce=self.nonce, cycles=cycles, pending=0, released_modules=2, sdk_errors=0, sdk_warnings=0, checks=50,
            debug_layer=False, debug_hresult=1, devices=[copy.deepcopy(device) for _ in range(cycles)],
            readbacks=readbacks, loaded=paths)
        return inputs, value

    def text(self, value):
        return (gpu.LIBRARIES + json.dumps(dict(nonce=self.nonce, loaded=value['loaded'])) + '\n' +
            'MW3_GPU_READY:' + self.nonce + '\n' + gpu.COMPLETE + json.dumps(value) + '\n')

    def test_complete_bootstrap_and_repeated_lifecycle_protocol(self):
        for case in ('bootstrap', 'lifetime', 'heldout'):
            inputs, value = self.fixture(case)
            self.assertEqual(gpu.classify(case, self.nonce, 0, self.text(value), inputs), value)

    def test_partial_nonzero_stale_duplicate_and_diagnostic_output_cannot_pass(self):
        inputs, value = self.fixture(); text = self.text(value)
        for code, output in ((1,text),(-999,text),(0,text.replace(self.nonce,'b'*32)),(0,text.split(gpu.COMPLETE)[0]),
                (0,text+gpu.COMPLETE+json.dumps(value)),(0,text+gpu.LIBRARIES+'{}'),
                (0,text+'\nMW3_GPU_FAILURE:failed'),(0,text+'\nAddressSanitizer: diagnostic'),(0,text+'\nruntime error: diagnostic')):
            self.assertIsNone(gpu.classify('bootstrap', self.nonce, code, output, inputs))
        duplicate = text.replace('"schema": 1', '"schema": 1, "schema": 1')
        self.assertIsNone(gpu.classify('bootstrap', self.nonce, 0, duplicate, inputs))

    def test_coercions_unknown_fields_and_unfinished_resources_are_rejected(self):
        inputs, value = self.fixture()
        for key, bad in (('schema',True),('cycles',1.0),('pending',1),('released_modules',1),('sdk_errors',1),('checks',True),('debug_layer',0),('debug_hresult',True),
                         ('devices',[]),('readbacks',[]),('extra',1)):
            changed = copy.deepcopy(value); changed[key] = bad
            self.assertIsNone(gpu.classify('bootstrap',self.nonce,0,self.text(changed),inputs),key)

    def test_wrong_pixel_missing_fence_pitch_and_timing_do_not_pass(self):
        inputs, value = self.fixture()
        for key,bad in (('pixel_hash','0'*16),('pixels',True),('fence',0),('row_pitch',4),('completion_ns',-1),('completion_ns',True)):
            changed=copy.deepcopy(value); changed['readbacks'][0][key]=bad
            self.assertIsNone(gpu.classify('bootstrap',self.nonce,0,self.text(changed),inputs),key)
        changed=copy.deepcopy(value); changed['readbacks'].reverse()
        self.assertIsNone(gpu.classify('bootstrap',self.nonce,0,self.text(changed),inputs))

    def test_software_changed_adapter_and_missing_driver_identity_do_not_pass(self):
        inputs,value=self.fixture('lifetime')
        for key,bad in (('software',True),('vendor',0),('dedicated_bytes',True),('cleanup_ns',-1),('driver_version',True)):
            changed=copy.deepcopy(value); changed['devices'][0][key]=bad
            self.assertIsNone(gpu.classify('lifetime',self.nonce,0,self.text(changed),inputs),key)
        changed=copy.deepcopy(value); changed['devices'][1]['luid_low']+=1
        self.assertIsNone(gpu.classify('lifetime',self.nonce,0,self.text(changed),inputs))

    def test_loaded_module_must_be_actual_approved_package_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); sdk=root/'sdk'; (sdk/'bin').mkdir(parents=True)
            paths={}
            for role,file in gpu.ROLES.items():
                path=sdk/'bin'/file; path.write_bytes(b'non executable path/hash fixture'); paths[role]=str(path)
            result=gpu.loaded_identity(paths,sdk)
            self.assertEqual(set(result),set(gpu.ROLES))
            other=root/'other.dll'; other.write_bytes(b'non executable path/hash fixture')
            paths['provider']=str(other)
            with self.assertRaises(ValueError):gpu.loaded_identity(paths,sdk)

    def test_output_cannot_overlap_source_sdk_or_its_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); sdk=root/'sdk'; receipt=root/'receipt/manifest.json'
            for path in (root,sdk,sdk/'nested',root.parent):
                with self.assertRaises(ValueError):gpu.output_root(path,root,sdk,receipt)
            sibling=root.parent/(root.name+'-output')
            self.assertEqual(gpu.output_root(sibling,root,sdk,receipt),sibling.resolve())

    def test_unknown_case_nonce_and_missing_input_cannot_pass(self):
        inputs,value=self.fixture()
        for case,nonce,rows in (('unknown',self.nonce,inputs),('bootstrap','bad',inputs),('bootstrap',self.nonce,[])):
            with self.assertRaises(ValueError):gpu.classify(case,nonce,0,self.text(value),rows)

    def test_bytecode_cache_is_excluded_but_maintained_source_changes_are_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'probe.cpp'; source.write_bytes(b'original synthetic source')
            before=gpu.source_snapshot(root)
            cache=root/'__pycache__'; cache.mkdir(); (cache/'test.cpython-312.pyc').write_bytes(b'bytecode fixture')
            self.assertEqual(gpu.source_snapshot(root),before)
            source.write_bytes(b'changed source')
            self.assertNotEqual(gpu.source_snapshot(root),before)

    def test_real_child_completion_then_deadline_is_not_success(self):
        inputs,value=self.fixture(); plausible=self.text(value)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); script=root/'child.py'; log=root/'run.log'
            script.write_text('import time\nprint('+repr(plausible)+',flush=True)\ntime.sleep(10)\n',encoding='utf-8')
            code=gpu.run_process([sys.executable,str(script)],cwd=root,env=None,log=log,timeout=1)
            self.assertEqual(code,-999)
            text=log.read_text()
            self.assertIsNotNone(gpu.classify('bootstrap',self.nonce,0,text,inputs))
            self.assertIsNone(gpu.classify('bootstrap',self.nonce,code,text,inputs))

    def test_unapproved_platform_or_sdk_fails_before_output_or_build(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            args=['test_gpu_bootstrap.py','--root',str(root),'--sdk-report',str(root/'bad.json'),'--output-root',str(root/'output')]
            with mock.patch.object(sys,'argv',args),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:gpu.main()
            self.assertEqual(caught.exception.code,2)
            self.assertFalse((root/'output').exists())


if __name__=='__main__':unittest.main()
