# SPDX-License-Identifier: GPL-3.0-only
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import test_ppc_reservations as driver

NONCE = '1' * 32


def completion():
    row = driver.oracle.cases()[0]
    actual = dict(r3=0, cr=row['cr'], so=0, memory=0, guards=True, preserved=True, ns=100)
    value = dict(schema=1, nonce=NONCE, loaded=dict(rexkernel='/sdk/librexkernel.so', rexbase='/sdk/librexbase.so'),
        threads_before=0, threads_after=0, memory_destroyed=True, cases=[dict(id=row['id'], steps=[actual])])
    return [row], value


def text(value):
    return driver.LIBRARIES + json.dumps(dict(nonce=value['nonce'], loaded=value['loaded'])) + '\n' + driver.PREFIX + json.dumps(value) + '\n'


class ReservationEvidenceTests(unittest.TestCase):
    def test_valid_result_and_real_mismatch_are_distinct(self):
        rows, value = completion()
        self.assertEqual(driver.classify(rows, NONCE, 0, text(value))['counts'], {'PASS': 1})
        value['cases'][0]['steps'][0]['r3'] ^= 1
        self.assertEqual(driver.classify(rows, NONCE, 0, text(value))['results'][0]['failures'], ['0:load'])

    def test_wrong_exit_nonce_duplicate_partial_and_sanitizer_cannot_pass(self):
        rows, value = completion()
        good = text(value)
        for code, log in [(1, good), (-1, good), (124, good), (0, good + good), (0, good[:-8]),
                (0, good.replace(NONCE, '2' * 32)), (0, good + 'runtime error: invalid\n'),
                (0, good + 'MW3_RESERVATION_ERROR:bad\n'), (0, good + 'MW3_RESERVATION_INCOMPLETE:' + NONCE)]:
            self.assertIsNone(driver.classify(rows, NONCE, code, log))

    def test_typed_bounded_and_complete_observations_required(self):
        rows, base = completion()
        for key, value in [('r3', True), ('cr', 16), ('so', 2), ('memory', 1 << 32), ('ns', -1), ('guards', 1)]:
            bad = copy.deepcopy(base); bad['cases'][0]['steps'][0][key] = value
            self.assertIsNone(driver.classify(rows, NONCE, 0, text(bad)))
        for key, value in [('schema', True), ('threads_after', 1), ('memory_destroyed', False), ('cases', [])]:
            bad = copy.deepcopy(base); bad[key] = value
            self.assertIsNone(driver.classify(rows, NONCE, 0, text(bad)))
        bad = copy.deepcopy(base); bad['cases'][0]['id'] = 'other'
        self.assertIsNone(driver.classify(rows, NONCE, 0, text(bad)))

    def test_incomplete_control_requires_fresh_library_and_marker_but_allows_sdk_log(self):
        rows, value = completion()
        prefix = driver.LIBRARIES + json.dumps(dict(nonce=NONCE, loaded=value['loaded'])) + '\n'
        log = 'SDK informational line\n' + prefix + 'MW3_RESERVATION_INCOMPLETE:' + NONCE + '\n'
        self.assertTrue(driver.incomplete_control(NONCE, 43, log))
        for code, bad in [(0, log), (43, log + log), (43, log + text(value)),
                (43, log.replace(NONCE, '2' * 32)), (43, log + 'runtime error: invalid')]:
            self.assertFalse(driver.incomplete_control(NONCE, code, bad))
        self.assertIsNone(driver.classify(rows, NONCE, 43, log))

    def test_actual_owned_child_timeout_after_plausible_output_is_refused(self):
        rows, value = completion()
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'run.log'
            code = driver.capture.run_process([sys.executable, '-c',
                'import sys,time;print(sys.argv[1],flush=True);time.sleep(10)', text(value)],
                cwd=folder, env=dict(os.environ), log=log, timeout=0.2)
            self.assertEqual(code, -999)
            self.assertIsNone(driver.classify(rows, NONCE, code, log.read_text()))

    def test_stale_or_changed_reference_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'bins').mkdir(); (root / 'copy').mkdir()
            for name in ('fixtures.o', 'fixtures.elf', 'fixtures.bin', 'fixtures.map'):
                (root / 'bins' / name).write_bytes(b'original fixture')
            sources = {'fixture': {'sha256': '0' * 64}}
            value = dict(task='MW3-047', investigation_complete=True, sources=sources,
                script_sha256=driver.common.sha(driver.__file__), assembly=driver.snapshot(root / 'bins'))
            (root / 'manifest.json').write_text(json.dumps(value))
            driver.reference_bundle(root, root / 'copy', sources)
            with self.assertRaises(ValueError): driver.reference_bundle(root, root / 'copy', {})
            (root / 'bins/fixtures.bin').write_bytes(b'changed')
            with self.assertRaises(ValueError): driver.reference_bundle(root, root / 'copy', sources)

    def test_wrong_loaded_core_bytes_or_location_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); sdk = root / 'sdk'; build = root / 'build'
            (sdk / 'lib').mkdir(parents=True); build.mkdir()
            expected = sdk / 'lib/librexkernel.so'; expected.write_bytes(b'approved')
            loaded = dict(rexkernel=str(expected))
            self.assertEqual(driver.verify_loaded(loaded, sdk, build, False)['rexkernel']['sha256'], driver.common.sha(expected))
            wrong = build / 'librexkernel.so'; wrong.write_bytes(b'wrong')
            with self.assertRaises(ValueError): driver.verify_loaded(dict(rexkernel=str(wrong)), sdk, build, False)


if __name__ == '__main__': unittest.main()
