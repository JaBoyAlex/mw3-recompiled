#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build and verify an isolated SDL trigger-state profile; never replace an existing SDK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import uuid

import prepare_windows_runtime as win
import recompile as common
import test_sdk_input as raw

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config/toolchains/sdl-input'
SOURCE = ROOT / 'tests/host_platform/sdl_input_profile'
COMPLETE, LOADED = 'MW3_SDL_COMPLETE:', 'MW3_SDL_LOADED:'
PHASES = ('initial', 'unchanged', 'second', 'reopen', 'remap', 'rest', 'detach')
HELD = ((32767, 16384), (-32768, 32767))


def one(prefix, text):
    lines = [l[len(prefix):] for l in text.splitlines() if l.startswith(prefix)]
    if len(lines) != 1: return None
    try: return json.loads(lines[0], object_pairs_hook=raw.unique_object)
    except (ValueError, TypeError): return None


def configuration():
    lock = json.loads((CONFIG / 'lock.json').read_text())
    if (type(lock.get('schema')) is not int or lock['schema'] != 1 or lock.get('profile') != 'sdl-trigger-v1' or
        lock.get('commit') != '147a8ee32dbf9ac02f3794964490687b6bbda1bc' or lock.get('version') != 3004014 or
        common.sha(CONFIG / 'preserve-trigger.patch') != lock.get('patch_sha256') or
        common.sha(CONFIG / 'LICENSE.SDL') != lock.get('license_sha256')): raise ValueError('unapproved SDL profile configuration')
    return lock


def files(path):
    path = Path(path).resolve(); result = {}
    for p in sorted(path.rglob('*')):
        if p.is_file():
            if not p.resolve().is_relative_to(path): raise ValueError('profile link escapes its tree')
            result[p.relative_to(path).as_posix()] = dict(sha256=common.sha(p), bytes=p.stat().st_size)
    return result


def base_source(root, lock):
    source = root / lock['source_relative']
    def git(*a): return subprocess.check_output(['git', '-C', str(source), *a], text=True).strip()
    if git('rev-parse', 'HEAD') != lock['commit'] or git('status', '--porcelain', '--untracked-files=all'):
        raise ValueError('SDL source differs from clean pinned checkout')
    rows = git('ls-tree', '-rz', '--full-tree', lock['commit']).split('\0')
    observed = {}
    for row in filter(None, rows):
        metadata, name = row.split('\t', 1); mode, kind, blob = metadata.split()
        if mode not in ('100644', '100755') or kind != 'blob' or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('unsupported SDL source path or link')
        observed[name] = blob
    for name, expected in lock['source_files'].items():
        data = subprocess.check_output(['git', '-C', str(source), 'show', lock['commit'] + ':' + name])
        if hashlib.sha256(data).hexdigest() != expected: raise ValueError('SDL canonical declarations/source differ')
    return source, observed


def extract_source(archive, destination):
    # Git archive supplies canonical blobs, independent of checkout CRLF filters.
    with tarfile.open(archive) as stream:
        members = stream.getmembers(); seen = set(); total = 0
        for member in members:
            name = member.name; path = Path(name)
            key = path.as_posix().casefold() if os.name == 'nt' else path.as_posix()
            reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
            if (not name or name.startswith('/') or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name or key in seen or
                any(p.endswith(('.', ' ')) or p.split('.')[0].upper() in reserved for p in path.parts) or
                not (member.isfile() or member.isdir()) or not 0 <= member.size <= 128 * 1024 * 1024):
                raise ValueError('unsafe source archive member')
            seen.add(key); total += member.size
            if total > 512 * 1024 * 1024: raise ValueError('source archive exceeds bounded size')
        for member in members:
            target = destination / member.name
            if member.isdir(): target.mkdir(parents=True, exist_ok=True); continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(member) as source, target.open('wb') as output:
                shutil.copyfileobj(source, output, 64 * 1024)
            target.chmod(member.mode & 0o777)


def check_derived(stage, original_git, lock, changed=True):
    observed = files(stage)
    if set(observed) != set(original_git): raise ValueError('SDL derivative file list differs')
    for name, blob in original_git.items():
        data = (stage / name).read_bytes()
        if changed and name == lock['changed_file']:
            if observed[name]['sha256'] != lock['derived_source_sha256']: raise ValueError('SDL patch output differs')
        elif hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != blob:
            raise ValueError('unexpected SDL source change')
    return observed


