#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Run original memory contracts against an explicitly verified private SDK."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

import recompile as prep
from run_conformance import geometry

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"tests/memory"
SCENARIOS=("stack","aliases","boundaries","reservation","decommit-copy","decommit-view","decommit-store","release-policy",
           "stress","bad-oracle","guard-read","readonly-write","released-read","decommitted-read",
           "decommit-neighbors","decommit-invalid","physical-decommit","physical-decommitted-read")


def classify(case,code,text,windows=False):
    passed="MEMORY_CONTRACT_PASS" in text
    failed="MEMORY_CONTRACT_FAIL:" in text
    if any(x in text for x in ("ERROR: AddressSanitizer","ERROR: LeakSanitizer","runtime error:","UndefinedBehaviorSanitizer:")):
        return "FAIL"
    faults=("guard-read","readonly-write","released-read","decommitted-read","physical-decommitted-read")
    if case in faults:
        fault=(code&0xffffffff)==0xc0000005 if windows else code in (-11,-7)
        armed=text.count("MEMORY_FAULT_ARMED:"+case+" ")==1
        return "PASS" if armed and fault and not passed and not failed else "FAIL"
    if case=="bad-oracle":
        return "PASS" if code==1 and not passed and "MEMORY_CONTRACT_FAIL:seeded oracle/content mismatch" in text else "FAIL"
    return "PASS" if code==0 and passed and not failed else "FAIL"


def layouts(metadata):
    lock=json.loads((ROOT/"runtime/bringup/analysis-lock.json").read_text())
    inventory=json.loads((metadata/"report.json").read_text())
    manifest=json.loads(prep.DEFAULT.read_text())
    if inventory["identity"]!=manifest["id"]:raise ValueError("wrong title inventory")
    result={"synthetic":dict(PPC_IMAGE_BASE=0x82000000,PPC_IMAGE_SIZE=0x100000,PPC_CODE_BASE=0x82090000,PPC_CODE_SIZE=0x10000)}
    for role,filename in (("sp","default.xex"),("mp","default_mp.xex")):
        path=metadata/(role+"-image.json")
        entry=next(t for t in inventory["titles"] if t["role"]==role)
        expected=next(t for t in manifest["executables"] if t["name"]==filename)
        if prep.sha(path)!=lock[role]["metadata_sha256"] or entry["executable_sha256"]!=expected["sha256"]:
            raise ValueError("unreviewed geometry identity")
        result[role]=geometry(json.loads(path.read_text()),entry)
    return result


