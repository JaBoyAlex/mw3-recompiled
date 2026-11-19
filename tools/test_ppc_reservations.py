#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Observe actual selected-translator reservation instructions; retain failures."""
import argparse
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

import recompile as common
import prepare_runtime_memory as memory
import test_rexglue_ppc as ppc
import test_sdk_audio as capture

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tests/ppc_reservations'
GENERATOR = ROOT / 'tests/ppc/generator'
PREFIX = 'MW3_RESERVATION_COMPLETE:'
LIBRARIES = 'MW3_RESERVATION_LIBRARIES:'
spec = importlib.util.spec_from_file_location('reservation_oracle', SOURCE / 'oracle.py')
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def snapshot(path):
    return {n: v for n, v in common.snapshot(path).items() if '__pycache__' not in Path(n).parts}


def library_record(nonce, text):
    value = capture.one_record(text, LIBRARIES)
    if (not isinstance(value, dict) or set(value) != {'nonce', 'loaded'} or value['nonce'] != nonce or
            not isinstance(value['loaded'], dict) or set(value['loaded']) != {'rexkernel', 'rexbase'} or
            any(type(p) is not str or not p or len(p) > 32768 for p in value['loaded'].values())):
        raise ValueError('invalid library record')
    return value['loaded']


def incomplete_control(nonce, code, text):
    try:
        library_record(nonce, text)
        return (code == 43 and capture.clean_output(text) and PREFIX not in text and
            'MW3_RESERVATION_ERROR:' not in text and
            [line for line in text.splitlines() if line.startswith('MW3_RESERVATION_INCOMPLETE:')] ==
            ['MW3_RESERVATION_INCOMPLETE:' + nonce])
    except (ValueError, TypeError, KeyError):
        return False


def classify(rows, nonce, code, text):
    oracle.validate_cases(rows)
    if (not re.fullmatch(r'[0-9a-f]{32}', nonce) or code != 0 or not capture.clean_output(text) or
            'MW3_RESERVATION_ERROR:' in text or 'MW3_RESERVATION_INCOMPLETE:' in text):
        return None
    try:
        loaded = library_record(nonce, text)
        value = capture.one_record(text, PREFIX)
        if (not isinstance(value, dict) or set(value) != {'schema', 'nonce', 'loaded', 'threads_before', 'threads_after', 'memory_destroyed', 'cases'} or
                type(value['schema']) is not int or value['schema'] != 1 or value['nonce'] != nonce or
                value['memory_destroyed'] is not True or type(value['threads_before']) is not int or
                type(value['threads_after']) is not int or not 0 <= value['threads_before'] <= 1024 or
                value['threads_before'] != value['threads_after'] or value['loaded'] != loaded or
                not isinstance(value['loaded'], dict) or set(value['loaded']) != {'rexkernel', 'rexbase'} or
                any(type(p) is not str or not p or len(p) > 32768 for p in value['loaded'].values()) or
                not isinstance(value['cases'], list) or len(value['cases']) != len(rows)):
            return None
        results = []
        for case, row in zip(rows, value['cases']):
            if (not isinstance(row, dict) or set(row) != {'id', 'steps'} or row['id'] != case['id'] or
                    not isinstance(row['steps'], list) or len(row['steps']) != len(case['steps'])):
                return None
            for step in row['steps']:
                if not isinstance(step, dict) or set(step) != {'r3', 'cr', 'so', 'memory', 'guards', 'preserved', 'ns'}:
                    return None
                for key, maximum in (('r3', oracle.MASK64), ('memory', (1 << (case['width'] * 8)) - 1),
                                     ('cr', 15), ('so', 1), ('ns', 30_000_000_000)):
                    if type(step[key]) is not int or not 0 <= step[key] <= maximum:
                        return None
                if type(step['guards']) is not bool or type(step['preserved']) is not bool:
                    return None
            results.append(oracle.evaluate(case, row['steps']))
        return dict(complete=value, results=results, counts=dict(Counter(r['status'] for r in results)))
    except (ValueError, TypeError, KeyError):
        return None


def verify_loaded(value, sdk, build, windows):
    result = {}
    for name, path in value.items():
        target = Path(path).resolve()
        expected = sdk / ('bin' if windows else 'lib') / (name + '.dll' if windows else 'lib' + name + '.so')
        if target.parent not in (expected.parent.resolve(), build.resolve()) or target.name != expected.name or common.sha(target) != common.sha(expected):
            raise ValueError('loaded core differs from approved package')
        result[name] = dict(path=str(target), sha256=common.sha(target))
    return result


