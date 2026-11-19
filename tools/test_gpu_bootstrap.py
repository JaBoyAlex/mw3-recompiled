#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Run original bounded D3D12 readback on the unchanged native SDK's actual device."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import uuid

import prepare_runtime_memory as memory
import prepare_windows_runtime as win
import recompile as common
import test_profile_storage as storage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tests/gpu_bootstrap'
COMPLETE = 'MW3_GPU_COMPLETE:'
LIBRARIES = 'MW3_GPU_LIBRARIES:'
ROLES = {'provider': 'rexgpu-xenos-d3d12.dll', 'graphics': 'rexgpu.dll', 'base': 'rexbase.dll'}
SEED = 0x50504350


def source_snapshot(path):
    return {name: value for name, value in common.snapshot(path).items() if '__pycache__' not in Path(name).parts}


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value: raise ValueError('duplicate result key')
        value[key] = item
    return value


def record(text, prefix):
    rows = [line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)]
    if len(rows) != 1: raise ValueError('missing or repeated record')
    return json.loads(rows[0], object_pairs_hook=unique)


def integer(value, low=0, high=2**63 - 1):
    return type(value) is int and low <= value <= high


def clean(text):
    return not any(token in text for token in ('MW3_GPU_FAILURE:', 'Sanitizer', 'runtime error:', 'end of crash report'))


def cases(seed):
    # Original deterministic inputs; no shader/game bytes or guest geometry.
    colors = [(0, 0, 0, 0), (255, 255, 255, 255), (17, 85, 170, 255), (254, 1, 127, 128)]
    for _ in range(4):
        color = []
        for _ in range(4):
            seed = (1664525 * seed + 1013904223) & 0xffffffff
            color.append(seed >> 24)
        colors.append(tuple(color))
    return [(width, height, color) for (width, height), color in zip(
        ((1, 1), (17, 7), (31, 9), (65, 33), (3, 5), (63, 17), (64, 8), (19, 13)), colors)]


def pixel_hash(width, height, color):
    result = 14695981039346656037
    for byte in bytes(color) * (width * height): result = ((result ^ byte) * 1099511628211) & (2**64 - 1)
    return f'{result:016x}'


def libraries(nonce, text):
    value = record(text, LIBRARIES)
    if (type(value) is not dict or set(value) != {'nonce', 'loaded'} or value['nonce'] != nonce or
            type(value['loaded']) is not dict or set(value['loaded']) != set(ROLES) or
            any(type(p) is not str or not p or '\n' in p or '\r' in p for p in value['loaded'].values())):
        raise ValueError('invalid loaded-module record')
    return value['loaded']


