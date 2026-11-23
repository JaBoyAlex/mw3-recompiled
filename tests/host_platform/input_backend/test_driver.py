# SPDX-License-Identifier: GPL-3.0-only
"""Original protocol guards; no SDL library or physical controller is exercised."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools'))
import test_input_backend as driver


class BackendEvidenceTests(unittest.TestCase):
    nonce='a'*32

    def fixture(self,case='held'):
        return dict(schema=1,case=case,nonce=self.nonce,sdl='original/fixture/SDL',version=3004014,
            cycles=24 if case=='orders' else 2 if case=='restart' else 1,created=driver.CASES[case],cleaned=driver.CASES[case],
            owners=4,sources_after=0,handles_after=0,sdl_after=0,reads=100,rumble_calls=8,rumble_zeros=4,
            late_rejections={'held':2,'hotplug':2,'restart':8,'rumble':2}.get(case,0),checks=100)

    def text(self,value,prefix=driver.COMPLETE):
        return driver.LOADED+json.dumps({k:value[k] for k in ('nonce','sdl','version')})+'\nMW3_BACKEND_READY:'+value['nonce']+'\n'+prefix+json.dumps(value)+'\n'

    def test_exact_complete_case_geometry_and_cleanup(self):
        for case in driver.CASES:
            self.assertIsNotNone(driver.classify(case,self.nonce,0,self.text(self.fixture(case))))
        value=self.fixture()
        for key,bad in [('schema',True),('case','orders'),('cycles',True),('created',5),('cleaned',3),('owners',1),
                        ('sources_after',1),('handles_after',1),('sdl_after',1),('late_rejections',0),('checks',True),('reads',0),('version',3004013)]:
            changed=copy.deepcopy(value);changed[key]=bad
            self.assertIsNone(driver.classify('held',self.nonce,0,self.text(changed)),key)

    def test_partial_duplicate_stale_and_sanitizer_output_reject(self):
        text=self.text(self.fixture())
        for bad in [text.split(driver.COMPLETE)[0],text+text,text.replace(self.nonce,'b'*32),
                    text+'AddressSanitizer: finding\n',text+'runtime error: error\n',text+'MW3_BACKEND_FAILURE:other\n',
                    text.replace('"schema": 1','"schema": 1, "schema": 1')]:
            self.assertIsNone(driver.classify('held',self.nonce,0,bad))
        self.assertIsNone(driver.classify('held',self.nonce,-999,text))

    def test_rumble_controls_require_real_callback_counts(self):
        value=self.fixture('rumble')
        for key,bad in [('rumble_calls',7),('rumble_zeros',3),('rumble_calls',True),('rumble_zeros',9)]:
            changed=copy.deepcopy(value);changed[key]=bad
            self.assertIsNone(driver.classify('rumble',self.nonce,0,self.text(changed)))

    def test_rejection_controls_require_exact_failure_and_completion(self):
        value=self.fixture();wrong=self.text(value,driver.REJECTED)+'MW3_BACKEND_FAILURE:deliberate wrong-route rejected\n'
        self.assertIsNotNone(driver.classify('held',self.nonce,1,wrong,'wrong-route'))
        self.assertIsNone(driver.classify('held',self.nonce,1,wrong.replace('deliberate wrong-route','arbitrary'),'wrong-route'))
        self.assertIsNotNone(driver.classify('held',self.nonce,-999,self.text(value),'deadline'))
        self.assertIsNone(driver.classify('held',self.nonce,0,self.text(value),'deadline'))
        partial=self.text(value).split(driver.COMPLETE)[0]
        self.assertIsNotNone(driver.classify('held',self.nonce,0,partial,'incomplete'))
        self.assertIsNone(driver.classify('held',self.nonce,0,self.text(value),'incomplete'))
        with self.assertRaises(ValueError):driver.classify('unknown',self.nonce,0,partial,'incomplete')
        with self.assertRaises(ValueError):driver.classify('orders',self.nonce,1,wrong,'wrong-route')

    def test_actual_late_child_with_plausible_complete_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);script=root/'child.py';log=root/'run.log';text=self.text(self.fixture())
            script.write_text('import time\nprint('+repr(text)+',flush=True)\ntime.sleep(10)\n',encoding='utf-8')
            code=driver.run_process([sys.executable,str(script)],cwd=root,env=None,log=log,timeout=1)
            self.assertEqual(code,-999)
            self.assertIsNotNone(driver.classify('held',self.nonce,0,log.read_text()))
            self.assertIsNone(driver.classify('held',self.nonce,code,log.read_text()))

    def test_library_path_and_output_overlap_are_guarded(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sdk=root/'sdk';expected=sdk/('bin/SDL3.dll' if sys.platform=='win32' else 'lib/libSDL3.so.0')
            expected.parent.mkdir(parents=True);expected.write_bytes(b'non executable original fixture')
            self.assertEqual(driver.loaded_identity({'sdl':str(expected)},sdk)['sha256'],driver.common.sha(expected))
            wrong=root/'other';wrong.write_bytes(expected.read_bytes())
            with self.assertRaises(ValueError):driver.loaded_identity({'sdl':str(wrong)},sdk)
            with self.assertRaises(ValueError):driver.output_root(root/'cache',root/'receipt/manifest.json',sdk,root/'cache/old-sdk/output')
            with self.assertRaises(ValueError):driver.output_root(root/'cache',root/'receipt/manifest.json',sdk,sdk/'output')

    def test_invalid_profile_rejects_before_output_or_build(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);args=['test_input_backend.py','--root',str(root),'--sdk-report',str(root/'bad.json'),'--output-root',str(root/'output')]
            with mock.patch.object(sys,'argv',args),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:driver.main()
            self.assertEqual(caught.exception.code,2);self.assertFalse((root/'output').exists())


if __name__=='__main__':unittest.main()
