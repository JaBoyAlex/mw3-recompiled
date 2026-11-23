#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Audit actual selected-kernel display queries; never admit services or execute a title."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

import prepare_runtime_xma as selected
import prepare_windows_runtime as win
import recompile as common
import test_profile_storage as storage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tests/gpu_display'
spec = importlib.util.spec_from_file_location('mw3_display_oracle', SOURCE / 'oracle.py')
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
COMPLETE, LIBRARIES, ARMED = ('MW3_DISPLAY_' + suffix + ':' for suffix in ('COMPLETE', 'LIBRARIES', 'ARMED'))
BOUNDARIES = {'null-mode': 0, 'guard-display': 1, 'readonly-gamma': 2, 'wrap-mode': 0, 'misaligned-display': 1}
SEED = 0x51c0de


def snapshot(path):
    return {n: v for n, v in common.snapshot(path).items() if '__pycache__' not in Path(n).parts}


def integer(value, low=0, high=2**64-1):
    return type(value) is int and low <= value <= high


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value: raise ValueError('duplicate observation key')
        value[key] = item
    return value


def record(text, prefix):
    rows = [line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)]
    if len(rows) != 1: raise ValueError('missing or repeated observation')
    return json.loads(rows[0], object_pairs_hook=unique)


def library_record(nonce, text):
    value = record(text, LIBRARIES)
    expected = [dict(name=name, ordinal=ordinal) for name, ordinal in oracle.SERVICES]
    if (type(value) is not dict or set(value) != {'nonce', 'loaded', 'exports'} or value['nonce'] != nonce or
            value['exports'] != expected or type(value['loaded']) is not dict or set(value['loaded']) != {'kernel', 'base'} or
            any(type(p) is not str or not p or '\n' in p or '\r' in p for p in value['loaded'].values())):
        raise ValueError('unapproved actual export/library binding')
    # bool/float equality must not masquerade as the integer ordinal identity.
    if any(type(row) is not dict or set(row) != {'name', 'ordinal'} or type(row['ordinal']) is not int for row in value['exports']):
        raise ValueError('invalid export tuple types')
    return value


def loaded_identity(value, sdk, build):
    result = {}
    windows = sys.platform == 'win32'
    for role, name in {'kernel': 'rexkernel', 'base': 'rexbase'}.items():
        filename = name + '.dll' if windows else 'lib' + name + '.so'
        expected = (sdk / ('bin' if windows else 'lib') / filename).resolve(strict=True)
        actual = Path(value['loaded'][role]).resolve(strict=True)
        if actual != expected and not (actual.is_relative_to(build.resolve()) and actual.name.lower() == expected.name.lower()):
            raise ValueError('unexpected actual SDK module path')
        if common.sha(actual) != common.sha(expected): raise ValueError('actual SDK module bytes differ')
        result[role] = dict(path=str(actual), sha256=common.sha(actual), package_path=str(expected))
    return result


def clean(text):
    return not any(t in text for t in ('MW3_DISPLAY_FAILURE:', 'AddressSanitizer', 'LeakSanitizer', 'UndefinedBehaviorSanitizer', 'runtime error:', 'end of crash report'))


