#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Exercise the C++20 host adapter through actual SDL, using original virtual devices."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

import prepare_sdl_input as selected
import prepare_windows_runtime as win
import recompile as common
import test_sdk_input as raw
import test_profile_storage as storage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tests/host_platform/input_backend'
CASES = {'held': 4, 'controls': 4, 'orders': 96, 'hotplug': 5, 'restart': 4, 'rumble': 4, 'budget': 17, 'lifetime': 4}
LOADED, COMPLETE, REJECTED = ('MW3_BACKEND_' + k + ':' for k in ('LOADED', 'COMPLETE', 'REJECTED'))
FAILURE = 'MW3_BACKEND_FAILURE:deliberate wrong-route rejected'
run_process = raw.run_process


def inputs():
    paths = {'CMakeLists.txt': SOURCE / 'SDL-CMakeLists.txt', 'contracts.cpp': SOURCE / 'contracts.cpp'}
    for name in ('input/slot_router.hpp', 'input/slot_router.cpp', 'input/ingress/ingress.hpp', 'input/ingress/ingress.cpp',
                 'input/backend/backend.hpp', 'input/backend/backend.cpp', 'input/backend/NOTICE.md'):
        paths['runtime/' + name] = ROOT / 'runtime' / name
    return paths


def one(prefix, text):
    rows = [line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)]
    if len(rows) != 1: return None
    try: return json.loads(rows[0], object_pairs_hook=raw.unique_object)
    except (ValueError, TypeError): return None


def loading(nonce, text):
    value = one(LOADED, text)
    if (not re.fullmatch('[0-9a-f]{32}', nonce) or type(value) is not dict or
            set(value) != {'nonce', 'sdl', 'version'} or value['nonce'] != nonce or
            type(value['version']) is not int or value['version'] != 3004014 or type(value['sdl']) is not str or
            not value['sdl'] or any(c in value['sdl'] for c in '\r\n')): return None
    return value


def record(case, nonce, prefix, text):
    if case not in CASES: raise ValueError('unknown controller case')
    value = one(prefix, text); loaded = loading(nonce, text)
    expected = dict(schema=1, case=case, nonce=nonce, version=3004014, cycles=24 if case == 'orders' else 2 if case == 'restart' else 1,
                    created=CASES[case], cleaned=CASES[case], owners=4, sources_after=0, handles_after=0, sdl_after=0,
                    late_rejections={'held': 2, 'hotplug': 2, 'restart': 8, 'rumble': 2}.get(case, 0))
    metrics = {'reads', 'rumble_calls', 'rumble_zeros', 'checks'}
    if (loaded is None or type(value) is not dict or set(value) != set(expected) | metrics | {'sdl'} or
            any(type(value[k]) is not type(v) or value[k] != v for k, v in expected.items()) or value['sdl'] != loaded['sdl'] or
            any(type(value[k]) is not int or not 0 <= value[k] <= 10_000_000 for k in metrics) or
            value['checks'] < 30 or value['reads'] < (96 if case == 'orders' else 4) or value['rumble_zeros'] > value['rumble_calls']): return None
    if case == 'rumble' and (value['rumble_calls'] < 8 or value['rumble_zeros'] < 4): return None
    if [line for line in text.splitlines() if line.startswith('MW3_BACKEND_READY:')] != ['MW3_BACKEND_READY:' + nonce]: return None
    return value


def classify(case, nonce, code, text, control=''):
    if case not in CASES or (control and case != 'held'): raise ValueError('invalid controller control/case')
    if control not in ('', 'wrong-route', 'incomplete', 'deadline'): raise ValueError('unknown control')
    if any(t in text for t in ('Sanitizer', 'runtime error:', 'end of crash report')): return None
    failures = [line for line in text.splitlines() if line.startswith('MW3_BACKEND_FAILURE:')]
    if control == 'incomplete':
        if (code == 0 and not failures and COMPLETE not in text and REJECTED not in text and loading(nonce, text) and
                [l for l in text.splitlines() if l.startswith('MW3_BACKEND_READY:')] == ['MW3_BACKEND_READY:' + nonce]):
            return {'incomplete_rejected': True}
        return None
    if control == 'wrong-route':
        if code != 1 or failures != [FAILURE] or COMPLETE in text: return None
        return record('held', nonce, REJECTED, text)
    if failures or REJECTED in text or code != (-999 if control == 'deadline' else 0): return None
    return record(case, nonce, COMPLETE, text)


