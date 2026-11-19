#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Execute original PPC fixtures through a verified ReXGlue exact-math emitter."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import recompile as prep

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'tests/ppc'

def source_snapshot():
    return {n:v for n,v in prep.snapshot(SOURCE).items() if '__pycache__' not in Path(n).parts}

def reference_bundle(path, destination):
    receipt=json.loads((path/'manifest.json').read_text())
    if (receipt.get('status')!='PASS' or receipt.get('evidence_class')!='original-synthetic-ppc-oracle'
            or receipt.get('script_sha256')!=prep.sha(__file__) or receipt.get('sources')!=source_snapshot()):
        raise ValueError('stale or unsuccessful synthetic reference')
    if set(receipt['assembly'])!={'fixtures.o','fixtures.elf','fixtures.bin','fixtures.map'}:
        raise ValueError('unexpected reference assembly inventory')
    if prep.snapshot(path/'bins')!=receipt['assembly']:raise ValueError('reference assembly changed')
    for name in receipt['assembly']:shutil.copyfile(path/'bins'/name,destination/name)
    return receipt

def bindings(output,symbols):
    read=[];write=[]
    for prefix,limit,member in [('r',32,'u64'),('f',32,'u64')]:
        for n in range(limit):
            key=f'{prefix}{n}';field=f'ctx.{key}.{member}'
            read.append(f'if(key=="{key}") return {field};')
            write.append(f'if(key=="{key}") {{ {field}=value;return; }}')
    for n in range(32):
        for lane in range(4):
            key=f'v{n}_{lane}';field=f'ctx.v{n}.u32[{lane}]'
            read.append(f'if(key=="{key}") return {field};')
            write.append(f'if(key=="{key}") {{ {field}=static_cast<u32>(value);return; }}')
    for n in range(8):
        read.append(f'if(key=="cr{n}") return ctx.cr{n}.GetRaw();')
        write.append(f'if(key=="cr{n}") {{ ctx.cr{n}.SetRaw(static_cast<u32>(value));return; }}')
    for n in ['ca','ov','so']:
        read.append(f'if(key=="{n}") return ctx.xer.{n};')
        write.append(f'if(key=="{n}") {{ ctx.xer.{n}=static_cast<u8>(value);return; }}')
    for n in ['lr','ctr']:
        field='ctx.lr' if n=='lr' else 'ctx.ctr.u64'
        read.append(f'if(key=="{n}") return {field};')
        write.append(f'if(key=="{n}") {{ {field}=value;return; }}')
    for name,lines in [('read_register.inc',read),('write_register.inc',write)]:
        (output/name).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    lines=['#pragma once','#include <string>','#include <stdexcept>','#include <rex/kernel/heap.h>']
    for name,address in symbols.items():lines.append(f'DECLARE_REX_FUNC(fixtures_{address:X});')
    lines+=['inline void register_functions(rex::kernel::GuestAddressSpace& memory) {']
    for name,address in symbols.items():lines.append(f'memory.SetFunction(0x{address:X},fixtures_{address:X});')
    lines+=['}','inline void dispatch(const std::string& name,PPCContext& ctx,u8* base) {']
    for name,address in symbols.items():lines.append(f'if(name=="{name}") {{ fixtures_{address:X}(ctx,base);return; }}')
    lines+=['throw std::runtime_error("unknown fixture");','}']
    (output/'dispatch.h').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def classify(code,log,cases,mutation=False):
    if any(t in log for t in ('AddressSanitizer','LeakSanitizer','runtime error:','PPC_ORACLE_ERROR:')):return False
    try:rows=[json.loads(s) for s in log.splitlines() if s.startswith('{')]
    except json.JSONDecodeError:return False
    if len(rows)!=len(cases)+1 or [r.get('id') for r in rows[:-1]]!=[r['id'] for r in cases]:return False
    if any(r.get('status')=='PASS' and r.get('mismatches')!=[] for r in rows[:-1]):return False
    failures=[r for r in rows[:-1] if r.get('status')!='PASS']
    if mutation:
        return (code==1 and len(failures)==1 and failures[0].get('id')==cases[0]['id']
                and rows[-1]==dict(completed=len(cases),failures=1)
                and failures[0].get('mismatches')==[dict(register='r3',expected=cases[0]['out']['r3'],actual=0)])
    return code==0 and not failures and rows[-1]==dict(completed=len(cases),failures=0)

