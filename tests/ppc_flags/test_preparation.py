# SPDX-License-Identifier: GPL-3.0-only
"""Original synthetic preparation/receipt faults; these do not load an SDK."""
import contextlib
import copy
import difflib
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import prepare_ppc_flags as flags
import test_ppc_reservations as driver

GIT = shutil.which('git')


class FlagsPreparationTests(unittest.TestCase):
    def test_repository_profile_has_one_explicit_target_and_original_adapter(self):
        lock, files = flags.definition()
        self.assertEqual(lock['source'], 'src/codegen/builder/memory.cpp')
        self.assertEqual(lock['profile'], 'conditional-store-so-v1')
        self.assertEqual(lock['adapter_sha256'], flags.common.sha(flags.ADAPTER))
        self.assertEqual(set(files), {'CMakeLists.txt', 'NOTICE.md', 'atomic-so.patch', 'lock.json'})

    @unittest.skipUnless(GIT, 'Git required for actual exclusive overlay checks')
    def test_actual_patch_is_exclusive_and_preserves_synthetic_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / 'original.txt'; original.write_bytes(b'first\nlast\n')
            after = b'first\ncopy SO\nlast\n'
            patch = root / 'test.patch'
            patch.write_text(''.join(difflib.unified_diff(original.read_text().splitlines(True), after.decode().splitlines(True),
                fromfile='a/' + flags.SOURCE_FILE, tofile='b/' + flags.SOURCE_FILE)), encoding='utf-8', newline='\n')
            lock = dict(source=flags.SOURCE_FILE, before_sha256=flags.common.sha(original),
                after_sha256=hashlib.sha256(after).hexdigest())
            target = flags.apply_overlay(original, root / 'overlay', patch, lock, GIT)
            self.assertEqual(target.read_bytes(), after)
            self.assertEqual(original.read_bytes(), b'first\nlast\n')
            with self.assertRaises(FileExistsError): flags.apply_overlay(original, root / 'overlay', patch, lock, GIT)
            original.write_bytes(b'changed')
            with self.assertRaises(ValueError): flags.apply_overlay(original, root / 'refused', patch, lock, GIT)
            self.assertFalse((root / 'refused').exists())

    @unittest.skipUnless(GIT, 'Git required for actual patch-scope rejection')
    def test_patch_to_another_path_is_refused_before_copying_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); original = root / 'original'; original.write_bytes(b'one\n')
            patch = root / 'wrong.patch'
            patch.write_text('--- a/other.cpp\n+++ b/other.cpp\n@@ -1 +1,2 @@\n one\n+two\n', encoding='utf-8')
            lock = dict(source=flags.SOURCE_FILE, before_sha256=flags.common.sha(original), after_sha256='0' * 64)
            with self.assertRaises(ValueError): flags.apply_overlay(original, root / 'overlay', patch, lock, GIT)
            self.assertFalse((root / 'overlay' / flags.SOURCE_FILE).exists())
            self.assertEqual(original.read_bytes(), b'one\n')

    def fixture(self, root):
        sdk_report = root / 'sdk.json'; sdk_report.write_text('{}')
        original = root / 'sources/rexglue-decommit' / flags.SOURCE_FILE
        original.parent.mkdir(parents=True); original.write_bytes(b'original fixture\n')
        out = root / 'attempt'; out.mkdir()
        overlay = out / 'overlay' / flags.SOURCE_FILE; overlay.parent.mkdir(parents=True); overlay.write_bytes(b'changed fixture\n')
        (out / 'adapter.cpp').write_bytes(b'adapter fixture\n')
        (out / 'project').mkdir(); (out / 'project/CMakeLists.txt').write_bytes(b'CMake fixture\n')
        (out / 'build').mkdir()
        commands = out / 'build/compile_commands.json'
        commands.write_text(json.dumps([dict(file=str(overlay))]))
        binary = out / ('ppc-generator.exe' if sys.platform == 'win32' else 'ppc-generator')
        binary.write_bytes(b'non-executable receipt fixture; never run')
        tool = root / 'tool'; tool.write_bytes(b'non-executable compiler fixture')
        lock = dict(source=flags.SOURCE_FILE, profile='conditional-store-so-v1',
            before_sha256=flags.common.sha(original), after_sha256=flags.common.sha(overlay),
            adapter_sha256=flags.common.sha(out / 'adapter.cpp'))
        inputs = {'CMakeLists.txt': dict(sha256=flags.common.sha(out / 'project/CMakeLists.txt'))}
        sdk = dict(sdk_tree_sha256='1' * 64)
        value = dict(schema=1, task='MW3-048', status='PASS', profile=lock['profile'], host=sys.platform,
            core_modified=False, producer_sha256=flags.common.sha(flags.__file__), profile_files=inputs,
            sdk_report_sha256=flags.common.sha(sdk_report), root=str(root.resolve()), sdk=sdk,
            adapter_sha256=lock['adapter_sha256'], binary_sha256=flags.common.sha(binary),
            compile_commands_sha256=flags.common.sha(commands), compiler=dict(fixture=True),
            tools=dict(fixture=dict(path=str(tool), sha256=flags.common.sha(tool))))
        receipt = out / 'manifest.json'; receipt.write_text(json.dumps(value))
        return receipt, sdk_report, lock, inputs, sdk, value

    def test_receipt_header_mutations_do_not_reach_sdk_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); receipt, sdk_report, lock, inputs, sdk, value = self.fixture(root)
            for key, bad in [('schema', True), ('status', 'ERROR'), ('host', 'other'), ('core_modified', True),
                    ('producer_sha256', '0' * 64), ('profile_files', {}), ('sdk_report_sha256', '0' * 64), ('root', 'other')]:
                changed = dict(value); changed[key] = bad; receipt.write_text(json.dumps(changed))
                with mock.patch.object(flags, 'definition', return_value=(lock, inputs)), mock.patch.object(flags.memory, 'verify_prepared') as verify:
                    with self.assertRaises(ValueError): flags.verify_prepared(root, receipt, sdk_report)
                    verify.assert_not_called()

    def test_artifact_and_sdk_mutations_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); receipt, sdk_report, lock, inputs, sdk, value = self.fixture(root)
            with mock.patch.object(flags, 'definition', return_value=(lock, inputs)), mock.patch.object(flags.memory, 'verify_prepared', return_value=(root / 'sdk', sdk)):
                binary, evidence = flags.verify_prepared(root, receipt, sdk_report)
                self.assertEqual(evidence['profile'], lock['profile'])
                for path in (binary, receipt.parent / 'overlay' / flags.SOURCE_FILE, receipt.parent / 'adapter.cpp',
                        receipt.parent / 'project/CMakeLists.txt', receipt.parent / 'build/compile_commands.json', root / 'tool'):
                    original = path.read_bytes(); path.write_bytes(original + b'changed')
                    with self.assertRaises(ValueError): flags.verify_prepared(root, receipt, sdk_report)
                    path.write_bytes(original)
                changed = dict(value, sdk=dict(sdk_tree_sha256='2' * 64)); receipt.write_text(json.dumps(changed))
                with self.assertRaises(ValueError): flags.verify_prepared(root, receipt, sdk_report)

    def test_invalid_sdk_preparation_creates_no_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); report = root / 'bad.json'; report.write_text('{"status":"ERROR"}')
            args = ['prepare_ppc_flags.py', '--root', str(root), '--sdk-report', str(report), '--output-root', str(root / 'output')]
            with mock.patch.object(sys, 'argv', args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught: flags.main()
            self.assertEqual(caught.exception.code, 2)
            self.assertFalse((root / 'output').exists())

    def test_invalid_opt_in_generator_never_falls_back_to_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            args = ['test_ppc_reservations.py', '--root', str(root), '--sdk-report', str(root / 'sdk.json'),
                '--output-root', str(root / 'output'), '--flags-report', str(root / 'bad.json')]
            with (mock.patch.object(sys, 'argv', args),
                    mock.patch.object(driver.memory, 'verify_prepared', return_value=(root / 'sdk', {})),
                    mock.patch.object(flags, 'verify_prepared', side_effect=ValueError('synthetic unapproved receipt')),
                    contextlib.redirect_stderr(io.StringIO())):
                with self.assertRaises(SystemExit) as caught: driver.main()
            self.assertEqual(caught.exception.code, 2)
            self.assertFalse((root / 'output').exists())

    def test_reference_must_match_the_selected_generator_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'bins').mkdir(); (root / 'copy').mkdir()
            for name in ('fixtures.o', 'fixtures.elf', 'fixtures.bin', 'fixtures.map'):
                (root / 'bins' / name).write_bytes(b'original assembly fixture')
            sources = dict(fixture=True)
            value = dict(task='MW3-047', investigation_complete=True, sources=sources,
                script_sha256=driver.common.sha(driver.__file__), generator_profile='baseline', assembly=driver.snapshot(root / 'bins'))
            (root / 'manifest.json').write_text(json.dumps(value))
            with self.assertRaises(ValueError): driver.reference_bundle(root, root / 'copy', sources, 'conditional-store-so-v1')
            driver.reference_bundle(root, root / 'copy', sources)  # Unchanged default baseline path.


if __name__ == '__main__': unittest.main()