def linux_sdk(root,report_path,sanitizers):
    receipt=json.loads(report_path.read_text())
    if "profile" in receipt:
        import prepare_runtime_memory as memory
        return memory.verify_prepared(root,report_path,allow_sanitized=sanitizers)
    if not receipt.get("core_sanitizers"):
        sdk,evidence=prep.toolchain(root,report_path)
        return sdk,evidence
    # This path validates a test-only instrumented SDK; it is never used for
    # code generation or title execution, which keep their stronger refusal.
    pins=json.loads((prep.EXPERIMENT/"pins.json").read_text())
    pin=pins["rexglue_memory_derivative"]
    actual=prep.derive(root/"sources/rexglue-memory",prep.EXPERIMENT/pin["patch_path"],pin)
    if (not sanitizers or receipt.get("status")!="PASS" or receipt.get("source")!=actual
            or receipt.get("pins_sha256")!=prep.sha(prep.EXPERIMENT/"pins.json")
            or receipt.get("script_sha256")!=prep.sha(prep.EXPERIMENT/"prepare_rexglue_memory.py")):
        raise ValueError("unreviewed sanitizer SDK")
    sdk=Path(receipt["sdk_prefix"])
    for name,digest in receipt["final_libraries"].items():
        if Path(name).name!=name or prep.sha(sdk/"lib"/name)!=digest:raise ValueError("SDK library changed")
    return sdk,dict(source=actual,receipt_sha256=prep.sha(report_path),sdk_files=prep.snapshot(sdk,internal_links=True),core_sanitizers=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("root","sdk-report","metadata","output-root"):parser.add_argument("--"+name,required=True,type=Path)
    parser.add_argument("--sanitizers",action="store_true")
    args=parser.parse_args()
    report=dict(schema_version=1,evidence_class="original-synthetic-memory-contract",owned_title_executed=False,
                performance_measured=False,script_sha256=prep.sha(__file__),sources=prep.snapshot(SOURCE),results=[])
    output=None
    try:
        output=prep.private_cache(args.output_root,ROOT/"game")/uuid.uuid4().hex;output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))),flush=True)
        root=args.root.resolve();windows=sys.platform=="win32"
        if windows:
            import prepare_windows_runtime as win
            lock=json.loads(win.LOCK.read_text())
            clang,compiler=win.compiler(root,lock["compiler"],False)
            env,cmake,ninja,host=win.msvc_environment(lock,clang)
            receipt=json.loads(args.sdk_report.read_text());sdk=Path(receipt["sdk_prefix"])
            if "profile" in receipt:
                import prepare_runtime_memory as memory
                sdk,evidence=memory.verify_prepared(root,args.sdk_report,allow_sanitized=args.sanitizers)
                actual=receipt["source"]
            else:
                actual=win.sdk_derivative(root/"sources/rexglue-sdk",lock,output)
            if (receipt.get("status")!="PASS" or receipt.get("source")!=actual or receipt.get("compiler")!=compiler
                    or (receipt.get("windows_lock_sha256") if "profile" in receipt else receipt.get("lock_sha256"))!=prep.sha(win.LOCK)
                    or receipt["sdk_files"]!=prep.snapshot(sdk)):
                raise ValueError("Windows SDK receipt/source/artifact mismatch")
            report.update(compiler=compiler,host=host,sdk=dict(source=actual,sdk_files=receipt["sdk_files"]))
            compiler_path=clang/"bin/clang++.exe"
            extra=["-DCMAKE_MAKE_PROGRAM="+ninja.as_posix(),"-DCMAKE_CXX_FLAGS=-march=x86-64-v2","-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld"]
            if args.sanitizers:report["calibration"]=win.calibrate_sanitizer(output,clang,env)
        else:
            if sys.platform!="linux":raise ValueError("unsupported host")
            sdk,report["sdk"]=linux_sdk(root,args.sdk_report,args.sanitizers)
            compiler_path=Path(shutil.which("clang++-20") or "missing-compiler")
            version=subprocess.check_output([compiler_path,"--version"],text=True)
            pinned=json.loads((prep.EXPERIMENT/"pins.json").read_text())["compiler"]
            if not re.search(r"clang version "+re.escape(pinned)+r"\b",version):raise ValueError("compiler mismatch")
            report["compiler"]=dict(version=version.splitlines()[0],sha256=prep.sha(compiler_path))
            env=dict(os.environ);cmake="cmake"
            extra=["-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13",
                   "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2"]
        report.update(sdk_report_sha256=prep.sha(args.sdk_report),sanitizers=("windows-ubsan-trap" if windows else "linux-asan-ubsan") if args.sanitizers else "none")
        shapes=layouts(args.metadata)
        for layout,shape in shapes.items():
            lane=output/layout;lane.mkdir();build=lane/"build"
            command=[cmake,"-S",SOURCE,"-B",build,"-G","Ninja","-DCMAKE_BUILD_TYPE=Release",
                     "-DCMAKE_CXX_COMPILER="+compiler_path.as_posix(),"-DCMAKE_PREFIX_PATH="+sdk.as_posix(),
                     "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG","-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                     "-DMW3_MEMORY_SANITIZERS="+("ON" if args.sanitizers else "OFF"),*extra]
            command += [f"-D{k}={hex(v)}" for k,v in shape.items()]
            report.setdefault("builds",[]).append(dict(layout=layout,geometry=shape,configure_command=list(map(str,command))))
            for index,call in enumerate((command,[cmake,"--build",build,"--parallel","2"])):
                with (lane/f"build-{index}.log").open("wb") as log:
                    subprocess.run(list(map(str,call)),env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
            binary=build/("memory-contract.exe" if windows else "memory-contract")
            for scenario in SCENARIOS:
                for seed in ((1,0x12345678,0xffffffff) if scenario=="stress" else (0x12345678,)):
                    case=lane/(scenario+"-"+str(seed));case.mkdir();(case/"tmp").mkdir();(case/"config").mkdir()
                    command=[str(binary),scenario,str(seed),"--app.root="+str(case/"app"),"--app.user_root="+str(case/"user"),
                             "--title.game_root="+str(case),"--ui.driver=none","--hid.drivers=none","--apu.driver=none","--gpu.driver=none"]
                    if scenario=="released-read":command.append("--runtime.protect_on_release=true")
                    child={k:v for k,v in env.items() if not k.startswith(("REX_","MW3_","LD_","ASAN_","UBSAN_","LSAN_"))}
                    child.update(TMPDIR=str(case/"tmp"),TMP=str(case/"tmp"),TEMP=str(case/"tmp"),XDG_CONFIG_HOME=str(case/"config"),
                                 SDL_VIDEODRIVER="dummy",SDL_AUDIODRIVER="dummy",UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
                    if not windows:child["LD_LIBRARY_PATH"]=str(sdk/"lib")
                    # Expected native page-fault cases retain hardware signals.
                    # All other instrumented cases keep normal ASan reporting.
                    child["ASAN_OPTIONS"]="detect_leaks=1"+(":handle_segv=0:handle_sigbus=0" if scenario.endswith(("-read","-write")) else "")
                    with (case/"run.log").open("wb") as log:
                        try:
                            result=subprocess.run(command,cwd=build,env=child,stdout=log,stderr=subprocess.STDOUT,timeout=15,
                                                  creationflags=subprocess.CREATE_NO_WINDOW if windows else 0)
                            code=result.returncode
                        except subprocess.TimeoutExpired:code=-999
                    text=(case/"run.log").read_text(errors="replace")
                    row=dict(layout=layout,scenario=scenario,seed=seed,status=classify(scenario,code,text,windows),returncode=code,
                             command=command,binary_sha256=prep.sha(binary),log_sha256=prep.sha(case/"run.log"),
                             events=[line for line in text.splitlines() if line.startswith("MEMORY_")])
                    report["results"].append(row)
                    (output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
                    print(json.dumps({k:row[k] for k in ("layout","scenario","seed","status","returncode")}),flush=True)
        if windows:
            if receipt["sdk_files"]!=prep.snapshot(sdk):raise ValueError("SDK package changed during tests")
        else:
            _,after=linux_sdk(root,args.sdk_report,args.sanitizers)
            if after!=report["sdk"]:raise ValueError("SDK preparation changed during tests")
        report["status"]="PASS" if all(r["status"]=="PASS" for r in report["results"]) else "FAIL"
        (output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
        return int(report["status"]!="PASS")
    except (OSError,ValueError,KeyError,StopIteration,subprocess.SubprocessError) as error:
        report.update(status="ERROR",error=str(error))
        if output:(output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
        parser.exit(2,f"memory contract failed: {type(error).__name__}; inspect {output}\n")


if __name__=="__main__":raise SystemExit(main())
