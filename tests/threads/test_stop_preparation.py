# SPDX-License-Identifier: GPL-3.0-only
"""Game-free negative receipt guards; mocks never establish runtime correctness."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import prepare_runtime_stop as stop

class StopPreparationGuards(unittest.TestCase):
    def fixture(self,root):
        sdk=root/'sdk';(sdk/'include').mkdir(parents=True)
        (sdk/'include/inert.h').write_text('original inert header; never compiled\n')
        baseline=root/'baseline.json';baseline.write_text(json.dumps({'compiler':{'inert_fixture':True}}))
        parent=dict(sdk_files=stop.memory.package_files(sdk),core_sanitizers=False)
        receipt=dict(status='PASS',profile=json.loads(stop.LOCK.read_text())['profile'],
            stop_lock_sha256=stop.common.sha(stop.LOCK),script_sha256=stop.common.sha(stop.__file__),
            baseline_report=str(baseline),baseline_report_sha256=stop.common.sha(baseline),baseline_identity=parent,
            source=dict(inert_fixture=True),sdk_prefix=str(sdk),sdk_files=stop.memory.package_files(sdk),core_sanitizers=False)
        receipt['compiler']={'inert_fixture':True}
        path=root/'manifest.json';path.write_text(json.dumps(receipt));return receipt,parent,path

    def test_stale_script_lock_or_failed_receipt_rejected_before_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);original,parent,path=self.fixture(root)
            for key,value in [('script_sha256','0'*64),('stop_lock_sha256','0'*64),('status','FAIL'),('profile','other')]:
                receipt=dict(original);receipt[key]=value;path.write_text(json.dumps(receipt))
                with patch.object(stop.memory,'verify_prepared') as verify,self.assertRaisesRegex(ValueError,'unreviewed'):
                    stop.verify_prepared(root,path)
                verify.assert_not_called()

    def test_changed_header_and_parent_receipt_are_preserved_and_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);receipt,parent,path=self.fixture(root)
            (root/'sdk/include/inert.h').write_text('modified inert header')
            with patch.object(stop.memory,'verify_prepared',return_value=(root/'sdk',parent)),patch.object(stop,'source_identity',return_value=receipt['source']):
                with self.assertRaisesRegex(ValueError,'artifact/header changed'):stop.verify_prepared(root,path)
            self.assertEqual((root/'sdk/include/inert.h').read_text(),'modified inert header')
            (root/'baseline.json').write_text('modified inert receipt')
            with self.assertRaisesRegex(ValueError,'memory receipt changed'):stop.verify_prepared(root,path)

    def test_changed_parent_identity_or_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);receipt,parent,path=self.fixture(root)
            with patch.object(stop.memory,'verify_prepared',return_value=(root/'sdk',dict(parent,changed=True))):
                with self.assertRaisesRegex(ValueError,'baseline changed'):stop.verify_prepared(root,path)
            with patch.object(stop.memory,'verify_prepared',return_value=(root/'sdk',parent)),patch.object(stop,'source_identity',return_value={'changed':True}):
                with self.assertRaisesRegex(ValueError,'source changed'):stop.verify_prepared(root,path)

    def test_core_profile_cannot_be_mislabeled_or_accepted_without_opt_in(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);receipt,parent,path=self.fixture(root)
            receipt['core_sanitizers']=True;path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,'validation-only'):stop.verify_prepared(root,path)
            receipt['core_sanitizers']=False
            parent['core_sanitizers']=True;receipt['baseline_identity']=parent;path.write_text(json.dumps(receipt))
            with patch.object(stop.memory,'verify_prepared',return_value=(root/'sdk',parent)):
                with self.assertRaisesRegex(ValueError,'instrumentation differs'):stop.verify_prepared(root,path,allow_sanitized=True)

    def test_tampered_composition_is_not_silently_repaired(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/'combined-stop.patch';p.write_bytes(b'original inert changed composition')
            with self.assertRaisesRegex(ValueError,'composition changed'):stop.source_identity(root,root,False,existing=True)
            self.assertEqual(p.read_bytes(),b'original inert changed composition')
