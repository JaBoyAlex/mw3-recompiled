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
        read.append(f'if(key=="{n}") return ctx.{n}.u64;')
        write.append(f'if(key=="{n}") {{ ctx.{n}.u64=value;return; }}')
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

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','sdk-report','output-root'):parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--sanitizers',action='store_true')
    parser.add_argument('--seed',type=lambda n:int(n,0),default=0x20110360)
    args=parser.parse_args();output=None
    report=dict(schema_version=1,evidence_class='original-synthetic-ppc-oracle',owned_title_executed=False,
                performance_measured=False,script_sha256=prep.sha(__file__),sources=prep.snapshot(SOURCE),results=[])
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
        sdk,evidence=memory.verify_prepared(root,args.sdk_report)
        receipt=json.loads(args.sdk_report.read_text());report.update(sdk=evidence,sdk_report_sha256=prep.sha(args.sdk_report))
        source=root/'sources/rexglue-decommit'
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
        tools={n:llvm/(n+suffix) for n in ('clang','clang++','ld.lld','llvm-objcopy','llvm-nm','llvm-objdump')}
        if not windows:
            # These three metadata utilities come from the existing LLVM 18
            # host preparation. Assembly, linking and host compilation use 20.
            for n in ('llvm-objcopy','llvm-nm','llvm-objdump'):tools[n]=Path('/usr/bin')/(n+'-18')
        report['tools']={n:dict(path=str(p),sha256=prep.sha(p),version=subprocess.check_output([p,'--version'],env=env,text=True).splitlines()[0]) for n,p in tools.items()}
        if not re.search(r'clang version 20\.1\.2\b',report['tools']['clang++']['version']):raise ValueError('wrong compiler')
        recipe=prep.validate_recipe(json.loads((ROOT/'config/recomp/recipe.json').read_text()))
        production=ROOT/'runtime/bringup/CMakeLists.txt'
        if 'target_compile_options(guest PRIVATE ${guest_options} -fwrapv -ffp-contract=off)' not in production.read_text():
            raise ValueError('unreviewed production guest compile policy')
        report['production_guest_policy_sha256']=prep.sha(production)
        report['configuration']=dict(recipe_sha256=prep.sha(ROOT/'config/recomp/recipe.json'),vector_math=recipe['vector_math'],
            register_locals=False,forward_stack_stores=False,
            limitation='Original bounded fixture analysis; not the full-title discovery/import pipeline or full ISA.')
        bins=output/'bins';generated=output/'generated';bins.mkdir();generated.mkdir()
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
        (bins/'fixtures.map').write_text('\n'.join(map_lines)+'\n',encoding='utf-8')
        run('disassembly',[tools['llvm-objdump'],'-dr',bins/'fixtures.elf'],env)
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
        generator=generator_build/('ppc-generator'+suffix)
        report.update(generator_sha256=prep.sha(generator),generator_build=str(generator_build),generator_key=key)
        run('generate',[generator,bins/'fixtures.bin',bins/'fixtures.map',generated],child)
        baseline=prep.snapshot(generated)
        second=output/'generated-repeat';second.mkdir()
        run('generate-repeat',[generator,bins/'fixtures.bin',bins/'fixtures.map',second],child)
        if baseline!=prep.snapshot(second):raise ValueError('synthetic generation not reproducible')
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
        for label,data in [('oracle',cases),('mutation',copy.deepcopy(cases))]:
            if label=='mutation':data[0]['out']['r3']^=1
            path=output/(label+'.json');path.write_text(json.dumps(data),encoding='utf-8')
            log=output/(label+'.log');child.update(ASAN_OPTIONS='detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            with log.open('wb') as stream:r=subprocess.run([str(binary),str(path)],stdout=stream,stderr=subprocess.STDOUT,env=child,cwd=binary.parent,timeout=90)
            passed=classify(r.returncode,log.read_text(encoding='utf-8',errors='replace'),data,label=='mutation')
            row=dict(case=label,status='PASS' if passed else 'FAIL',returncode=r.returncode,case_file_sha256=prep.sha(path),log_sha256=prep.sha(log))
            report['results'].append(row);print(json.dumps(row),flush=True)
        _,after=memory.verify_prepared(root,args.sdk_report)
        if after!=evidence:raise ValueError('SDK changed during tests')
        if report['script_sha256']!=prep.sha(__file__) or report['sources']!=prep.snapshot(SOURCE):
            raise ValueError('oracle source changed during tests')
        if report['generator_sha256']!=prep.sha(generator) or report['binary_sha256']!=prep.sha(binary):
            raise ValueError('executed binary changed during tests')
        if any(report['tools'][n]['sha256']!=prep.sha(p) for n,p in tools.items()):raise ValueError('compiler utility changed during tests')
        if report['production_guest_policy_sha256']!=prep.sha(production):raise ValueError('production guest policy changed during tests')
        report['status']='PASS' if all(r['status']=='PASS' for r in report['results']) else 'FAIL'
        (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        return int(report['status']!='PASS')
    except (OSError,ValueError,KeyError,IndexError,subprocess.SubprocessError) as e:
        report.update(status='ERROR',error=str(e))
        if output:(output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        parser.exit(2,f'PPC oracle error: {type(e).__name__}; inspect {output}\n')
if __name__=='__main__':raise SystemExit(main())