def classify(case, nonce, code, text, inputs):
    if case not in ('bootstrap', 'heldout', 'lifetime') or not re.fullmatch('[0-9a-f]{32}', nonce):
        raise ValueError('unknown case or nonce')
    if len(inputs) != 8: raise ValueError('eight bounded original input rows required')
    if code != 0 or not clean(text): return None
    try:
        loaded = libraries(nonce, text)
        value = record(text, COMPLETE)
        cycles = 3 if case == 'lifetime' else 1
        if (type(value) is not dict or set(value) != {'schema', 'case', 'nonce', 'cycles', 'pending', 'checks',
                'released_modules', 'sdk_errors', 'sdk_warnings',
                'debug_layer', 'debug_hresult', 'devices', 'readbacks', 'loaded'} or
                type(value['schema']) is not int or value['schema'] != 1 or value['case'] != case or value['nonce'] != nonce or
                type(value['cycles']) is not int or value['cycles'] != cycles or type(value['pending']) is not int or value['pending'] != 0 or
                type(value['released_modules']) is not int or value['released_modules'] != 2 or
                type(value['sdk_errors']) is not int or value['sdk_errors'] != 0 or not integer(value['sdk_warnings']) or
                not integer(value['checks'], 50) or type(value['debug_layer']) is not bool or not integer(value['debug_hresult'], 0, 2**32 - 1) or
                (value['debug_hresult'] == 0) != value['debug_layer'] or value['loaded'] != loaded or
                type(value['devices']) is not list or len(value['devices']) != cycles or
                type(value['readbacks']) is not list or len(value['readbacks']) != cycles * len(inputs) or
                [line for line in text.splitlines() if line.startswith('MW3_GPU_READY:')] != ['MW3_GPU_READY:' + nonce]):
            return None
        identities = []
        for device in value['devices']:
            if (type(device) is not dict or set(device) != {'name', 'vendor', 'device', 'luid_low', 'luid_high', 'dedicated_bytes',
                    'software', 'driver_version', 'driver_version_hresult', 'initialization_ns', 'cleanup_ns', 'debug_warnings'} or
                    type(device['name']) is not str or not device['name'] or device['software'] is not False or
                    not integer(device['vendor'], 1, 65535) or not integer(device['device'], 1, 65535) or
                    not integer(device['luid_low'], 0, 2**32 - 1) or not integer(device['luid_high'], -2**31, 2**31 - 1) or
                    not integer(device['dedicated_bytes']) or not integer(device['driver_version_hresult'], 0, 2**32 - 1) or
                    not integer(device['initialization_ns'], 0, 30_000_000_000) or not integer(device['cleanup_ns'], 0, 30_000_000_000) or
                    not integer(device['debug_warnings'], 0, 4095) or
                    (device['driver_version'] is not None and not integer(device['driver_version'])) or
                    (device['driver_version_hresult'] == 0) != (device['driver_version'] is not None)):
                return None
            identities.append({k: v for k, v in device.items() if k not in ('initialization_ns', 'cleanup_ns', 'debug_warnings')})
        if any(device != identities[0] for device in identities): return None
        for actual, (width, height, color) in zip(value['readbacks'], inputs * cycles):
            if (type(actual) is not dict or set(actual) != {'width', 'height', 'pixel_hash', 'pixels', 'row_pitch', 'fence', 'completion_ns'} or
                    any(type(actual[k]) is not int or actual[k] != expected for k, expected in
                        {'width': width, 'height': height, 'pixels': width * height, 'fence': 1}.items()) or
                    actual['pixel_hash'] != pixel_hash(width, height, color) or
                    not integer(actual['row_pitch'], width * 4, 1024 * 1024) or actual['row_pitch'] % 256 or
                    not integer(actual['completion_ns'], 0, 5_000_000_000)):
                return None
        return value
    except (ValueError, KeyError, TypeError):
        return None


def loaded_identity(paths, sdk):
    result = {}
    for role, name in ROLES.items():
        expected = (sdk / 'bin' / name).resolve(strict=True)
        actual = Path(paths[role]).resolve(strict=True)
        if actual != expected: raise ValueError('loaded SDK module does not match approved package')
        result[role] = dict(path=str(actual), sha256=common.sha(actual))
    return result


def run_process(command, *, cwd, env, log, timeout):
    with Path(log).open('wb') as stream:
        try:
            return subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            return -999  # subprocess.run kills and waits only for its own direct child.


