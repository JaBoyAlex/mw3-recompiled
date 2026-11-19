#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build an isolated conditional-store SO generator, leaving SDK inputs read-only."""
import argparse
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
import test_sdk_audio as capture

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'config/toolchains/rexglue-conditional-so'
ADAPTER = ROOT / 'tests/ppc/generator/adapter.cpp'
SOURCE_FILE = 'src/codegen/builder/memory.cpp'


def definition():
    lock = json.loads((PROFILE / 'lock.json').read_text(encoding='utf-8'))
    if (set(lock) != {'schema', 'profile', 'commit', 'source', 'before_sha256', 'after_sha256', 'patch', 'patch_sha256',
                     'adapter_sha256', 'upstream_license_sha256'} or type(lock['schema']) is not int or lock['schema'] != 1 or
            lock['profile'] != 'conditional-store-so-v1' or lock['source'] != SOURCE_FILE or lock['patch'] != 'atomic-so.patch' or
            lock['commit'] != json.loads(memory.LOCK.read_text())['commit']):
        raise ValueError('unreviewed conditional-store profile')
    for key in ('before_sha256', 'after_sha256', 'patch_sha256', 'adapter_sha256', 'upstream_license_sha256'):
        if type(lock[key]) is not str or not re.fullmatch('[0-9a-f]{64}', lock[key]):
            raise ValueError('invalid profile fingerprint')
    if (common.sha(PROFILE / lock['patch']) != lock['patch_sha256'] or common.sha(ADAPTER) != lock['adapter_sha256'] or
            common.sha(ROOT / 'experiments/runtime-bakeoff/patches/LICENSE.rexglue') != lock['upstream_license_sha256']):
        raise ValueError('patch, adapter or license changed')
    return lock, common.snapshot(PROFILE)


def apply_overlay(source, destination, patch, lock, git):
    """Create one exclusive private file; never apply a patch to SDK source."""
    if lock['source'] != SOURCE_FILE or common.sha(source) != lock['before_sha256']:
        raise ValueError('original emitter differs from profile')
    destination.mkdir()  # Existing attempts are never reused or overwritten.
    subprocess.run([git, 'init', '--quiet', str(destination)], check=True, capture_output=True, timeout=30)
    # Do not inherit a user's global CRLF or whitespace-rewrite policy.
    apply = [git, '-c', 'core.autocrlf=false', '-c', 'core.eol=lf', '-C', str(destination), 'apply', '--whitespace=nowarn']
    stat = subprocess.check_output([*apply, '--numstat', str(patch)], text=True, timeout=30)
    if stat.strip() != '1\t0\t' + SOURCE_FILE:
        raise ValueError('patch exceeds the one-line/one-file scope')
    target = destination / SOURCE_FILE
    target.parent.mkdir(parents=True)
    shutil.copyfile(source, target)
    for flags in (['--check'], []):
        subprocess.run([*apply, *flags, str(patch)], check=True, capture_output=True, timeout=30)
    if common.sha(target) != lock['after_sha256'] or common.sha(source) != lock['before_sha256']:
        raise ValueError('overlay or original source changed')
    return target