def output_root(root, destination, source):
    destination = common.private_cache(destination, ROOT / 'game')
    protected = (Path(root).resolve(), source.resolve(), CONFIG.resolve(), SOURCE.resolve())
    if any(destination == p or destination.is_relative_to(p) or p.is_relative_to(destination) for p in protected):
        raise ValueError('output overlaps maintained/source inputs')
    if destination.is_relative_to(ROOT) and not destination.is_relative_to(ROOT / '.local'):
        raise ValueError('output enters maintained project')
    return destination


def loading(nonce, text):
    value = one(LOADED, text)
    if (not re.fullmatch('[0-9a-f]{32}', nonce) or type(value) is not dict or set(value) != {'nonce', 'library', 'version'} or
        value['nonce'] != nonce or type(value['version']) is not int or value['version'] != 3004014 or
        type(value['library']) is not str or not value['library'] or any(c in value['library'] for c in '\n\r')): return None
    return value


def mapped(value):
    f32 = lambda v: struct.unpack('<f', struct.pack('<f', v))[0]
    return int(f32(f32((value + 32768) / 65535) * 32767))


def record(mode, nonce, text):
    value = one(COMPLETE, text); loaded = loading(nonce, text)
    expected = dict(schema=1, mode=mode, nonce=nonce, version=3004014, created=2, cleaned=2, sdl_after=0)
    if (loaded is None or type(value) is not dict or set(value) != set(expected) | {'library', 'checks', 'rows'} or
        any(type(value[k]) is not type(v) or value[k] != v for k, v in expected.items()) or value['library'] != loaded['library'] or
        type(value['checks']) is not int or not 50 <= value['checks'] <= 10000 or type(value['rows']) is not list or len(value['rows']) != 14): return None
    if [l for l in text.splitlines() if l.startswith('MW3_SDL_READY:')] != ['MW3_SDL_READY:' + nonce]: return None
    baseline = mode == 'baseline'
    for row, (phase, pad) in zip(value['rows'], ((p, i) for p in PHASES for i in range(2))):
        if type(row) is not dict or set(row) != {'phase', 'pad', 'before', 'after', 'mapped', 'stick', 'button'}: return None
        if row['phase'] != phase or type(row['pad']) is not int or row['pad'] != pad: return None
        for field in ('before', 'after', 'mapped'):
            if type(row[field]) is not list or len(row[field]) != 2 or any(type(v) is not int for v in row[field]): return None
        current = list(HELD[pad]); rest = [-32768, -32768]
        before = rest if phase == 'rest' or (baseline and phase in ('unchanged', 'second')) else current
        after = rest if phase in ('rest', 'detach') or baseline else current
        expected_mapped = [mapped(v) for v in after]
        if (row['before'] != before or row['after'] != after or row['mapped'] != expected_mapped or
            type(row['stick']) is not int or row['stick'] != (0 if phase == 'detach' else 1024 * (pad + 1)) or
            type(row['button']) is not bool or row['button'] != (phase != 'detach')): return None
    return value


def classify(mode, nonce, code, text):
    if mode not in ('baseline', 'repaired', 'wrong', 'incomplete', 'deadline'): raise ValueError('unknown SDL probe mode')
    if any(t in text for t in ('Sanitizer', 'runtime error:', 'end of crash report')): return None
    errors = [l for l in text.splitlines() if l.startswith('MW3_SDL_FAILURE:')]
    if mode == 'incomplete':
        return {'incomplete_rejected': True} if code == 0 and not errors and COMPLETE not in text and loading(nonce, text) and text.splitlines().count('MW3_SDL_READY:' + nonce) == 1 else None
    expected_error = 'MW3_SDL_FAILURE:original mapping reset observed' if mode == 'baseline' else 'MW3_SDL_FAILURE:wrong-zero expectation rejected' if mode == 'wrong' else None
    if errors != ([expected_error] if expected_error else []) or code != (1 if expected_error else -999 if mode == 'deadline' else 0): return None
    return record(mode, nonce, text)


def library(prefix): return prefix / ('bin/SDL3.dll' if sys.platform == 'win32' else 'lib/libSDL3.so.0')


def loaded_identity(value, prefix):
    actual, expected = Path(value['library']).resolve(strict=True), library(prefix).resolve(strict=True)
    if actual != expected or common.sha(actual) != common.sha(expected): raise ValueError('unexpected actual SDL profile library')
    return dict(path=str(actual), sha256=common.sha(actual))