def complete(case, nonce, code, text, plan):
    if case not in ('ordinary', 'wrong-result', 'deadline', 'misaligned-display', *BOUNDARIES) or not re.fullmatch('[0-9a-f]{32}', nonce):
        raise ValueError('unknown display case or nonce')
    if code != 0 or not clean(text): return None
    try:
        libs = library_record(nonce, text)
        value = record(text, COMPLETE)
        if (type(value) is not dict or set(value) != {'schema', 'case', 'nonce', 'pages_before', 'pages_after',
                'objects_before', 'objects_after', 'runtime_loaded_after', 'sdk_errors', 'sdk_warnings', 'load_ns', 'teardown_ns',
                'rows', 'loaded', 'exports'} or type(value['schema']) is not int or value['schema'] != 1 or
                value['case'] != case or value['nonce'] != nonce or value['loaded'] != libs['loaded'] or value['exports'] != libs['exports'] or
                value['runtime_loaded_after'] is not False or type(value['sdk_errors']) is not int or value['sdk_errors'] != 0 or
                any(not integer(value[k]) for k in ('pages_before', 'pages_after', 'objects_before', 'objects_after', 'sdk_warnings')) or
                any(not integer(value[k], 0, 30_000_000_000) for k in ('load_ns', 'teardown_ns')) or
                type(value['rows']) is not list or
                [line for line in text.splitlines() if line.startswith('MW3_DISPLAY_READY:')] != ['MW3_DISPLAY_READY:' + nonce]):
            return None
        if value['pages_before'] != value['pages_after'] or value['objects_before'] != value['objects_after']:
            return None
        expected_rows = 1 if case == 'misaligned-display' else 0 if case in BOUNDARIES else len(plan)
        if len(value['rows']) != expected_rows: return None
        failures = []
        if case not in BOUNDARIES:
            if len(plan) != 128: raise ValueError('exact original plan required')
            for index, (row, (service, offset)) in enumerate(zip(value['rows'], plan)):
                for reason in oracle.check_row(row, service, offset): failures.append(f'{index}:{reason}')
        elif case == 'misaligned-display':
            # Observable return is still not retail alignment compatibility.
            row = value['rows'][0]
            for reason in oracle.check_row(row, 1, 16):
                if reason != 'output-extent/endian/canary': failures.append('0:' + reason)
            if bytes.fromhex(row['bytes']) != oracle.expected(1,17): failures.append('0:misaligned-bytes')
        return dict(complete=value, failures=failures)
    except (ValueError, TypeError, KeyError):
        return None


def boundary(case, nonce, code, text, plan):
    if case not in BOUNDARIES: raise ValueError('unknown boundary case')
    armed = record(text, ARMED)
    if (type(armed) is not dict or set(armed) != {'nonce', 'case', 'service', 'pointer'} or armed['nonce'] != nonce or
            armed['case'] != case or type(armed['service']) is not int or armed['service'] != BOUNDARIES[case] or
            not integer(armed['pointer'], 0, 2**32-1) or (case == 'null-mode' and armed['pointer'] != 0) or
            (case == 'wrap-mode' and armed['pointer'] != 0xfffffff0)):
        raise ValueError('invalid armed boundary identity')
    if code == -999: return dict(observation='OWNED_PROCESS_TIMEOUT', armed=armed, compatibility_passed=False)
    if code != 0 and COMPLETE not in text and 'MW3_DISPLAY_FAILURE:' not in text:
        return dict(observation='TERMINATED_AFTER_ARM', armed=armed, compatibility_passed=False,
            sanitizer_diagnostic=any(t in text for t in ('Sanitizer', 'runtime error:')))
    value = complete(case, nonce, code, text, plan)
    if value is None: raise ValueError('unverified boundary termination/return')
    return dict(observation='RETURNED', armed=armed, compatibility_passed=False, record=value)


def run_process(command, cwd, env, log, timeout):
    with Path(log).open('wb') as stream:
        try: return subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired: return -999


