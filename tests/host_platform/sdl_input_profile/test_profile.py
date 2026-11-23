# SPDX-License-Identifier: GPL-3.0-only
"""Original synthetic evidence guards; these do not execute an SDL library."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools'))
import prepare_sdl_input as profile


class SdlProfileEvidenceTests(unittest.TestCase):
    nonce = 'a' * 32

    def fixture(self, mode='repaired'):
        baseline = mode == 'baseline'; rows = []
        for phase in profile.PHASES:
            for pad in range(2):
                held, rest = list(profile.HELD[pad]), [-32768, -32768]
                before = rest if phase == 'rest' or (baseline and phase in ('unchanged', 'second')) else held
                after = rest if phase in ('rest', 'detach') or baseline else held
                rows.append(dict(phase=phase,pad=pad,before=before[:],after=after[:],mapped=[profile.mapped(v) for v in after],
                    stick=0 if phase=='detach' else 1024*(pad+1),button=phase!='detach'))
        return dict(schema=1,mode=mode,nonce=self.nonce,library='original/fixture/SDL-library',version=3004014,
                    created=2,cleaned=2,sdl_after=0,checks=100,rows=rows)

    def text(self, value):
        return (profile.LOADED+json.dumps(dict(nonce=value['nonce'],library=value['library'],version=value['version']))+'\n'+
                'MW3_SDL_READY:'+value['nonce']+'\n'+profile.COMPLETE+json.dumps(value)+'\n')

    def test_repaired_observations_and_original_failure_are_distinct(self):
        fixed, baseline = self.fixture(), self.fixture('baseline')
        self.assertIsNotNone(profile.classify('repaired',self.nonce,0,self.text(fixed)))
        original=self.text(baseline)+'MW3_SDL_FAILURE:original mapping reset observed\n'
        self.assertIsNotNone(profile.classify('baseline',self.nonce,1,original))
        self.assertIsNone(profile.classify('repaired',self.nonce,0,original))
        self.assertIsNone(profile.classify('baseline',self.nonce,0,original))

    def test_changed_raw_mapped_independent_control_and_type_results_reject(self):
        original=self.fixture()
        for field,bad in [('before',[0,0]),('after',[0,0]),('mapped',[0,0]),('stick',0),('button',False),('pad',True),('phase','unknown')]:
            value=copy.deepcopy(original);value['rows'][0][field]=bad
            self.assertIsNone(profile.classify('repaired',self.nonce,0,self.text(value)),field)
        for key,bad in [('schema',True),('created',3),('cleaned',1),('sdl_after',1),('checks',True),('version',3004013),('rows',[])]:
            value=copy.deepcopy(original);value[key]=bad
            self.assertIsNone(profile.classify('repaired',self.nonce,0,self.text(value)),key)

    def test_partial_duplicate_stale_and_diagnostic_output_cannot_pass(self):
        text=self.text(self.fixture())
        for bad in [text.split(profile.COMPLETE)[0],text+text,text.replace(self.nonce,'b'*32),text+'AddressSanitizer: finding\n',
                    text+'runtime error: failure\n',text+'MW3_SDL_FAILURE:other failure\n',text.replace('"schema": 1','"schema": 1, "schema": 1')]:
            self.assertIsNone(profile.classify('repaired',self.nonce,0,bad))
        self.assertIsNone(profile.classify('repaired',self.nonce,-999,text))

    def test_wrong_partial_and_deadline_controls_require_exact_evidence(self):
        wrong=self.text(self.fixture('wrong'))+'MW3_SDL_FAILURE:wrong-zero expectation rejected\n'
        self.assertIsNotNone(profile.classify('wrong',self.nonce,1,wrong))
        self.assertIsNone(profile.classify('wrong',self.nonce,1,wrong.replace('wrong-zero','arbitrary')))
        deadline=self.text(self.fixture('deadline'))
        self.assertIsNotNone(profile.classify('deadline',self.nonce,-999,deadline))
        self.assertIsNone(profile.classify('deadline',self.nonce,0,deadline))
        incomplete=self.text(self.fixture('incomplete')).split(profile.COMPLETE)[0]
        self.assertIsNotNone(profile.classify('incomplete',self.nonce,0,incomplete))
        self.assertIsNone(profile.classify('incomplete',self.nonce,0,incomplete+profile.COMPLETE+'{}\n'))

    def test_actual_late_child_with_complete_record_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);script=root/'late.py';log=root/'run.log';text=self.text(self.fixture())
            script.write_text('import time\nprint('+repr(text)+',flush=True)\ntime.sleep(10)\n',encoding='utf-8')
            code=profile.raw.run_process([sys.executable,str(script)],cwd=root,env=None,log=log,timeout=1)
            self.assertEqual(code,-999)
            self.assertIsNotNone(profile.classify('repaired',self.nonce,0,log.read_text()))
            self.assertIsNone(profile.classify('repaired',self.nonce,code,log.read_text()))

    def test_canonical_source_archive_rejects_traversal_links_and_duplicates(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            def archive(name,entries):
                file=root/name
                with tarfile.open(file,'w') as stream:
                    for entry,data in entries:
                        stream.addfile(entry,io.BytesIO(data) if entry.isfile() else None)
                return file
            valid=tarfile.TarInfo('src/original.c');valid.size=4
            profile.extract_source(archive('ok.tar',[(valid,b'code')]),root/'good')
            self.assertEqual((root/'good/src/original.c').read_bytes(),b'code')
            for name in ('../escape','/absolute','C:escape','a\\escape','NUL.txt','trailing./file'):
                entry=tarfile.TarInfo(name);entry.size=1
                with self.assertRaises(ValueError):profile.extract_source(archive('bad.tar',[(entry,b'x')]),root/'bad')
            link=tarfile.TarInfo('symlink');link.type=tarfile.SYMTYPE;link.linkname='../escape'
            with self.assertRaises(ValueError):profile.extract_source(archive('link.tar',[(link,b'')]),root/'bad')
            with self.assertRaises(ValueError):profile.extract_source(archive('duplicate.tar',[(valid,b'code'),(valid,b'code')]),root/'bad')
            self.assertFalse((root/'bad').exists())

    def test_derived_source_requires_only_the_reviewed_change(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);a=root/'changed.c';a.write_bytes(b'original change');b=root/'untouched.c';b.write_bytes(b'unchanged')
            blob=lambda data:hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            original={'changed.c':blob(a.read_bytes()),'untouched.c':blob(b.read_bytes())}
            self.assertEqual(len(profile.check_derived(root,original,{},changed=False)),2)
            a.write_bytes(b'original change\r\n')
            with self.assertRaises(ValueError):profile.check_derived(root,original,{},changed=False)
            a.write_bytes(b'reviewed derivative');lock={'changed_file':'changed.c','derived_source_sha256':profile.common.sha(a)}
            self.assertEqual(len(profile.check_derived(root,original,lock)),2)
            b.write_bytes(b'other change')
            with self.assertRaises(ValueError):profile.check_derived(root,original,lock)
            b.write_bytes(b'unchanged');a.write_bytes(b'unreviewed derivative')
            with self.assertRaises(ValueError):profile.check_derived(root,original,lock)

    def test_changed_patch_and_invalid_receipt_fail_before_build(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'config';config.mkdir()
            for name in ('lock.json','preserve-trigger.patch','LICENSE.SDL'):(config/name).write_bytes((profile.CONFIG/name).read_bytes())
            with mock.patch.object(profile,'CONFIG',config):
                self.assertEqual(profile.configuration()['version'],3004014)
                (config/'preserve-trigger.patch').write_bytes(b'changed patch')
                with self.assertRaises(ValueError):profile.configuration()
            bad=root/'bad.json';bad.write_text('{}')
            with self.assertRaises(ValueError):profile.verify_prepared(root,bad)
            self.assertFalse((root/'source').exists())

    def test_output_cannot_enter_input_cache_or_maintained_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);cache=root/'cache';source=cache/'source'
            for bad in (cache,cache/'old-sdk/output',source,root):
                with self.assertRaises(ValueError):profile.output_root(cache,bad,source)
            self.assertEqual(profile.output_root(cache,root/'own-output',source),(root/'own-output').resolve())

    def test_loaded_library_path_must_be_the_selected_package(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sdk=root/'sdk';expected=profile.library(sdk);expected.parent.mkdir(parents=True);expected.write_bytes(b'original non executable fixture')
            self.assertEqual(profile.loaded_identity({'library':str(expected)},sdk)['sha256'],profile.common.sha(expected))
            wrong=root/'other';wrong.write_bytes(expected.read_bytes())
            with self.assertRaises(ValueError):profile.loaded_identity({'library':str(wrong)},sdk)

    def test_prepared_receipt_reconciles_packages_sources_logs_and_tools(self):
        # Non-executable, original fixture trees exercise the verifier, not SDL.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);out=root/'profile';stage=out/'source';stage.mkdir(parents=True)
            before=b'original';after=b'reviewed derivative';unchanged=b'unchanged'
            (stage/'mapping.c').write_bytes(after);(stage/'other.c').write_bytes(unchanged)
            blob=lambda data:hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            original_git={'mapping.c':blob(before),'other.c':blob(unchanged)}
            lock=dict(profile='sdl-trigger-v1',changed_file='mapping.c',derived_source_sha256=hashlib.sha256(after).hexdigest(),
                source_files={'mapping.c':hashlib.sha256(before).hexdigest()},original_changed_bytes=len(before),commit='original-fixture-commit',patch_sha256='a'*64)
            derived=profile.files(stage);original=copy.deepcopy(derived);original['mapping.c']={'sha256':hashlib.sha256(before).hexdigest(),'bytes':len(before)}
            packages={}
            for name in ('sdk','baseline-sdk'):
                library=profile.library(out/name);library.parent.mkdir(parents=True);library.write_bytes(b'not an executable '+name.encode())
                packages[name]=profile.files(out/name)
            probe=out/'probe-build/probe';probe.parent.mkdir();probe.write_bytes(b'not executable original probe')
            probe_source=out/'probe-source';probe_source.mkdir();inputs={}
            for name in ('CMakeLists.txt','probe.cpp'):
                (probe_source/name).write_bytes((profile.SOURCE/name).read_bytes());inputs[name]=profile.common.sha(profile.SOURCE/name)
            tool=out/'original-tool';tool.write_bytes(b'not executable original tool')
            results=[]
            plans=[('baseline',i) for i in range(3)]+[('repaired',i) for i in range(3)]+[(m,0) for m in ('wrong','incomplete','deadline')]
            for index,(mode,repeat) in enumerate(plans):
                nonce=f'{index+1:032x}';value=self.fixture(mode);value['nonce']=nonce
                value['library']=str(profile.library(out/('baseline-sdk' if mode=='baseline' else 'sdk')))
                text=self.text(value)
                if mode=='baseline':text+='MW3_SDL_FAILURE:original mapping reset observed\n'
                if mode=='wrong':text+='MW3_SDL_FAILURE:wrong-zero expectation rejected\n'
                if mode=='incomplete':text=text.split(profile.COMPLETE)[0]
                code=1 if mode in ('baseline','wrong') else -999 if mode=='deadline' else 0
                log=out/f'{mode}-{repeat}.log';log.write_text(text,encoding='utf-8')
                results.append(dict(mode=mode,repeat=repeat,nonce=nonce,returncode=code,status='PASS',record=profile.classify(mode,nonce,code,text),
                    loaded=profile.loaded_identity(profile.loading(nonce,text),out/('baseline-sdk' if mode=='baseline' else 'sdk')),log_sha256=profile.common.sha(log)))
            receipt=dict(status='PASS',profile='sdl-trigger-v1',sanitizers=False,script_sha256=profile.common.sha(profile.__file__),
                lock_sha256=profile.common.sha(profile.CONFIG/'lock.json'),sdk_prefix=str(out/'sdk'),original_git_files=original_git,
                original_sources=original,derived_sources=derived,packages=packages,inputs=inputs,probe_name='probe',
                probe_sha256=profile.common.sha(probe),helpers={},tools={'original':{'path':str(tool),'sha256':profile.common.sha(tool)}},
                results=results,compiler={'fixture':'original stdlib data'})
            path=out/'manifest.json'
            def save():path.write_text(json.dumps(receipt),encoding='utf-8')
            save()
            with mock.patch.object(profile,'configuration',return_value=lock),mock.patch.object(profile,'base_source',return_value=(root,original_git)):
                self.assertEqual(profile.verify_prepared(root,path)[0],out/'sdk')
                for target in (profile.library(out/'sdk'),profile.library(out/'baseline-sdk'),stage/'other.c',stage/'mapping.c',probe,tool,out/'repaired-0.log'):
                    data=target.read_bytes();target.write_bytes(data+b'changed')
                    with self.assertRaises(ValueError):profile.verify_prepared(root,path)
                    target.write_bytes(data)
                original_repeat=receipt['results'][0]['repeat'];receipt['results'][0]['repeat']=True;save()
                with self.assertRaises(ValueError):profile.verify_prepared(root,path)
                receipt['results'][0]['repeat']=original_repeat;receipt['sanitizers']=True;save()
                with self.assertRaises(ValueError):profile.verify_prepared(root,path)


if __name__=='__main__':unittest.main()