def linux_calibration(output,tools,env):
    source=output/'host-calibration.cpp'
    source.write_text('#include <cstdint>\n#include <cstdio>\nint main(int argc,char**) { '
        'volatile std::int64_t value=argc==1?41:INT64_MAX; auto result=value+1; '
        'std::printf("HOST_CALIBRATION:%lld\\n",static_cast<long long>(result)); return 0; }\n',encoding='utf-8')
    binary=output/'host-calibration'
    command=[str(tools['clang++']),'--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13',
        '-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize=vptr',str(source),'-o',str(binary)]
    with (output/'host-calibration-build.log').open('wb') as log:
        subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=60,check=True)
    rows=[];child=dict(env,UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',ASAN_OPTIONS='detect_leaks=1')
    for name,arguments in [('positive',[]),('signed-overflow',['mutation'])]:
        result=subprocess.run([str(binary),*arguments],env=child,capture_output=True,timeout=20)
        data=result.stdout+result.stderr;path=output/('host-calibration-'+name+'.log');path.write_bytes(data)
        passed=(result.returncode==0 and data.strip()==b'HOST_CALIBRATION:42') if not arguments else (
            result.returncode==1 and b'runtime error: signed integer overflow' in data)
        rows.append(dict(case=name,returncode=result.returncode,status='PASS' if passed else 'FAIL',log_sha256=prep.sha(path)))
    if not all(r['status']=='PASS' for r in rows):raise ValueError('host sanitizer calibration failed')
    return dict(command=command,source_sha256=prep.sha(source),binary_sha256=prep.sha(binary),results=rows)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','sdk-report','output-root'):parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--sanitizers',action='store_true')
    parser.add_argument('--sdk-profile',choices=('memory','stop'),default='memory')
    parser.add_argument('--reference',type=Path,help='Windows: successful canonical Linux synthetic fixture preparation')
    parser.add_argument('--seed',type=lambda n:int(n,0),default=0x20110360)
    args=parser.parse_args();output=None
    report=dict(schema_version=1,evidence_class='original-synthetic-ppc-oracle',owned_title_executed=False,
                performance_measured=False,script_sha256=prep.sha(__file__),sources=source_snapshot(),
                python=dict(version=sys.version,executable_sha256=prep.sha(sys.executable)),results=[])
    try:
        output=prep.private_cache(args.output_root,ROOT/'game')/uuid.uuid4().hex;output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))),flush=True)
        def run(label,command,env=None,timeout=180):
            command=list(map(str,command));path=output/(label+'.log')
            with path.open('wb') as log:r=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout,cwd=output)
            report.setdefault('commands',[]).append(dict(label=label,command=command,returncode=r.returncode,log_sha256=prep.sha(path)))
            if r.returncode:raise ValueError(f'{label} failed')
            return path.read_text(encoding='utf-8',errors='replace')
        windows=sys.platform=='win32';root=args.root.resolve()
        import prepare_runtime_memory as memory
        # Generation uses a native SDK. Sanitizers instrument the adapter and
        # emitted instructions, not an accidentally mixed native/core-ASan CLI.
        if args.sdk_profile=='stop':
            import prepare_runtime_stop as selected
        else:selected=memory
        sdk,evidence=selected.verify_prepared(root,args.sdk_report)
        receipt=json.loads(args.sdk_report.read_text());report.update(sdk=evidence,sdk_report_sha256=prep.sha(args.sdk_report))
        source=root/('sources/rexglue-stop' if args.sdk_profile=='stop' else 'sources/rexglue-decommit')
        if windows:
            import prepare_windows_runtime as win
            lock=json.loads(win.LOCK.read_text());clang,compiler=win.compiler(root,lock['compiler'],False)
            env,cmake,ninja,host=win.msvc_environment(lock,clang)
            llvm=clang/'bin';extra=['-DCMAKE_MAKE_PROGRAM='+ninja.as_posix(),'-DCMAKE_CXX_FLAGS=-march=x86-64-v2','-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld']
            report.update(compiler=compiler,host=host)
            if args.sanitizers:report['calibration']=win.calibrate_sanitizer(output,clang,env)
        else:
            if sys.platform!='linux':raise ValueError('unsupported host')
            llvm=Path('/usr/lib/llvm-20/bin');env=dict(os.environ);cmake='cmake'
            extra=['-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13',
                   '-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2']
        suffix='.exe' if windows else ''
        names=('clang','clang++','llvm-readobj') if windows else ('clang','clang++','ld.lld','llvm-objcopy','llvm-nm','llvm-objdump')
        tools={n:llvm/(n+suffix) for n in names}
        if not windows:
            # These three metadata utilities come from the existing LLVM 18
            # host preparation. Assembly, linking and host compilation use 20.
            for n in ('llvm-objcopy','llvm-nm','llvm-objdump'):tools[n]=Path('/usr/bin')/(n+'-18')
        report['tools']={n:dict(path=str(p),sha256=prep.sha(p),version=subprocess.check_output([p,'--version'],env=env,text=True).splitlines()[0]) for n,p in tools.items()}
        if not re.search(r'clang version 20\.1\.2\b',report['tools']['clang++']['version']):raise ValueError('wrong compiler')
        if args.sanitizers and not windows:report['calibration']=linux_calibration(output,tools,env)
        recipe=prep.validate_recipe(json.loads((ROOT/'config/recomp/recipe.json').read_text()))
        production=ROOT/'runtime/bringup/CMakeLists.txt'
        if 'target_compile_options(guest PRIVATE ${guest_options} -fwrapv -ffp-contract=off)' not in production.read_text():
            raise ValueError('unreviewed production guest compile policy')
        report['production_guest_policy_sha256']=prep.sha(production)
        report['configuration']=dict(recipe_sha256=prep.sha(ROOT/'config/recomp/recipe.json'),vector_math=recipe['vector_math'],
            register_locals=False,forward_stack_stores=False,
            limitation='Original bounded fixture analysis; not the full-title discovery/import pipeline or full ISA.')
        bins=output/'bins';generated=output/'generated';bins.mkdir();generated.mkdir()
        reference=None
        if windows:
            if not args.reference:raise ValueError('Windows LLVM lacks PowerPC; canonical synthetic reference is required')
            reference=reference_bundle(args.reference,bins)
            report['reference_manifest_sha256']=prep.sha(args.reference/'manifest.json')
            nm=(bins/'fixtures.map').read_text()
        else:
            if args.reference:raise ValueError('canonical Linux preparation must assemble its own original inputs')
            run('assemble',[tools['clang'],'--target=powerpc64-unknown-linux-gnu','-mcpu=pwr7','-maltivec','-c',SOURCE/'fixtures.s','-o',bins/'fixtures.o'],env)
            run('link-ppc',[tools['ld.lld'],'-m','elf64ppc','-Ttext=0x82010000','-e','test_addc',bins/'fixtures.o','-o',bins/'fixtures.elf'],env)
            run('binary',[tools['llvm-objcopy'],'--only-section=.text','-O','binary',bins/'fixtures.elf',bins/'fixtures.bin'],env)
            nm=run('symbols',[tools['llvm-nm'],'--numeric-sort',bins/'fixtures.o'],env)
        symbols={};map_lines=[]
        for line in nm.splitlines():
            fields=line.split()
            if len(fields)==3 and fields[1].upper()=='T' and fields[2].startswith('test_'):
                offset=int(fields[0],16);symbols[fields[2]]=0x82010000+offset
                map_lines.append(f'{offset:08x} T {fields[2]}')
        if len(symbols)!=14:raise ValueError('unexpected fixture symbol inventory')
        (bins/'fixtures.map').write_bytes(('\n'.join(map_lines)+'\n').encode('utf-8'))
        if not windows:run('disassembly',[tools['llvm-objdump'],'-dr',bins/'fixtures.elf'],env)
        child={k:v for k,v in env.items() if not k.startswith(('REX_','LD_','ASAN_','UBSAN_','LSAN_'))}
        if not windows:child['LD_LIBRARY_PATH']=str(sdk/'lib')
        # The upstream CLI hardcodes stack forwarding on. Build a small test
        # adapter around unchanged codegen sources to use the actual title policy.
        key=prep.digest(dict(adapter=prep.snapshot(SOURCE/'generator'),sdk=evidence,tools=report['tools']))
        generator_build=output.parent/('generator-'+key)
        run('configure-generator',[cmake,'-S',SOURCE/'generator','-B',generator_build,'-G','Ninja',
            '-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_COMPILER='+tools['clang'].as_posix(),
            '-DCMAKE_CXX_COMPILER='+tools['clang++'].as_posix(),'-DCMAKE_PREFIX_PATH='+sdk.as_posix(),
            '-DMW3_SDK_SOURCE='+source.as_posix(),'-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG',*extra],env)
        run('build-generator',[cmake,'--build',generator_build,'--target','ppc-generator','--parallel','2'],env,timeout=900)
        # A later cache rebuild must not replace an earlier receipt's executable.
        generator=output/('ppc-generator'+suffix)
        shutil.copy2(generator_build/generator.name,generator)
        if windows:child['PATH']=str(sdk/'bin')+os.pathsep+child.get('PATH','')
        report.update(generator_sha256=prep.sha(generator),generator_binary=str(generator),
                      generator_build=str(generator_build),generator_key=key)
        run('generate',[generator,bins/'fixtures.bin',bins/'fixtures.map',generated],child)
        baseline=prep.snapshot(generated)
        second=output/'generated-repeat';second.mkdir()
        run('generate-repeat',[generator,bins/'fixtures.bin',bins/'fixtures.map',second],child)
        if baseline!=prep.snapshot(second):raise ValueError('synthetic generation not reproducible')
        if reference is not None:
            if baseline!=reference['generated']:raise ValueError('native Windows emission differs from canonical reference')
            report['generation_matches_reference']=True
        report.update(generated=baseline,assembly=prep.snapshot(bins),generation_reproduced=True,symbols=symbols)
        bindings(generated,symbols)
        run('configure',[cmake,'-S',SOURCE,'-B',output/'build','-G','Ninja','-DCMAKE_BUILD_TYPE=Release',
            '-DCMAKE_CXX_COMPILER='+tools['clang++'].as_posix(),'-DCMAKE_PREFIX_PATH='+sdk.as_posix(),
            '-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
            '-DMW3_GENERATED='+generated.as_posix(),'-DMW3_JSON_INCLUDE='+(source/'thirdparty/inja/third_party/include').as_posix(),
            '-DMW3_PPC_SANITIZERS='+('ON' if args.sanitizers else 'OFF'),*extra],env)
        run('build',[cmake,'--build',output/'build','--target','ppc-oracle','--parallel','2'],env)
        compile_commands=output/'build/compile_commands.json'
        compiled=json.loads(compile_commands.read_text())
        guest=next(row['command'] for row in compiled if Path(row['file']).name=='ppc_test_functions.cpp')
        host=next(row['command'] for row in compiled if Path(row['file']).name=='runner.cpp')
        if any(flag not in guest for flag in ('-fwrapv','-ffp-contract=off')) or '-fwrapv' in host:
            raise ValueError('guest/host compilation policy mismatch')
        report['compile_commands_sha256']=prep.sha(compile_commands)
        binary=output/'build'/('ppc-oracle'+suffix);report['binary_sha256']=prep.sha(binary)
        spec=importlib.util.spec_from_file_location('original_oracle',SOURCE/'oracle.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
        cases=oracle.cases(args.seed);report.update(seed=args.seed,case_count=len(cases),sanitizers=args.sanitizers)
        if not windows:
            linked=run('linkage',['ldd',binary],child)
            if str(sdk/'lib/librexkernel.so') not in linked:raise ValueError('wrong kernel loaded')
        else:
            linked=run('linkage',[tools['llvm-readobj'],'--coff-imports',binary],env)
            if 'rexkernel.dll' not in linked.lower():raise ValueError('runner does not import the kernel DLL')
        for label,data in [('oracle',cases),('mutation',copy.deepcopy(cases))]:
            if label=='mutation':data[0]['out']['r3']^=1
            path=output/(label+'.json');path.write_text(json.dumps(data),encoding='utf-8')
            log=output/(label+'.log');child.update(ASAN_OPTIONS='detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            with log.open('wb') as stream:r=subprocess.run([str(binary),str(path)],stdout=stream,stderr=subprocess.STDOUT,env=child,cwd=binary.parent,timeout=90)
            passed=classify(r.returncode,log.read_text(encoding='utf-8',errors='replace'),data,label=='mutation')
            row=dict(case=label,status='PASS' if passed else 'FAIL',returncode=r.returncode,case_file_sha256=prep.sha(path),log_sha256=prep.sha(log))
            report['results'].append(row);print(json.dumps(row),flush=True)
        _,after=selected.verify_prepared(root,args.sdk_report)
        if after!=evidence:raise ValueError('SDK changed during tests')
        if report['script_sha256']!=prep.sha(__file__) or report['sources']!=source_snapshot():
            raise ValueError('oracle source changed during tests')
        if report['generator_sha256']!=prep.sha(generator) or report['binary_sha256']!=prep.sha(binary):
            raise ValueError('executed binary changed during tests')
        if any(report['tools'][n]['sha256']!=prep.sha(p) for n,p in tools.items()):raise ValueError('compiler utility changed during tests')
        if report['production_guest_policy_sha256']!=prep.sha(production):raise ValueError('production guest policy changed during tests')
        if reference is not None and report['reference_manifest_sha256']!=prep.sha(args.reference/'manifest.json'):
            raise ValueError('synthetic reference receipt changed during tests')
        report['status']='PASS' if all(r['status']=='PASS' for r in report['results']) else 'FAIL'
        (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        return int(report['status']!='PASS')
    except (OSError,ValueError,KeyError,IndexError,subprocess.SubprocessError) as e:
        report.update(status='ERROR',error=str(e))
        if output:(output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        parser.exit(2,f'PPC oracle error: {type(e).__name__}; inspect {output}\n')
if __name__=='__main__':raise SystemExit(main())
