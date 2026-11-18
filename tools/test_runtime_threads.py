#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Bounded selected-runtime thread diagnostics; each suite states its coverage."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
import recompile as prep
import prepare_runtime_memory as memory
from host_checks import exact_filter,summarize
from test_runtime_memory import upstream_status

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'tests/threads'

def snapshot():
    return {n:v for n,v in prep.snapshot(SOURCE).items() if '__pycache__' not in Path(n).parts}

def outcome(code,path,expected):
    if expected<1:raise ValueError('empty diagnostic plan')
    checked=summarize(path)
    status,reasons=upstream_status(code,checked,path)
    return dict(status=status if checked['cases']==expected else 'FAIL',skip_reasons=reasons,**checked)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ('root','sdk-report','output-root'):parser.add_argument('--'+n,required=True,type=Path)
    parser.add_argument('--suite',required=True,choices=('platform',),help='platform diagnostics do not complete guest-kernel contracts')
    parser.add_argument('--sanitizers',action='store_true')
    args=parser.parse_args();output=None
    report=dict(schema_version=1,evidence_class='upstream-platform-thread-diagnostics',
        kernel_contracts_complete=False,owned_title_executed=False,performance_measured=False,
        script_sha256=prep.sha(__file__),sources=snapshot(),suite=args.suite,results=[])
    try:
        output=prep.private_cache(args.output_root,ROOT/'game')/uuid.uuid4().hex;output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))),flush=True)
        def run(label,call,env,timeout=180):
            path=output/(label+'.log');command=list(map(str,call))
            with path.open('wb') as log:r=subprocess.run(command,env=env,cwd=output,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
            report.setdefault('commands',[]).append(dict(label=label,command=command,returncode=r.returncode,log_sha256=prep.sha(path)))
            if r.returncode:raise ValueError(label+' failed')
            return path
        windows=sys.platform=='win32';root=args.root.resolve()
        sdk,evidence=memory.verify_prepared(root,args.sdk_report,allow_sanitized=args.sanitizers)
        report.update(sdk=evidence,sdk_report_sha256=prep.sha(args.sdk_report),
            sdk_core_instrumented=evidence['core_sanitizers'],test_callback_sanitizers=args.sanitizers)
        if windows:
            import prepare_windows_runtime as win
            lock=json.loads(win.LOCK.read_text());clang,compiler=win.compiler(root,lock['compiler'],False)
            env,cmake,ninja,host=win.msvc_environment(lock,clang);cxx=clang/'bin/clang++.exe'
            report.update(compiler=compiler,host=host)
            extra=['-DCMAKE_MAKE_PROGRAM='+ninja.as_posix(),'-DCMAKE_CXX_FLAGS=-march=x86-64-v2','-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld']
            if args.sanitizers:report['calibration']=win.calibrate_sanitizer(output,clang,env)
        else:
            if sys.platform!='linux':raise ValueError('unsupported host')
            env=dict(os.environ);cmake='cmake';cxx=Path(shutil.which('clang++-20') or 'missing')
            version=subprocess.check_output([cxx,'--version'],text=True)
            if not re.search(r'clang version 20\.1\.2\b',version):raise ValueError('compiler mismatch')
            report['compiler']=dict(version=version.splitlines()[0],sha256=prep.sha(cxx))
            extra=['-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13',
                   '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2']
        source=root/'sources/rexglue-decommit';build=output/'build'
        run('configure',[cmake,'-S',SOURCE,'-B',build,'-G','Ninja','-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_CXX_COMPILER='+cxx.as_posix(),'-DCMAKE_PREFIX_PATH='+sdk.as_posix(),
            '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
            '-DMW3_SDK_SOURCE='+source.as_posix(),'-DMW3_THREAD_SANITIZERS='+('ON' if args.sanitizers else 'OFF'),*extra],env)
        run('build',[cmake,'--build',build,'--target','thread-platform-tests','--parallel','2'],env,900)
        binary=build/('thread-platform-tests.exe' if windows else 'thread-platform-tests')
        report['binary_sha256']=prep.sha(binary);report['compile_commands_sha256']=prep.sha(build/'compile_commands.json')
        child={k:v for k,v in env.items() if not k.startswith(('REX_','LD_','ASAN_','UBSAN_','LSAN_'))}
        child.update(ASAN_OPTIONS='detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
            SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
        if windows:child['PATH']=str(sdk/'bin')+os.pathsep+child.get('PATH','')
        else:child['LD_LIBRARY_PATH']=str(sdk/'lib')
        listing=run('listing',[binary,'--list-tests','--reporter','xml'],child)
        names=[c.findtext('Name') for c in ET.fromstring(listing.read_bytes()).findall('TestCase')]
        if not names or len(names)!=len(set(names)):raise ValueError('empty or duplicate platform selection')
        report['selected_cases']=names
        plans=[('isolated-'+str(i),[exact_filter(name)],1) for i,name in enumerate(names)]
        plans += [('aggregate-decl',['--order','decl'],len(names))]
        plans += [('aggregate-'+str(seed),['--order','rand','--rng-seed',str(seed)],len(names)) for seed in (1,0x12345678)]
        for label,options,count in plans:
            lane=output/label;lane.mkdir();(lane/'tmp').mkdir();(lane/'config').mkdir()
            scoped=dict(child,TMP=str(lane/'tmp'),TEMP=str(lane/'tmp'),TMPDIR=str(lane/'tmp'),XDG_CONFIG_HOME=str(lane/'config'))
            command=[str(binary),*options,'--reporter','xml','--out',str(lane/'results.xml')]
            with (lane/'run.log').open('wb') as log:
                try:r=subprocess.run(command,env=scoped,cwd=lane,stdout=log,stderr=subprocess.STDOUT,timeout=45);code=r.returncode
                except subprocess.TimeoutExpired:code=-999
            if (lane/'results.xml').exists():checked=outcome(code,lane/'results.xml',count)
            else:checked=dict(status='FAIL',cases=0,failed=['missing results XML'],skip_reasons=[])
            text=(lane/'run.log').read_text(errors='replace')
            if any(t in text for t in ('AddressSanitizer','LeakSanitizer','runtime error:')):checked['status']='FAIL'
            row=dict(case=label,returncode=code,command=command,log_sha256=prep.sha(lane/'run.log'),**checked)
            if (lane/'results.xml').exists():row['xml_sha256']=prep.sha(lane/'results.xml')
            report['results'].append(row);print(json.dumps(dict(case=label,status=row['status'],returncode=code)),flush=True)
            (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
        if windows:
            linked=run('linkage',[clang/'bin/llvm-readobj.exe','--coff-imports',binary],env).read_text()
            if 'rexbase.dll' not in linked.lower():raise ValueError('platform test does not import SDK base DLL')
        else:
            linked=run('linkage',['ldd',binary],child).read_text()
            if str(sdk/'lib/librexbase.so') not in linked:raise ValueError('platform test loaded wrong base library')
        _,after=memory.verify_prepared(root,args.sdk_report,allow_sanitized=args.sanitizers)
        if after!=evidence or report['sources']!=snapshot() or report['script_sha256']!=prep.sha(__file__):
            raise ValueError('SDK or maintained source changed during diagnostics')
        if report['binary_sha256']!=prep.sha(binary):raise ValueError('executed binary changed')
        report['status']='PASS' if all(r['status']=='PASS' for r in report['results']) else 'FAIL'
        (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
        return int(report['status']!='PASS')
    except (OSError,ValueError,KeyError,ET.ParseError,subprocess.SubprocessError) as error:
        report.update(status='ERROR',error=str(error))
        if output:(output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
        parser.exit(2,f'thread diagnostics failed: {type(error).__name__}; inspect {output}\n')
if __name__=='__main__':raise SystemExit(main())