def verify_prepared(root, report_path, allow_sanitized=False):
    lock = configuration(); report_path = report_path.resolve(); out = report_path.parent
    m = json.loads(report_path.read_text())
    if (m.get('status') != 'PASS' or m.get('profile') != lock['profile'] or type(m.get('sanitizers')) is not bool or
        (m['sanitizers'] and not allow_sanitized) or m.get('script_sha256') != common.sha(__file__) or
        m.get('lock_sha256') != common.sha(CONFIG / 'lock.json') or m.get('sdk_prefix') != str(out / 'sdk')):
        raise ValueError('unapproved SDL preparation receipt')
    source, original_git = base_source(Path(root).resolve(), lock)
    derived = check_derived(out / 'source', original_git, lock)
    original = dict(derived)
    original[lock['changed_file']] = dict(sha256=lock['source_files'][lock['changed_file']], bytes=lock['original_changed_bytes'])
    if original_git != m['original_git_files'] or original != m['original_sources'] or derived != m['derived_sources']:
        raise ValueError('SDL source/provenance changed')
    for name in ('sdk', 'baseline-sdk'):
        if files(out / name) != m['packages'][name]: raise ValueError('SDL package changed')
    for name, digest in m['inputs'].items():
        if common.sha(SOURCE / name) != digest or common.sha(out / 'probe-source' / name) != digest: raise ValueError('SDL probe changed')
    if common.sha(out / 'probe-build' / m['probe_name']) != m['probe_sha256']: raise ValueError('SDL probe binary changed')
    for name, digest in m['helpers'].items():
        if common.sha(ROOT / 'tools' / name) != digest: raise ValueError('SDL preparation helper changed')
    for tool in m['tools'].values():
        if common.sha(tool['path']) != tool['sha256']: raise ValueError('SDL preparation tool changed')
    plans = [('baseline', i) for i in range(3)] + [('repaired', i) for i in range(3)] + [(mode, 0) for mode in ('wrong', 'incomplete', 'deadline')]
    if len(m['results']) != len(plans): raise ValueError('missing SDL profile trials')
    for row, (mode, repeat) in zip(m['results'], plans):
        if row['mode'] != mode or type(row['repeat']) is not int or row['repeat'] != repeat or row['status'] != 'PASS': raise ValueError('wrong SDL trial order/status')
        log = out / f'{mode}-{repeat}.log'
        if common.sha(log) != row['log_sha256']: raise ValueError('SDL trial log changed')
        text = log.read_text(errors='replace'); parsed = classify(mode, row['nonce'], row['returncode'], text)
        if parsed is None or parsed != row['record'] or loaded_identity(loading(row['nonce'], text), out / ('baseline-sdk' if mode == 'baseline' else 'sdk')) != row['loaded']:
            raise ValueError('SDL trial evidence differs')
    identity = dict(profile=lock['profile'], source_commit=lock['commit'], patch_sha256=lock['patch_sha256'],
        compiler=m['compiler'], library_sha256=common.sha(library(out / 'sdk')), package_files=m['packages']['sdk'],
        preparation_sha256=common.sha(report_path), sanitizers=m['sanitizers'])
    return out / 'sdk', identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--sanitizers', action='store_true')
    args = parser.parse_args(); out = None
    m = dict(schema=1, profile='sdl-trigger-v1', status='IN_PROGRESS', sanitizers=args.sanitizers,
             guest_executed=False, physical_devices=False, existing_sdk_modified=False, script_sha256=common.sha(__file__), results=[], commands=[])
    try:
        lock = configuration(); root = args.root.resolve(); source, original_git = base_source(root, lock)
        if args.sanitizers and sys.platform != 'linux': raise ValueError('participating SDL sanitizers are Linux-only')
        out = output_root(root, args.output_root, source) / uuid.uuid4().hex; out.mkdir(parents=True)
        print(json.dumps(dict(output=str(out))), flush=True)
        stage = out / 'source'
        archive = out / 'source.tar'
        with archive.open('wb') as stream:
            subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf', '-C', str(source), 'archive', '--format=tar', lock['commit']], stdout=stream, check=True)
        extract_source(archive, stage); original = check_derived(stage, original_git, lock, changed=False)
        inputs = {name: common.sha(SOURCE / name) for name in ('CMakeLists.txt', 'probe.cpp')}
        shutil.copytree(SOURCE, out / 'probe-source', ignore=shutil.ignore_patterns('__pycache__', 'test_*.py', '__init__.py'))
        shutil.copy2(__file__, out / 'maintained-driver.py')
        helpers = {n: common.sha(ROOT / 'tools' / n) for n in ('prepare_windows_runtime.py', 'recompile.py', 'test_sdk_input.py')}
        windows = sys.platform == 'win32'
        if windows:
            wlock = json.loads(win.LOCK.read_text()); clang, compiler = win.compiler(root, wlock['compiler'], False)
            env, cmake, ninja, m['host_tools'] = win.msvc_environment(wlock, clang)
            cxx, cc = clang / 'bin/clang++.exe', clang / 'bin/clang.exe'
            extra = ['-DCMAKE_MAKE_PROGRAM=' + ninja.as_posix(), '-DCMAKE_SHARED_LINKER_FLAGS=-fuse-ld=lld', '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld']
        else:
            if sys.platform != 'linux': raise ValueError('unsupported SDL host')
            env = dict(os.environ); cmake, ninja = shutil.which('cmake'), shutil.which('ninja')
            cxx, cc = Path(shutil.which('clang++-20') or 'missing'), Path(shutil.which('clang-20') or 'missing')
            compiler = dict(sha256=common.sha(cxx), version=subprocess.check_output([cxx, '--version'], text=True).splitlines()[0])
            extra = ['-DCMAKE_SHARED_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2', '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2']
        if not re.search(r'clang version 20\.1\.2\b', compiler['version']): raise ValueError('compiler differs')
        tools = {n: dict(path=str(p), sha256=common.sha(p), version=subprocess.check_output([str(p), '--version'], env=env, text=True).splitlines()[0])
                 for n, p in dict(cxx=cxx, cc=cc, cmake=cmake, ninja=ninja, git=shutil.which('git')).items()}
        m.update(compiler=compiler, tools=tools, inputs=inputs, helpers=helpers, original_sources=original, original_git_files=original_git,
                 lock_sha256=common.sha(CONFIG / 'lock.json'), sdk_prefix=str(out / 'sdk'))
        def command(label, cmd, cwd=None):
            cmd = list(map(str, cmd)); m['commands'].append(cmd); print(json.dumps(dict(stage=label)), flush=True)
            with (out / (label + '.log')).open('wb') as log:
                subprocess.run(cmd, cwd=cwd or out, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=1200, check=True)
        flags = '-march=x86-64-v2'
        if not windows: flags += ' --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13'
        if args.sanitizers: flags += ' -fsanitize=address,undefined -fno-omit-frame-pointer'
        build = out / 'build'
        command('configure', [cmake, '-S', stage, '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_C_COMPILER=' + cc.as_posix(), '-DCMAKE_CXX_COMPILER=' + cxx.as_posix(),
            '-DCMAKE_C_FLAGS=' + flags, '-DCMAKE_CXX_FLAGS=' + flags, '-DCMAKE_C_FLAGS_RELEASE=-O2 -DNDEBUG',
            '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
            '-DCMAKE_INSTALL_PREFIX=' + (out / 'sdk').as_posix(), '-DSDL_SHARED=ON', '-DSDL_STATIC=OFF',
            '-DSDL_TESTS=OFF', '-DSDL_TEST_LIBRARY=OFF', '-DSDL_EXAMPLES=OFF', *extra,
            # An ASan DSO resolves instrumentation from the instrumented host.
            # SDL's executable-oriented --no-undefined check is unsuitable here.
            *(['-DLINKER_SUPPORTS_WL_NO_UNDEFINED=OFF'] if args.sanitizers else [])])
        command('build-baseline', [cmake, '--build', build, '--parallel', '2'])
        command('install-baseline', [cmake, '--install', build, '--prefix', out / 'baseline-sdk'])
        probe = out / 'probe-build'
        command('configure-probe', [cmake, '-S', out / 'probe-source', '-B', probe, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_CXX_COMPILER=' + cxx.as_posix(), '-DCMAKE_PREFIX_PATH=' + (out / 'baseline-sdk').as_posix(),
            '-DCMAKE_CXX_FLAGS=' + flags, '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG',
            '-DMW3_SDL_SANITIZERS=' + ('ON' if args.sanitizers else 'OFF'), '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON', *extra])
        command('build-probe', [cmake, '--build', probe, '--parallel', '2'])
        binary = probe / ('sdl-trigger-probe.exe' if windows else 'sdl-trigger-probe')
        m.update(probe_name=binary.name, probe_sha256=common.sha(binary), packages={'baseline-sdk': files(out / 'baseline-sdk')},
                 compile_commands_sha256=common.sha(build / 'compile_commands.json'), probe_compile_commands_sha256=common.sha(probe / 'compile_commands.json'),
                 cmake_cache_sha256=common.sha(build / 'CMakeCache.txt'))
        def trial(mode, repeat):
            prefix = out / ('baseline-sdk' if mode == 'baseline' else 'sdk'); nonce = uuid.uuid4().hex
            child = {k: v for k, v in env.items() if not k.startswith(('REX_', 'MW3_', 'SDL_', 'LD_', 'ASAN_', 'LSAN_', 'UBSAN_'))}
            lane = out / f'profile-{mode}-{repeat}'; lane.mkdir()
            for name in ('tmp', 'config', 'data', 'cache', 'runtime', 'user'): (lane / name).mkdir()
            child.update(TMP=str(lane/'tmp'), TEMP=str(lane/'tmp'), TMPDIR=str(lane/'tmp'), XDG_CONFIG_HOME=str(lane/'config'),
                XDG_DATA_HOME=str(lane/'data'), XDG_CACHE_HOME=str(lane/'cache'), XDG_RUNTIME_DIR=str(lane/'runtime'),
                APPDATA=str(lane/'config'), LOCALAPPDATA=str(lane/'data'), USERPROFILE=str(lane/'user'),
                SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', ASAN_OPTIONS='detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            if windows: child['PATH'] = str(prefix / 'bin') + os.pathsep + child.get('PATH', '')
            else: child['LD_LIBRARY_PATH'] = str(prefix / 'lib')
            cmd = [str(binary), mode, nonce]; log = out / f'{mode}-{repeat}.log'
            code = raw.run_process(cmd, cwd=lane, env=child, log=log, timeout=8 if mode == 'deadline' else 30)
            text = log.read_text(errors='replace'); value = classify(mode, nonce, code, text); loader = loading(nonce, text)
            loaded = loaded_identity(loader, prefix) if loader else None
            row = dict(mode=mode, repeat=repeat, nonce=nonce, command=cmd, returncode=code, record=value,
                       loaded=loaded, log_sha256=common.sha(log), status='PASS' if value is not None and loaded else 'FAIL')
            m['results'].append(row); print(json.dumps({k:row[k] for k in ('mode','repeat','status','returncode')}), flush=True)
            if row['status'] != 'PASS': raise ValueError('SDL trial failed; original result retained')
        for i in range(3): trial('baseline', i)
        patch = CONFIG / 'preserve-trigger.patch'
        command('patch-check', ['git', '-c', 'core.autocrlf=false', 'apply', '--no-index', '--check', patch.resolve()], stage)
        command('patch', ['git', '-c', 'core.autocrlf=false', 'apply', '--no-index', patch.resolve()], stage)
        derived = check_derived(stage, original_git, lock); expected = dict(original)
        expected[lock['changed_file']] = dict(sha256=lock['derived_source_sha256'], bytes=(stage / lock['changed_file']).stat().st_size)
        if derived != expected: raise ValueError('unexpected SDL derivative')
        m['derived_sources'] = derived
        command('build-repaired', [cmake, '--build', build, '--parallel', '2'])
        command('install-repaired', [cmake, '--install', build, '--prefix', out / 'sdk'])
        m['packages']['sdk'] = files(out / 'sdk')
        for i in range(3): trial('repaired', i)
        for mode in ('wrong', 'incomplete', 'deadline'): trial(mode, 0)
        if (base_source(root, lock)[1] != original_git or common.sha(__file__) != m['script_sha256'] or
            common.sha(CONFIG / 'lock.json') != m['lock_sha256'] or files(stage) != derived or
            files(out / 'baseline-sdk') != m['packages']['baseline-sdk'] or files(out / 'sdk') != m['packages']['sdk'] or
            common.sha(binary) != m['probe_sha256'] or any(common.sha(SOURCE / n) != h for n, h in inputs.items()) or
            any(common.sha(ROOT / 'tools' / n) != h for n, h in helpers.items()) or
            any(common.sha(t['path']) != t['sha256'] for t in tools.values())): raise ValueError('preparation inputs changed')
        m['status'] = 'PASS'
        (out / 'manifest.json').write_text(json.dumps(m, indent=2) + '\n', encoding='utf-8', newline='\n')
        verify_prepared(root, out / 'manifest.json', allow_sanitized=args.sanitizers)
        return 0
    except (OSError, ValueError, TypeError, KeyError, tarfile.TarError, subprocess.SubprocessError) as error:
        m.update(status='ERROR', error=str(error))
        if out: (out / 'manifest.json').write_text(json.dumps(m, indent=2) + '\n', encoding='utf-8', newline='\n')
        parser.exit(2, f'SDL input profile failed: {type(error).__name__}; inspect {out}\n')


if __name__ == '__main__': raise SystemExit(main())
