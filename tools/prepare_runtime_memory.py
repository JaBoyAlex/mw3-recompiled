#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build/verify an isolated selected-runtime memory derivative, preserving baselines."""
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

ROOT=Path(__file__).resolve().parents[1]
LOCK=ROOT/"config/toolchains/rexglue-memory/lock.json"


def composition(windows=False):
    lock=json.loads(LOCK.read_text())
    pins=json.loads((common.EXPERIMENT/"pins.json").read_text())
    base=pins["rexglue_memory_derivative"]
    paths=[(common.EXPERIMENT/base["patch_path"],base["patch_sha256"])]
    if windows:
        import prepare_windows_runtime as win
        profile=json.loads(win.LOCK.read_text())
        paths.append((win.LOCK.parent/profile["compatibility_patch"]["path"],profile["compatibility_patch"]["sha256"]))
    paths.append((LOCK.parent/lock["patch_path"],lock["patch_sha256"]))
    if lock["commit"]!=base["commit"] or any(common.sha(p)!=sha for p,sha in paths):
        raise ValueError("memory patch/base fingerprint mismatch")
    return b"\n".join(p.read_bytes() for p,_ in paths),lock


def source_identity(root,output,windows=False,existing=False):
    patch,lock=composition(windows)
    path=output/"combined-memory.patch"
    if path.exists():
        if path.read_bytes()!=patch:raise ValueError("recorded memory patch changed")
    elif existing:
        raise ValueError("recorded memory patch missing")
    else:path.write_bytes(patch)
    if existing:
        from mw2_tools import git
        if git(root/"sources/rexglue-decommit","diff","--quiet",lock["commit"],"--ignore-submodules=none",check=False).returncode==0:
            raise ValueError("prepared memory source was reset to baseline")
    return common.derive(root/"sources/rexglue-decommit",path,dict(commit=lock["commit"],patch_sha256=common.sha(path)))


def package_files(sdk):
    return {n:v for n,v in common.snapshot(sdk,internal_links=sys.platform!="win32").items() if not n.startswith("bin/logs/")}