def verify_prepared(root, report_path, sdk_report):
    lock, inputs = definition()
    report_path = Path(report_path)
    value = json.loads(report_path.read_text(encoding='utf-8'))
    if (value.get('status') != 'PASS' or value.get('task') != 'MW3-048' or type(value.get('schema')) is not int or
            value['schema'] != 1 or value.get('profile') != lock['profile'] or value.get('host') != sys.platform or
            value.get('core_modified') is not False or value.get('producer_sha256') != common.sha(__file__) or
            value.get('profile_files') != inputs or value.get('sdk_report_sha256') != common.sha(sdk_report) or
            value.get('root') != str(Path(root).resolve()) or value.get('adapter_sha256') != lock['adapter_sha256']):
        raise ValueError('unreviewed or stale prepared generator')
    sdk, actual = memory.verify_prepared(Path(root), Path(sdk_report))
    if value.get('sdk') != actual:
        raise ValueError('generator uses a different approved SDK')
    directory = common.no_symlink_path(report_path.parent)
    binary = directory / ('ppc-generator.exe' if sys.platform == 'win32' else 'ppc-generator')
    overlay = directory / 'overlay' / SOURCE_FILE
    adapter = directory / 'adapter.cpp'
    commands = directory / 'build/compile_commands.json'
    if (binary.is_symlink() or common.sha(binary) != value['binary_sha256'] or
            common.sha(overlay) != lock['after_sha256'] or common.sha(adapter) != lock['adapter_sha256'] or
            common.sha(directory / 'project/CMakeLists.txt') != inputs['CMakeLists.txt']['sha256'] or
            common.sha(commands) != value['compile_commands_sha256']):
        raise ValueError('prepared generator artifact changed')
    compiled = json.loads(commands.read_text(encoding='utf-8'))
    emitter = [Path(row['file']).resolve() for row in compiled if Path(row['file']).name == 'memory.cpp']
    if emitter != [overlay.resolve()]:
        raise ValueError('generator did not compile exactly the approved overlay')
    for entry in value['tools'].values():
        if common.sha(Path(entry['path'])) != entry['sha256']:
            raise ValueError('generator build tool changed')
    original = Path(root) / 'sources/rexglue-decommit' / SOURCE_FILE
    if common.sha(original) != lock['before_sha256']:
        raise ValueError('original emitter changed')
    return binary, dict(profile=lock['profile'], preparation_sha256=common.sha(report_path),
        binary_sha256=value['binary_sha256'], profile_files=inputs, overlay_sha256=lock['after_sha256'],
        adapter_sha256=lock['adapter_sha256'], sdk_tree_sha256=actual['sdk_tree_sha256'], compiler=value['compiler'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'sdk-report', 'output-root'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    output = None
    report = dict(schema=1, task='MW3-048', status='IN_PROGRESS', core_modified=False,
        producer_sha256=common.sha(__file__), host=sys.platform, python=sys.version)
    try:
        lock, inputs = definition()
        root = args.root.resolve()
        sdk, identity = memory.verify_prepared(root, args.sdk_report)
        source = root / 'sources/rexglue-decommit'
        if common.sha(source / SOURCE_FILE) != lock['before_sha256']:
            raise ValueError('approved emitter source differs')
        output = common.private_cache(args.output_root, ROOT / '.local/game') / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        git = shutil.which('git')
        if not git: raise ValueError('Git required for private patch verification')
        target = apply_overlay(source / SOURCE_FILE, output / 'overlay', PROFILE / lock['patch'], lock, git)
        shutil.copyfile(ADAPTER, output / 'adapter.cpp')
        (output / 'project').mkdir()
        shutil.copyfile(PROFILE / 'CMakeLists.txt', output / 'project/CMakeLists.txt')
        windows = sys.platform == 'win32'
        if windows:
            import prepare_windows_runtime as win
            windows_lock = json.loads(win.LOCK.read_text())
            clang, compiler = win.compiler(root, windows_lock['compiler'], False)
            env, cmake, ninja, report['host_tools'] = win.msvc_environment(windows_lock, clang)
            llvm = clang / 'bin'
            extra = ['-DCMAKE_MAKE_PROGRAM=' + ninja.as_posix(), '-DCMAKE_CXX_FLAGS=-march=x86-64-v2', '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld']
        else:
            if sys.platform != 'linux': raise ValueError('unsupported host')
            llvm, env, cmake, ninja = Path('/usr/lib/llvm-20/bin'), dict(os.environ), shutil.which('cmake'), shutil.which('ninja')
            compiler = dict(sha256=common.sha(llvm / 'clang++'), version=subprocess.check_output([llvm / 'clang++', '--version'], text=True).splitlines()[0])
            extra = ['-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13',
                '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2']
        suffix = '.exe' if windows else ''
        paths = dict(clang=llvm / ('clang' + suffix), cxx=llvm / ('clang++' + suffix),
            cmake=Path(cmake), ninja=Path(ninja), git=Path(git))
        tools = {}
        for name, path in paths.items():
            tools[name] = dict(path=str(path), sha256=common.sha(path), version=subprocess.check_output([path, '--version'], env=env, text=True).splitlines()[0])
        if not re.search(r'clang version 20\.1\.2\b', tools['cxx']['version']):
            raise ValueError('unapproved compiler')
        report.update(profile=lock['profile'], profile_files=inputs, root=str(root), sdk=identity,
            sdk_report_sha256=common.sha(args.sdk_report), adapter_sha256=lock['adapter_sha256'], compiler=compiler,
            tools=tools, commands=[])
        build = output / 'build'
        configure = [cmake, '-S', output / 'project', '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_C_COMPILER=' + paths['clang'].as_posix(), '-DCMAKE_CXX_COMPILER=' + paths['cxx'].as_posix(),
            '-DCMAKE_PREFIX_PATH=' + sdk.as_posix(), '-DMW3_SDK_SOURCE=' + source.as_posix(),
            '-DMW3_ADAPTER=' + (output / 'adapter.cpp').as_posix(), '-DMW3_MEMORY_OVERLAY=' + target.as_posix(),
            '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG', '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON', *extra]
        for label, command in [('configure', configure), ('build', [cmake, '--build', build, '--target', 'ppc-generator', '--parallel', '2'])]:
            command = list(map(str, command))
            with (output / (label + '.log')).open('wb') as log:
                subprocess.run(command, cwd=output, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=900)
            report['commands'].append(dict(label=label, command=command))
        binary = output / ('ppc-generator' + suffix)
        shutil.copy2(build / binary.name, binary)
        report.update(binary_sha256=common.sha(binary), compile_commands_sha256=common.sha(build / 'compile_commands.json'))
        _, after = memory.verify_prepared(root, args.sdk_report)
        if (after != identity or definition()[1] != inputs or common.sha(__file__) != report['producer_sha256'] or
                common.sha(source / SOURCE_FILE) != lock['before_sha256'] or common.sha(target) != lock['after_sha256']):
            raise ValueError('source, profile, producer or SDK changed during preparation')
        report['status'] = 'PASS'
        report['artifacts'] = capture.storage.artifact_snapshot(output)
        receipt = output / 'manifest.json'
        receipt.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
        verify_prepared(root, receipt, args.sdk_report)
        print(json.dumps(dict(status='PASS', report=str(receipt))), flush=True)
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        report.update(status='ERROR', error=str(error))
        if output: (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        parser.exit(2, f'Conditional-store generator preparation failed: {type(error).__name__}; inspect {output}\n')


if __name__ == '__main__':
    raise SystemExit(main())