def output_root(path, root, sdk, receipt):
    path = common.private_cache(path, ROOT / '.local/game')
    if any(path == p or path.is_relative_to(p) or p.is_relative_to(path)
           for p in (root.resolve(), sdk.resolve(), receipt.parent.resolve(), SOURCE.resolve())):
        raise ValueError('output overlaps SDK/source/preparation')
    if path.is_relative_to(ROOT) and not path.is_relative_to(ROOT / '.local'):
        raise ValueError('output must not enter maintained project paths')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'sdk-report', 'output-root'): parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--sanitizers', action='store_true')
    args = parser.parse_args()
    output = None
    report = dict(schema=1, task='MW3-050', status='IN_PROGRESS', game_free=True, guest_executed=False,
        xenos_commands=False, sdk_modified=False, host_ubsan=args.sanitizers, script_sha256=common.sha(__file__), results=[])
    try:
        if sys.platform != 'win32': raise ValueError('native Windows D3D12 required; other platforms are NOT RUN')
        root = args.root.resolve()
        sdk, identity = memory.verify_prepared(root, args.sdk_report)
        output = output_root(args.output_root, root, sdk, args.sdk_report) / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        shutil.copytree(SOURCE, output / 'maintained', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(__file__, output / 'maintained-driver.py')
        sources = source_snapshot(output / 'maintained')
        helpers = {name: common.sha(ROOT / 'tools' / name) for name in
            ('prepare_runtime_memory.py', 'prepare_windows_runtime.py', 'recompile.py', 'test_profile_storage.py')}
        lock = json.loads(win.LOCK.read_text())
        clang, compiler = win.compiler(root, lock['compiler'], False)
        env, cmake, ninja, host = win.msvc_environment(lock, clang)
        tools = {}
        for name, path in dict(cxx=clang / 'bin/clang++.exe', cmake=cmake, ninja=ninja, git=shutil.which('git')).items():
            path = Path(path)
            tools[name] = dict(path=str(path), sha256=common.sha(path), version=subprocess.check_output([path, '--version'], env=env, text=True).splitlines()[0])
        report.update(sdk=identity, sdk_report_sha256=common.sha(args.sdk_report), sources=sources, helpers=helpers,
            compiler=compiler, tools=tools, host_tools=host, python=sys.version, os=platform.platform(), commands=[])
        inventory = 'Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion | ConvertTo-Json -Compress'
        report['system_gpu_inventory'] = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', inventory], text=True))
        if args.sanitizers: report['calibration'] = win.calibrate_sanitizer(output, clang, env)
        source = root / 'sources/rexglue-decommit'
        build = output / 'build'
        configure = [cmake, '-S', output / 'maintained', '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_CXX_COMPILER=' + (clang / 'bin/clang++.exe').as_posix(), '-DCMAKE_PREFIX_PATH=' + sdk.as_posix(),
            '-DCMAKE_MAKE_PROGRAM=' + ninja.as_posix(), '-DMW3_SDK_SOURCE=' + source.as_posix(),
            '-DCMAKE_CXX_FLAGS=-march=x86-64-v2', '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG', '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld',
            '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON', '-DMW3_GPU_HOST_UBSAN=' + ('ON' if args.sanitizers else 'OFF')]
        for label, command in [('configure', configure), ('build', [cmake, '--build', build, '--parallel', '2'])]:
            command = list(map(str, command)); report['commands'].append(command)
            with (output / (label + '.log')).open('wb') as log:
                subprocess.run(command, env=env, cwd=output, stdout=log, stderr=subprocess.STDOUT, timeout=180, check=True)
        binary = build / 'gpu-bootstrap.exe'
        report.update(binary_sha256=common.sha(binary), compile_commands_sha256=common.sha(build / 'compile_commands.json'))
        plan = [(f'repeat-{i}-{case}', case, SEED, 'ordinary') for i in range(3) for case in ('bootstrap', 'lifetime')]
        plan.append(('heldout', 'heldout', 0x5eed050, 'ordinary'))
        plan += [(control, 'bootstrap', SEED, control) for control in ('wrong-pixel', 'incomplete', 'deadline')]
        adapter_identity = None
        for label, case, seed, control in plan:
            lane = output / label
            for directory in ('tmp', 'config', 'data', 'runtime', 'cache', 'profile'): (lane / directory).mkdir(parents=True, exist_ok=True)
            inputs = cases(seed)
            path = lane / 'cases.txt'
            path.write_text(''.join(' '.join(map(str, (w, h, *color))) + '\n' for w, h, color in inputs), encoding='ascii', newline='\n')
            child = {k: v for k, v in env.items() if not k.startswith(('REX_', 'MW3_', 'SDL_', 'LD_', 'ASAN_', 'LSAN_', 'UBSAN_'))}
            child.update(TMP=str(lane / 'tmp'), TEMP=str(lane / 'tmp'), TMPDIR=str(lane / 'tmp'),
                XDG_CONFIG_HOME=str(lane / 'config'), XDG_DATA_HOME=str(lane / 'data'), XDG_RUNTIME_DIR=str(lane / 'runtime'),
                XDG_CACHE_HOME=str(lane / 'cache'), APPDATA=str(lane / 'config'), LOCALAPPDATA=str(lane / 'data'),
                USERPROFILE=str(lane / 'profile'), PATH=str(sdk / 'bin') + os.pathsep + child.get('PATH', ''))
            nonce = uuid.uuid4().hex
            command = list(map(str, (binary, case, nonce, path, sdk / 'bin/rexgpu.dll', sdk / 'bin/rexgpu-xenos-d3d12.dll', control)))
            timeout = 8 if control == 'deadline' else 45
            attempt = dict(label=label, case=case, control=control, seed=seed, nonce=nonce,
                command=command, timeout=timeout, status='IN_PROGRESS', cases_sha256=common.sha(path))
            report['results'].append(attempt)
            code = run_process(command, cwd=lane, env=child, log=lane / 'run.log', timeout=timeout)
            text = (lane / 'run.log').read_text(encoding='utf-8', errors='replace')
            attempt.update(returncode=code, log_sha256=common.sha(lane / 'run.log'))
            paths = libraries(nonce, text)
            loaded = loaded_identity(paths, sdk)
            value = classify(case, nonce, code, text, inputs)
            if control == 'ordinary': valid = value is not None
            elif control == 'wrong-pixel':
                valid = (code == 1 and COMPLETE not in text and
                    [line for line in text.splitlines() if line.startswith('MW3_GPU_FAILURE:')] == ['MW3_GPU_FAILURE:deliberate wrong-pixel rejected'] and
                    not any(s in text for s in ('Sanitizer', 'runtime error:')))
            elif control == 'incomplete':
                valid = (code == 0 and clean(text) and COMPLETE not in text and value is None and
                    [line for line in text.splitlines() if line.startswith('MW3_GPU_READY:')] == ['MW3_GPU_READY:' + nonce])
            else: valid = code == -999 and classify(case, nonce, 0, text, inputs) is not None
            if value:
                device = {k: v for k, v in value['devices'][0].items() if k not in ('initialization_ns', 'cleanup_ns', 'debug_warnings')}
                if adapter_identity is None: adapter_identity = device
                if adapter_identity != device: raise ValueError('actual adapter identity changed during matrix')
            attempt.update(status='PASS' if valid else 'FAIL', record=value, loaded=loaded)
            print(json.dumps(dict(label=label, status=report['results'][-1]['status'], returncode=code)), flush=True)
        _, after = memory.verify_prepared(root, args.sdk_report)
        if (after != identity or source_snapshot(SOURCE) != sources or common.sha(__file__) != report['script_sha256'] or
                common.sha(binary) != report['binary_sha256'] or any(common.sha(ROOT / 'tools' / n) != h for n, h in helpers.items()) or
                any(common.sha(Path(t['path'])) != t['sha256'] for t in tools.values())):
            raise ValueError('source, tool, producer, binary or SDK changed')
        report['status'] = 'PASS' if all(r['status'] == 'PASS' for r in report['results']) else 'FAIL'
        report['artifacts'] = storage.artifact_snapshot(output)
        (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        return 0 if report['status'] == 'PASS' else 1
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        report.update(status='ERROR', error=str(error))
        if output: (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        parser.exit(2, f'GPU diagnostic failed: {type(error).__name__}; inspect {output}\n')


if __name__ == '__main__': raise SystemExit(main())