def reference_bundle(path, destination, sources):
    receipt = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
    if (receipt.get('task') != 'MW3-047' or not receipt.get('investigation_complete') or
            receipt.get('sources') != sources or receipt.get('script_sha256') != common.sha(__file__) or
            set(receipt.get('assembly', {})) != {'fixtures.o', 'fixtures.elf', 'fixtures.bin', 'fixtures.map'} or
            snapshot(path / 'bins') != receipt['assembly']):
        raise ValueError('stale or incomplete fixture reference')
    for name in receipt['assembly']:
        shutil.copyfile(path / 'bins' / name, destination / name)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('root', 'sdk-report', 'output-root'):
        parser.add_argument('--' + key, required=True, type=Path)
    parser.add_argument('--reference', type=Path, help='Windows: completed canonical Linux fixture receipt, including retained failures')
    parser.add_argument('--sanitizers', action='store_true')
    args = parser.parse_args()
    output = None
    report = dict(schema=1, task='MW3-047', status='IN_PROGRESS', investigation_complete=False,
        game_free=True, title_executed=False, sdk_repaired=False, sdk_instrumented=False,
        sanitizers=args.sanitizers, script_sha256=common.sha(__file__), sources=snapshot(SOURCE),
        generator_adapter=snapshot(GENERATOR), results=[])
    try:
        root = args.root.resolve()
        sdk, identity = memory.verify_prepared(root, args.sdk_report)
        output = common.private_cache(args.output_root, ROOT / '.local/game') / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        shutil.copytree(SOURCE, output / 'maintained', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(__file__, output / 'maintained-driver.py')
        report.update(sdk=identity, sdk_report_sha256=common.sha(args.sdk_report), helpers={
            name: common.sha(ROOT / 'tools' / name) for name in ('recompile.py', 'prepare_runtime_memory.py',
                'test_rexglue_ppc.py', 'test_sdk_audio.py', 'prepare_windows_runtime.py')})
        windows = sys.platform == 'win32'
        source = root / 'sources/rexglue-decommit'
        if windows:
            import prepare_windows_runtime as win
            lock = json.loads(win.LOCK.read_text())
            clang, compiler = win.compiler(root, lock['compiler'], False)
            env, cmake, ninja, report['host'] = win.msvc_environment(lock, clang)
            llvm = clang / 'bin'
            extra = ['-DCMAKE_MAKE_PROGRAM=' + ninja.as_posix(), '-DCMAKE_CXX_FLAGS=-march=x86-64-v2', '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld']
            if args.sanitizers:
                report['calibration'] = win.calibrate_sanitizer(output, clang, env)
        else:
            if sys.platform != 'linux': raise ValueError('unsupported host')
            env, cmake, llvm = dict(os.environ), 'cmake', Path('/usr/lib/llvm-20/bin')
            compiler = dict(sha256=common.sha(llvm / 'clang++'), version=subprocess.check_output([llvm / 'clang++', '--version'], text=True).splitlines()[0])
            extra = ['-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13',
                '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2']
        suffix = '.exe' if windows else ''
        tools = {name: llvm / (name + suffix) for name in ('clang', 'clang++')}
        if not windows:
            tools.update({'ld.lld': llvm / 'ld.lld', **{name: Path('/usr/bin') / (name + '-18')
                for name in ('llvm-objcopy', 'llvm-nm', 'llvm-objdump')}})
        report['tools'] = {n: dict(sha256=common.sha(p), version=subprocess.check_output([p, '--version'], env=env, text=True).splitlines()[0]) for n, p in tools.items()}
        if not re.search(r'clang version 20\.1\.2\b', report['tools']['clang++']['version']):
            raise ValueError('wrong compiler')
        report['compiler'] = compiler
        if args.sanitizers and not windows:
            report['calibration'] = ppc.linux_calibration(output, tools, env)
        report['commands'] = []
        def run(label, command, child=env, timeout=180):
            command = list(map(str, command))
            with (output / (label + '.log')).open('wb') as log:
                result = subprocess.run(command, cwd=output, env=child, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
            report['commands'].append(dict(label=label, command=command, returncode=result.returncode))
            if result.returncode: raise ValueError(label + ' failed')
            return (output / (label + '.log')).read_text(encoding='utf-8', errors='replace')
        bins, generated = output / 'bins', output / 'generated'
        bins.mkdir(); generated.mkdir()
        reference = None
        if windows:
            if not args.reference: raise ValueError('Windows LLVM has no PowerPC assembler; canonical fixture reference required')
            reference = reference_bundle(args.reference, bins, report['sources'])
            report['reference_manifest_sha256'] = common.sha(args.reference / 'manifest.json')
            symbols_text = (bins / 'fixtures.map').read_text(encoding='utf-8')
        else:
            if args.reference: raise ValueError('Linux must assemble original inputs')
            run('assemble', [tools['clang'], '--target=powerpc64-unknown-linux-gnu', '-mcpu=pwr7', '-c', SOURCE / 'fixtures.s', '-o', bins / 'fixtures.o'])
            run('link-ppc', [tools['ld.lld'], '-m', 'elf64ppc', '-Ttext=0x82010000', '-e', 'test_load_w_zero', bins / 'fixtures.o', '-o', bins / 'fixtures.elf'])
            run('binary', [tools['llvm-objcopy'], '--only-section=.text', '-O', 'binary', bins / 'fixtures.elf', bins / 'fixtures.bin'])
            symbols_text = run('symbols', [tools['llvm-nm'], '--numeric-sort', bins / 'fixtures.o'])
            run('disassemble', [tools['llvm-objdump'], '-dr', bins / 'fixtures.elf'])
        symbols, map_lines = {}, []
        for line in symbols_text.splitlines():
            fields = line.split()
            if len(fields) == 3 and fields[1].upper() == 'T' and fields[2].startswith('test_'):
                offset = int(fields[0], 16)
                symbols[fields[2]] = 0x82010000 + offset
                map_lines.append(f'{offset:08x} T {fields[2]}')
        expected_symbols = {f'test_{op}_{width}_{form}' for op in ('load', 'store') for width in ('w', 'd') for form in ('zero', 'index')}
        if set(symbols) != expected_symbols or (bins / 'fixtures.bin').stat().st_size != 64:
            raise ValueError('unexpected instruction inventory')
        (bins / 'fixtures.map').write_bytes(('\n'.join(map_lines) + '\n').encode('ascii'))
        child = {k: v for k, v in env.items() if not k.startswith(('REX_', 'MW3_', 'LD_', 'ASAN_', 'LSAN_', 'UBSAN_'))}
        if windows: child['PATH'] = str(sdk / 'bin') + os.pathsep + child.get('PATH', '')
        else: child['LD_LIBRARY_PATH'] = str(sdk / 'lib')
        # Existing original038 generator adapter, unchanged, under this lane's cache.
        key = common.digest(dict(adapter=report['generator_adapter'], sdk=identity, tools=report['tools']))
        generator_build = output.parent / ('generator-' + key)
        run('configure-generator', [cmake, '-S', GENERATOR, '-B', generator_build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_C_COMPILER=' + tools['clang'].as_posix(), '-DCMAKE_CXX_COMPILER=' + tools['clang++'].as_posix(),
            '-DCMAKE_PREFIX_PATH=' + sdk.as_posix(), '-DMW3_SDK_SOURCE=' + source.as_posix(), '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG', *extra])
        run('build-generator', [cmake, '--build', generator_build, '--target', 'ppc-generator', '--parallel', '2'], timeout=900)
        generator = output / ('ppc-generator' + suffix)
        shutil.copy2(generator_build / generator.name, generator)
        report['generator_sha256'] = common.sha(generator)
        run('generate', [generator, bins / 'fixtures.bin', bins / 'fixtures.map', generated], child)
        emitted = snapshot(generated)
        second = output / 'generated-repeat'; second.mkdir()
        run('generate-repeat', [generator, bins / 'fixtures.bin', bins / 'fixtures.map', second], child)
        if emitted != snapshot(second) or reference is not None and emitted != reference['generated']:
            raise ValueError('emission differs between repeated or cross-host generations')
        report.update(generated=emitted, assembly=snapshot(bins), symbols=symbols, generation_reproduced=True)
        ppc.bindings(generated, symbols)
        build = output / 'build'
        run('configure', [cmake, '-S', output / 'maintained', '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_CXX_COMPILER=' + tools['clang++'].as_posix(), '-DCMAKE_PREFIX_PATH=' + sdk.as_posix(),
            '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
            '-DMW3_GENERATED=' + generated.as_posix(), '-DMW3_JSON_INCLUDE=' + (source / 'thirdparty/inja/third_party/include').as_posix(),
            '-DMW3_RESERVATION_SANITIZERS=' + ('ON' if args.sanitizers else 'OFF'), *extra])
        run('build', [cmake, '--build', build, '--parallel', '2'])
        binary = build / ('ppc-reservations' + suffix)
        report.update(binary_sha256=common.sha(binary), compile_commands_sha256=common.sha(build / 'compile_commands.json'))
        commands = json.loads((build / 'compile_commands.json').read_text())
        guest = next(c['command'] for c in commands if Path(c['file']).name == 'ppc_test_functions.cpp')
        if any(f not in guest for f in ('-fwrapv', '-ffp-contract=off')): raise ValueError('guest policy mismatch')
        plans = [(f'repeat-{n}', 0x20110360, False, None) for n in range(3)]
        plans += [('reversed', 0x20110360, True, None), ('held-out', 0xBADC0DE, False, None),
                  ('wrong-result', 0x20110360, False, 'wrong'), ('incomplete', 0x20110360, False, 'incomplete')]
        child.update(ASAN_OPTIONS='detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        for label, seed, reverse, control in plans:
            lane = output / label; lane.mkdir()
            rows = oracle.cases(seed)
            if control: rows = [rows[0]]  # A real, defined, positive load-only case.
            if reverse: rows.reverse()
            oracle.validate_cases(rows)
            path = lane / 'cases.json'
            path.write_text(json.dumps(rows), encoding='utf-8', newline='\n')
            nonce = uuid.uuid4().hex
            process_env = dict(child, TMP=str(lane), TEMP=str(lane), TMPDIR=str(lane))
            if control == 'wrong': process_env['MW3_RESERVATION_WRONG'] = '1'
            if control == 'incomplete': process_env['MW3_RESERVATION_INCOMPLETE'] = '1'
            code = capture.run_process([str(binary), str(path), nonce], cwd=lane, env=process_env, log=lane / 'run.log', timeout=60)
            text = (lane / 'run.log').read_text(encoding='utf-8', errors='replace')
            record = classify(rows, nonce, code, text)
            loaded = None
            try:
                loaded = verify_loaded(library_record(nonce, text), sdk, build, windows)
            except (OSError, ValueError, TypeError, KeyError):
                record = None
            if control == 'incomplete':
                valid = loaded is not None and incomplete_control(nonce, code, text)
            elif control == 'wrong':
                valid = bool(record and record['counts'] == {'FAIL': 1} and record['results'][0]['failures'] == ['0:load'])
            else:
                valid = record is not None
            status = 'ERROR' if not valid else 'PASS' if control else 'FAIL' if record['counts'].get('FAIL') else 'INCONCLUSIVE' if record['counts'].get('INCONCLUSIVE') else 'PASS'
            row = dict(label=label, seed=seed, reverse=reverse, control=control, nonce=nonce, returncode=code,
                status=status, record=record, loaded=loaded, log_sha256=common.sha(lane / 'run.log'), case_sha256=common.sha(path))
            report['results'].append(row)
            print(json.dumps(dict(label=label, status=status, counts=record['counts'] if record else None)), flush=True)
        _, after = memory.verify_prepared(root, args.sdk_report)
        if (after != identity or snapshot(SOURCE) != report['sources'] or snapshot(GENERATOR) != report['generator_adapter'] or
                common.sha(__file__) != report['script_sha256'] or common.sha(binary) != report['binary_sha256'] or common.sha(generator) != report['generator_sha256'] or
                any(common.sha(ROOT / 'tools' / n) != h for n, h in report['helpers'].items()) or
                any(common.sha(p) != report['tools'][n]['sha256'] for n, p in tools.items())):
            raise ValueError('source, tool, SDK or binary changed')
        report['investigation_complete'] = all(r['status'] != 'ERROR' for r in report['results'])
        report['status'] = 'ERROR' if not report['investigation_complete'] else 'FAIL' if any(r['status'] == 'FAIL' for r in report['results']) else 'INCONCLUSIVE' if any(r['status'] == 'INCONCLUSIVE' for r in report['results']) else 'PASS'
        report['artifacts'] = capture.storage.artifact_snapshot(output)
        (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        return 0 if report['status'] == 'PASS' else 1 if report['investigation_complete'] else 2
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as error:
        report.update(status='ERROR', error=str(error))
        if output: (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        parser.exit(2, f'Reservation diagnostic error: {type(error).__name__}; inspect {output}\n')


if __name__ == '__main__':
    raise SystemExit(main())