def loaded_identity(value, sdk):
    actual = Path(value['sdl']).resolve(strict=True)
    expected = (sdk / ('bin/SDL3.dll' if sys.platform == 'win32' else 'lib/libSDL3.so.0')).resolve(strict=True)
    if actual != expected or common.sha(actual) != common.sha(expected): raise ValueError('unexpected actual SDL library')
    return dict(path=str(actual), sha256=common.sha(actual), package_path=str(expected))


def output_root(root, receipt, sdk, destination):
    destination = common.private_cache(destination, ROOT / 'game')
    protected = (root.resolve(), receipt.resolve().parent, sdk.resolve(), SOURCE.resolve(), ROOT / 'runtime/input')
    if any(destination == p or destination.is_relative_to(p) or p.is_relative_to(destination) for p in protected):
        raise ValueError('output overlaps maintained source/SDK/preparation')
    if destination.is_relative_to(ROOT) and not destination.is_relative_to(ROOT / '.local'):
        raise ValueError('output enters maintained project')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'sdk-report', 'output-root'): parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--sanitizers', action='store_true')
    parser.add_argument('--repeat', type=int, choices=range(1, 5), default=3)
    args = parser.parse_args(); output = None
    report = dict(schema=1, task='MW3-089', status='IN_PROGRESS', guest_executed=False, physical_devices=False,
                  sdk_modified=False, host_sanitizers=args.sanitizers, script_sha256=common.sha(__file__), results=[])
    try:
        root = args.root.resolve()
        sdk, identity = selected.verify_prepared(root, args.sdk_report, allow_sanitized=args.sanitizers)
        output = output_root(root, args.sdk_report, sdk, args.output_root) / uuid.uuid4().hex; output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        maintained = inputs(); hashes = {name: common.sha(p) for name, p in maintained.items()}; stage = output / 'maintained'
        for name, path in maintained.items():
            p = stage / name; p.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, p)
        shutil.copy2(__file__, output / 'maintained-driver.py')
        helpers = {n: common.sha(ROOT / 'tools' / n) for n in ('prepare_sdl_input.py',
            'prepare_windows_runtime.py', 'recompile.py', 'test_sdk_input.py', 'test_profile_storage.py')}
        windows = sys.platform == 'win32'
        if windows:
            lock = json.loads(win.LOCK.read_text()); clang, compiler = win.compiler(root, lock['compiler'], False)
            env, cmake, ninja, report['host_tools'] = win.msvc_environment(lock, clang); cxx = clang / 'bin/clang++.exe'
            extra = ['-DCMAKE_MAKE_PROGRAM=' + ninja.as_posix(), '-DCMAKE_CXX_FLAGS=-march=x86-64-v2', '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld']
            if args.sanitizers: report['calibration'] = win.calibrate_sanitizer(output, clang, env)
        else:
            if sys.platform != 'linux': raise ValueError('unsupported host')
            env = dict(os.environ); cmake, ninja = shutil.which('cmake'), shutil.which('ninja'); cxx = Path(shutil.which('clang++-20') or 'missing')
            compiler = dict(sha256=common.sha(cxx), version=subprocess.check_output([cxx, '--version'], text=True).splitlines()[0])
            extra = ['-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13',
                     '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2']
        if compiler != identity['compiler']: raise ValueError('compiler differs from selected preparation')
        tools = {n: dict(path=str(p), sha256=common.sha(p), version=subprocess.check_output([str(p), '--version'], env=env, text=True).splitlines()[0])
                 for n, p in dict(cxx=cxx, cmake=cmake, ninja=ninja, git=shutil.which('git')).items()}
        report.update(sdk=identity, sdk_report_sha256=common.sha(args.sdk_report), compiler=compiler, tools=tools,
                      sources=hashes, helpers=helpers, repeat=args.repeat, commands=[])
        build = output / 'build'
        configure = [cmake, '-S', stage, '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_CXX_COMPILER=' + cxx.as_posix(), '-DCMAKE_PREFIX_PATH=' + sdk.as_posix(),
            '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
            '-DMW3_INPUT_SANITIZERS=' + ('ON' if args.sanitizers else 'OFF'), *extra]
        for label, command in [('configure', configure), ('build', [cmake, '--build', build, '--parallel', '2'])]:
            command = list(map(str, command)); report['commands'].append(command)
            with (output / (label + '.log')).open('wb') as log:
                subprocess.run(command, cwd=output, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300, check=True)
        binary = build / ('input-backend-contracts.exe' if windows else 'input-backend-contracts')
        compiled = json.loads((build / 'compile_commands.json').read_text())
        expected = {(stage / p).resolve() for p in hashes if p.endswith('.cpp')}
        if {Path(r['file']).resolve() for r in compiled} != expected or len(compiled) != 4: raise ValueError('unexpected compiled implementation')
        report.update(binary_sha256=common.sha(binary), compile_commands_sha256=common.sha(build / 'compile_commands.json'),
                      cmake_cache_sha256=common.sha(build / 'CMakeCache.txt'))
        plans = [(case, repeat, '') for repeat in range(args.repeat) for case in CASES]
        plans += [('held', 0, control) for control in ('wrong-route', 'incomplete', 'deadline')]
        for case, repeat, control in plans:
            lane = output / (f'{case}-{repeat}' if not control else control)
            for n in ('tmp', 'config', 'data', 'runtime', 'cache', 'profile'): (lane / n).mkdir(parents=True, exist_ok=True)
            child = {k: v for k, v in env.items() if not k.startswith(('REX_', 'MW3_', 'SDL_', 'LD_', 'ASAN_', 'LSAN_', 'UBSAN_'))}
            child.update(TMP=str(lane / 'tmp'), TEMP=str(lane / 'tmp'), TMPDIR=str(lane / 'tmp'), XDG_CONFIG_HOME=str(lane / 'config'),
                XDG_DATA_HOME=str(lane / 'data'), XDG_RUNTIME_DIR=str(lane / 'runtime'), XDG_CACHE_HOME=str(lane / 'cache'),
                APPDATA=str(lane / 'config'), LOCALAPPDATA=str(lane / 'data'), USERPROFILE=str(lane / 'profile'),
                SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', ASAN_OPTIONS='detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            if windows: child['PATH'] = str(sdk / 'bin') + os.pathsep + child.get('PATH', '')
            else: child['LD_LIBRARY_PATH'] = str(sdk / 'lib')
            nonce = uuid.uuid4().hex; command = [str(binary), case, nonce] + (['--' + control] if control else [])
            code = run_process(command, cwd=lane, env=child, log=lane / 'run.log', timeout=8 if control == 'deadline' else 30)
            text = (lane / 'run.log').read_text(errors='replace'); value = classify(case, nonce, code, text, control)
            loader = loading(nonce, text); loaded = loaded_identity(loader, sdk) if loader else None
            row = dict(case=case, repeat=repeat, control=control, nonce=nonce, command=command, returncode=code,
                       status='PASS' if value is not None and loaded else 'FAIL', record=value, loaded=loaded,
                       log_sha256=common.sha(lane / 'run.log'))
            report['results'].append(row); print(json.dumps({k: row[k] for k in ('case', 'repeat', 'control', 'status', 'returncode')}), flush=True)
        _, after = selected.verify_prepared(root, args.sdk_report, allow_sanitized=args.sanitizers)
        if (after != identity or any(common.sha(p) != hashes[n] for n, p in inputs().items()) or
            common.sha(binary) != report['binary_sha256'] or common.sha(__file__) != report['script_sha256'] or
            any(common.sha(ROOT / 'tools' / n) != h for n, h in helpers.items()) or
            any(common.sha(v['path']) != v['sha256'] for v in tools.values())): raise ValueError('source, SDK, producer, tool or binary changed')
        report['status'] = 'PASS' if all(r['status'] == 'PASS' for r in report['results']) else 'FAIL'
        report['artifacts'] = storage.artifact_snapshot(output)
        (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        return 0 if report['status'] == 'PASS' else 1
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        report.update(status='ERROR', error=str(error))
        if output: (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        parser.exit(2, f'Input backend diagnostic failed: {type(error).__name__}; inspect {output}\n')


if __name__ == '__main__': raise SystemExit(main())