def private_output(path, root, sdk, receipt):
    path = common.private_cache(path, ROOT / '.local/game')
    if any(path == p or path.is_relative_to(p) or p.is_relative_to(path) for p in (root, sdk.resolve(), receipt.parent.resolve(), SOURCE.resolve())):
        raise ValueError('output overlaps source/SDK/preparation')
    if path.is_relative_to(ROOT) and not path.is_relative_to(ROOT / '.local'):
        raise ValueError('output enters maintained project paths')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'sdk-report', 'output-root'): parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--sanitizers', action='store_true')
    args = parser.parse_args(); output = None
    report = dict(schema=1, task='MW3-051', status='IN_PROGRESS', investigation_complete=False,
        evidence_class='original synthetic guest callbacks into actual kernel exports', owned_title_executed=False,
        sdk_modified=False, services_admitted=False, script_sha256=common.sha(__file__), host_sanitizers=args.sanitizers, results=[])
    try:
        root = args.root.resolve()
        sdk, identity = selected.verify_prepared(root, args.sdk_report, allow_sanitized=args.sanitizers)
        output = private_output(args.output_root, root, sdk, args.sdk_report) / uuid.uuid4().hex; output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        shutil.copytree(SOURCE, output / 'maintained', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(__file__, output / 'maintained-driver.py')
        sources = snapshot(output / 'maintained')
        helpers = {n: common.sha(ROOT / 'tools' / n) for n in ('prepare_runtime_xma.py', 'prepare_runtime_stop.py',
            'prepare_runtime_memory.py', 'prepare_windows_runtime.py', 'recompile.py', 'test_profile_storage.py')}
        windows = sys.platform == 'win32'
        if windows:
            clang, compiler = win.compiler(root, json.loads(win.LOCK.read_text())['compiler'], False)
            env, cmake, ninja, host = win.msvc_environment(json.loads(win.LOCK.read_text()), clang); cxx = clang / 'bin/clang++.exe'
            extra = ['-DCMAKE_MAKE_PROGRAM=' + ninja.as_posix(), '-DCMAKE_CXX_FLAGS=-march=x86-64-v2', '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld']
            report['host_tools'] = host
            if args.sanitizers: report['calibration'] = win.calibrate_sanitizer(output, clang, env)
        else:
            if sys.platform != 'linux': raise ValueError('unsupported host')
            env = dict(os.environ); cmake, ninja = shutil.which('cmake'), shutil.which('ninja'); cxx = Path('/usr/lib/llvm-20/bin/clang++')
            compiler = dict(sha256=common.sha(cxx), version=subprocess.check_output([cxx, '--version'], text=True).splitlines()[0])
            if not re.search(r'clang version 20\.1\.2\b', compiler['version']): raise ValueError('compiler differs')
            extra = ['-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13',
                '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2']
        tools = {}
        for name, p in dict(cxx=cxx, cmake=cmake, ninja=ninja, git=shutil.which('git')).items():
            p = Path(p); tools[name] = dict(path=str(p), sha256=common.sha(p), version=subprocess.check_output([p, '--version'], env=env, text=True).splitlines()[0])
        source = root / 'sources/rexglue-xma'; build = output / 'build'
        declarations = {p: common.sha(source / p) for p in ('src/kernel/xboxkrnl/xboxkrnl_video.cpp',
            'src/kernel/xboxkrnl/export_table.inc', 'include/rex/kernel/xboxkrnl.h', 'include/rex/ppc/call.h')}
        report.update(sdk=identity, sdk_report_sha256=common.sha(args.sdk_report), sources=sources, helpers=helpers,
            declarations=declarations, compiler=compiler, tools=tools, commands=[])
        configure = [cmake, '-S', output / 'maintained', '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_CXX_COMPILER=' + cxx.as_posix(), '-DCMAKE_PREFIX_PATH=' + sdk.as_posix(), '-DMW3_SDK_SOURCE=' + source.as_posix(),
            '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
            '-DMW3_DISPLAY_SANITIZERS=' + ('ON' if args.sanitizers else 'OFF'), *extra]
        for label, command in [('configure', configure), ('build', [cmake, '--build', build, '--parallel', '2'])]:
            command = list(map(str, command)); report['commands'].append(command)
            with (output / (label + '.log')).open('wb') as log:
                subprocess.run(command, env=env, cwd=output, stdout=log, stderr=subprocess.STDOUT, timeout=300, check=True)
        binary = build / ('display-queries.exe' if windows else 'display-queries')
        commands = json.loads((build / 'compile_commands.json').read_text())
        for row in commands:
            path = Path(row['file']).resolve()
            if path != (output / 'maintained/probe.cpp').resolve() and not (path.name == 'rexglue_host_alloc_stub.cpp' and path.is_relative_to(sdk.resolve())):
                raise ValueError('unexpected compiled source; kernel objects are forbidden')
        if not any(Path(r['file']).name == 'probe.cpp' for r in commands): raise ValueError('original callback not compiled')
        report.update(binary_sha256=common.sha(binary), compile_commands_sha256=common.sha(build / 'compile_commands.json'))
        plans = [(f'repeat-{i}', SEED, False, 'ordinary') for i in range(3)]
        plans += [('reversed', SEED, True, 'ordinary'), ('heldout', 0x5eed051, False, 'ordinary')]
        plans += [(case, SEED, False, case) for case in (*BOUNDARIES, 'wrong-result', 'incomplete', 'deadline')]
        for label, seed, reverse, case in plans:
            lane = output / label
            for directory in ('tmp', 'config', 'data', 'runtime', 'cache', 'profile'): (lane / directory).mkdir(parents=True, exist_ok=True)
            plan = oracle.plan(seed, reverse); path = lane / 'plan.txt'
            path.write_text(''.join(f'{service} {offset}\n' for service, offset in plan), encoding='ascii', newline='\n')
            child = {k: v for k, v in env.items() if not k.startswith(('REX_', 'MW3_', 'SDL_', 'LD_', 'ASAN_', 'LSAN_', 'UBSAN_'))}
            child.update(TMP=str(lane / 'tmp'), TEMP=str(lane / 'tmp'), TMPDIR=str(lane / 'tmp'), XDG_CONFIG_HOME=str(lane / 'config'),
                XDG_DATA_HOME=str(lane / 'data'), XDG_RUNTIME_DIR=str(lane / 'runtime'), XDG_CACHE_HOME=str(lane / 'cache'),
                APPDATA=str(lane / 'config'), LOCALAPPDATA=str(lane / 'data'), USERPROFILE=str(lane / 'profile'),
                SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', ASAN_OPTIONS='detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            if windows: child['PATH'] = str(sdk / 'bin') + os.pathsep + child.get('PATH', '')
            else: child['LD_LIBRARY_PATH'] = str(sdk / 'lib')
            nonce = uuid.uuid4().hex; command = list(map(str, (binary, case, nonce, path))); timeout = 8 if case == 'deadline' else 45
            attempt = dict(label=label, seed=seed, reverse=reverse, case=case, nonce=nonce, command=command,
                timeout=timeout, plan_sha256=common.sha(path), status='IN_PROGRESS'); report['results'].append(attempt)
            code = run_process(command, lane, child, lane / 'run.log', timeout)
            text = (lane / 'run.log').read_text(encoding='utf-8', errors='replace')
            attempt.update(returncode=code, log_sha256=common.sha(lane / 'run.log'))
            libs = library_record(nonce, text); loaded = loaded_identity(libs, sdk, build)
            value = None; disposition = None
            if case in BOUNDARIES:
                disposition = boundary(case, nonce, code, text, plan); status = 'OBSERVED_BOUNDARY'
            elif case == 'incomplete':
                status = 'EXPECTED_CONTROL_PASS' if code == 0 and clean(text) and COMPLETE not in text and text.splitlines().count('MW3_DISPLAY_READY:' + nonce) == 1 else 'ERROR'
            elif case == 'deadline':
                value = complete(case, nonce, 0, text, plan)
                status = 'EXPECTED_CONTROL_PASS' if code == -999 and value and not value['failures'] else 'ERROR'
            else:
                value = complete(case, nonce, code, text, plan)
                if case == 'wrong-result': status = 'EXPECTED_CONTROL_PASS' if value and value['failures'] == ['0:output-extent/endian/canary'] else 'ERROR'
                else: status = 'ERROR' if value is None else 'FAIL' if value['failures'] else 'PASS'
            attempt.update(status=status, loaded=loaded, record=value, boundary=disposition)
            print(json.dumps(dict(label=label, status=status, returncode=code, failures=value['failures'] if value else None,
                boundary=disposition['observation'] if disposition else None)), flush=True)
        _, after = selected.verify_prepared(root, args.sdk_report, allow_sanitized=args.sanitizers)
        if (after != identity or snapshot(SOURCE) != sources or common.sha(__file__) != report['script_sha256'] or
                common.sha(binary) != report['binary_sha256'] or any(common.sha(ROOT / 'tools' / n) != h for n, h in helpers.items()) or
                any(common.sha(source / n) != h for n, h in declarations.items()) or any(common.sha(Path(t['path'])) != t['sha256'] for t in tools.values())):
            raise ValueError('source, producer, tools, binary or SDK changed')
        report['investigation_complete'] = all(r['status'] != 'ERROR' for r in report['results'])
        report['declared_default_policy_passed'] = all(r['status'] == 'PASS' for r in report['results'] if r['case'] == 'ordinary')
        # An observed invalid/unaligned return or termination cannot pass a console/containment gate.
        report['status'] = 'INCONCLUSIVE' if report['investigation_complete'] else 'ERROR'
        if any(r['status'] == 'FAIL' for r in report['results']): report['status'] = 'FAIL'
        report['artifacts'] = storage.artifact_snapshot(output)
        (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        return 2 if not report['investigation_complete'] else 1
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        report.update(status='ERROR', error=str(error))
        if output: (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        parser.exit(2, f'Display query audit failed: {type(error).__name__}; inspect {output}\n')


if __name__ == '__main__': raise SystemExit(main())