def verify_prepared(root,report_path,allow_sanitized=False):
    receipt=json.loads(report_path.read_text())
    lock=json.loads(LOCK.read_text())
    if (receipt.get("status")!="PASS" or receipt.get("profile")!=lock["profile"]
            or receipt.get("memory_lock_sha256")!=common.sha(LOCK)
            or receipt.get("script_sha256")!=common.sha(__file__)
            or receipt.get("core_sanitizers") and not allow_sanitized):
        raise ValueError("unreviewed or validation-only memory preparation")
    windows=sys.platform=="win32"
    # Verify exact composition without changing any tracked or baseline file.
    actual=source_identity(root,report_path.parent,windows,existing=True)
    if actual!=receipt["source"]:raise ValueError("memory source tree changed")
    sdk=Path(receipt["sdk_prefix"])
    files=package_files(sdk)
    if files!=receipt["sdk_files"]:raise ValueError("memory SDK artifact changed")
    pins=json.loads((common.EXPERIMENT/"pins.json").read_text())
    if receipt["pins_sha256"]!=common.sha(common.EXPERIMENT/"pins.json"):
        raise ValueError("memory dependency pins changed")
    for entry in pins["sources"]:
        if entry["name"] in ("headers","vma"):common.verify_source(root/"sources"/entry["name"],entry)
    if windows:
        import prepare_windows_runtime as win
        if receipt["windows_lock_sha256"]!=common.sha(win.LOCK):raise ValueError("Windows compiler profile changed")
        _,compiler=win.compiler(root,json.loads(win.LOCK.read_text())["compiler"],False)
        if compiler!=receipt["compiler"]:raise ValueError("Windows compiler changed")
    else:
        entry=next(p for p in pins["sources"] if p["name"]=="rexglue-sdk")
        common.verify_source(root/"sources/rexglue-sdk",entry)
        compiler=Path(shutil.which("clang++-20") or "missing")
        if common.sha(compiler)!=receipt["compiler"]["sha256"]:raise ValueError("Linux compiler changed")
    return sdk,dict(source=receipt["baseline_source"],derivative=actual,memory_profile=lock["profile"],
                    memory_lock_sha256=common.sha(LOCK),preparation_sha256=common.sha(report_path),
                    sdk_files=files,sdk_tree_sha256=common.digest(files),core_sanitizers=receipt["core_sanitizers"])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("root","baseline-report"):parser.add_argument("--"+name,required=True,type=Path)
    parser.add_argument("--core-sanitizers",action="store_true")
    parser.add_argument("--fetch",action="store_true",help="create the isolated source worktree and fetch its pinned submodules")
    args=parser.parse_args();output=None
    report=dict(schema_version=1,guest_executed=False,release_package=False,core_sanitizers=args.core_sanitizers,
                script_sha256=common.sha(__file__),memory_lock_sha256=common.sha(LOCK),
                pins_sha256=common.sha(common.EXPERIMENT/"pins.json"))
    try:
        root=common.private_cache(args.root,ROOT/"game")
        output=root/"memory-preparations"/uuid.uuid4().hex;output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))),flush=True)
        windows=sys.platform=="win32"
        report["profile"]=json.loads(LOCK.read_text())["profile"]
        if windows:
            if args.core_sanitizers:raise ValueError("Windows full-core instrumentation is not supported by this profile")
            import prepare_windows_runtime as win
            wlock=json.loads(win.LOCK.read_text())
            clang,report["compiler"]=win.compiler(root,wlock["compiler"],False)
            env,cmake,ninja,report["host_tools"]=win.msvc_environment(wlock,clang)
            baseline=json.loads(args.baseline_report.read_text());sdk=Path(baseline["sdk_prefix"])
            if (baseline.get("status")!="PASS" or baseline["sdk_files"]!=package_files(sdk)
                    or baseline["source"]!=win.sdk_derivative(root/"sources/rexglue-sdk",wlock,output)
                    or baseline["compiler"]!=report["compiler"] or baseline["lock_sha256"]!=common.sha(win.LOCK)):
                raise ValueError("Windows baseline changed")
            for entry in wlock["sources"]:
                if entry["name"]!="rexglue-sdk":common.verify_source(root/"sources"/entry["name"],entry)
            report["windows_lock_sha256"]=common.sha(win.LOCK)
            report["baseline_source"]=baseline["source"]
            cc=(clang/"bin/clang.exe").as_posix();cxx=(clang/"bin/clang++.exe").as_posix()
            extra=["-DCMAKE_MAKE_PROGRAM="+ninja.as_posix(),"-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld",
                   "-DCMAKE_SHARED_LINKER_FLAGS=-fuse-ld=lld","-DVulkan_LIBRARY="+(root/"vulkan-import/vulkan-1.lib").as_posix()]
            cflags="-march=x86-64-v2"
        else:
            if sys.platform!="linux":raise ValueError("unsupported host")
            sdk,base=common.toolchain(root,args.baseline_report)
            report["baseline_source"]=base["source"]
            cc="clang-20";cxx="clang++-20";cmake="cmake";env=dict(os.environ)
            compiler=Path(shutil.which(cxx));version=subprocess.check_output([compiler,"--version"],text=True)
            pinned=json.loads((common.EXPERIMENT/"pins.json").read_text())["compiler"]
            if not re.search(r"clang version "+re.escape(pinned)+r"\b",version):raise ValueError("compiler mismatch")
            report["compiler"]=dict(sha256=common.sha(compiler),version=version.splitlines()[0])
            sanitizer=" -fsanitize=address,undefined -fno-sanitize=vptr -fno-omit-frame-pointer" if args.core_sanitizers else ""
            cflags="-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13"+sanitizer
            link="-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2"+sanitizer
            extra=["-DCMAKE_EXE_LINKER_FLAGS="+link,"-DCMAKE_SHARED_LINKER_FLAGS="+link,
                   "-DREXGLUE_GCC_INSTALL_DIR=/usr/lib/gcc/x86_64-linux-gnu/13","-DVulkan_LIBRARY=/usr/lib/x86_64-linux-gnu/libvulkan.so"]
        baseline_files=package_files(sdk)
        report.update(baseline_report_sha256=common.sha(args.baseline_report),baseline_sdk_files=baseline_files)
        source=root/"sources/rexglue-decommit"
        if not source.exists():
            if not args.fetch:raise ValueError("isolated source absent; explicit --fetch required")
            with (output/"source-worktree.log").open("wb") as log:
                subprocess.run(["git","-C",str(root/"sources/rexglue-sdk"),"worktree","add","--detach",str(source),
                                json.loads(LOCK.read_text())["commit"]],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
        if args.fetch:
            with (output/"source-submodules.log").open("wb") as log:
                subprocess.run(["git","-C",str(source),"submodule","update","--init","--recursive","--depth","1","--jobs","2"],
                               stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
        report["source"]=source_identity(root,output,windows)
        print(json.dumps(dict(stage="source-verified",profile=report["profile"])),flush=True)
        build=root/"build"/("rexglue-decommit-asan" if args.core_sanitizers else "rexglue-decommit")
        source=root/"sources/rexglue-decommit"
        command=[cmake,"-S",source,"-B",build,"-G","Ninja","-DCMAKE_BUILD_TYPE=Release",
                 "-DCMAKE_C_COMPILER="+cc,"-DCMAKE_CXX_COMPILER="+cxx,
                 "-DCMAKE_C_FLAGS="+cflags,"-DCMAKE_CXX_FLAGS="+cflags,
                 "-DCMAKE_C_FLAGS_RELEASE=-O2 -DNDEBUG","-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG",
                 "-DPYTHON_EXECUTABLE="+sys.executable,"-DREX_OUTPUT_DIR="+(build/"sdk-output").as_posix(),
                 "-DREXGLUE_BUILD_TESTS=OFF","-DREXGLUE_BUILD_PPC_TESTS=OFF","-DREXGLUE_ENABLE_TRACY=OFF","-DREXGLUE_REGISTER_PACKAGE=OFF",
                 "-DVulkan_INCLUDE_DIR="+(root/"sources/headers/include").as_posix(),
                 "-DREXGLUE_VMA_INCLUDE_DIR="+(root/"sources/vma/include").as_posix(),*extra]
        report["configure_command"]=list(map(str,command))
        for index,call in enumerate((command,[cmake,"--build",build,"--target","rexkernel","--parallel","2"])):
            print(json.dumps(dict(stage="configure" if index==0 else "build",log=str(output/f"build-{index}.log"))),flush=True)
            with (output/f"build-{index}.log").open("wb") as log:
                subprocess.run(list(map(str,call)),env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
        package=output/"sdk";shutil.copytree(sdk,package,symlinks=not windows)
        changed={}
        for name in ("rexbase","rexppc","rexkernel"):
            source_lib=build/"sdk-output"/(name+".dll" if windows else "lib"+name+".so")
            target=package/("bin" if windows else "lib")/source_lib.name
            shutil.copy2(source_lib,target);changed[source_lib.name]=common.sha(target)
        if package_files(sdk)!=baseline_files:raise ValueError("baseline SDK changed during preparation")
        report.update(status="PASS",sdk_prefix=str(package),replaced_libraries=changed,sdk_files=package_files(package))
        (output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
        verify_prepared(root,output/"manifest.json",allow_sanitized=args.core_sanitizers)
        print(json.dumps(dict(status="PASS",report=str(output/"manifest.json"))),flush=True)
        return 0
    except (OSError,ValueError,KeyError,StopIteration,subprocess.SubprocessError) as error:
        report.update(status="ERROR",error=str(error))
        if output:(output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
        parser.exit(2,f"memory SDK preparation failed: {type(error).__name__}; inspect {output}\n")


if __name__=="__main__":raise SystemExit(main())
