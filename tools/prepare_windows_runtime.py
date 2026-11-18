#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Prepare a pinned private Windows SDK and optionally run guarded owned-title probes."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import uuid

import recompile as common

ROOT=Path(__file__).resolve().parents[1]
LOCK=ROOT/"config/toolchains/rexglue-windows/lock.json"
TOOLS={"clang.exe","clang++.exe","clang-cl.exe","lld-link.exe","ld.lld.exe","llvm-lib.exe",
       "llvm-ar.exe","llvm-readobj.exe","llvm-dlltool.exe","llvm-objdump.exe","llvm-mc.exe","llvm-objcopy.exe","llvm-rc.exe"}


def selected_member(name, archive_root):
    path=PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError("unsafe compiler archive member")
    if not path.parts or path.parts[0]!=archive_root:raise ValueError("unexpected compiler archive root")
    relative=PurePosixPath(*path.parts[1:])
    parts=relative.parts
    selected=(len(parts)==2 and parts[0]=="bin" and (parts[1] in TOOLS or parts[1].endswith(".dll"))) or (
        len(parts)>3 and parts[:3]==("lib","clang","20")) or (len(parts)==1 and parts[0].lower().startswith(("license","notice")))
    return relative.as_posix() if selected else None


def extract_compiler(archive, output, entry):
    if common.sha(archive)!=entry["sha256"] or archive.stat().st_size!=entry["size"]:
        raise ValueError("compiler archive fingerprint mismatch")
    links=[]
    total=0
    with tarfile.open(archive,"r|xz") as stream:
        for member in stream:
            name=selected_member(member.name,entry["archive_root"])
            if not name or member.isdir():continue
            destination=output/name
            if member.islnk():
                target=selected_member(member.linkname,entry["archive_root"])
                if not target:raise ValueError("compiler hardlink outside selected inputs")
                links.append((destination,output/target));continue
            if not member.isfile():raise ValueError("nonregular selected compiler member")
            total+=member.size
            if total>4*1024**3:raise ValueError("selected compiler exceeds 4 GiB budget")
            destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open("xb") as target,stream.extractfile(member) as source:
                shutil.copyfileobj(source,target,1024*1024)
    for destination,source in links:
        if not source.is_file():raise ValueError("unresolved selected compiler hardlink")
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)
    required={"clang.exe","clang++.exe","clang-cl.exe","lld-link.exe","llvm-dlltool.exe","llvm-readobj.exe"}
    if not all((output/"bin"/name).is_file() for name in required):raise ValueError("incomplete selected compiler")
    files=common.snapshot(output)
    (output/"compiler-files.json").write_text(json.dumps(files,indent=2,sort_keys=True)+"\n")
    return files


def run(command, log=None, env=None, timeout=1200):
    if log:
        with Path(log).open("wb") as output:
            result=subprocess.run(list(map(str,command)),env=env,stdout=output,stderr=subprocess.STDOUT,timeout=timeout)
        if result.returncode:raise ValueError(f"command failed; inspect {Path(log).name}")
        return ""
    result=subprocess.run(list(map(str,command)),env=env,capture_output=True,text=True,timeout=timeout)
    if result.returncode:raise ValueError("host command failed; diagnostic retained by caller")
    return result.stdout


def compiler(root, entry, fetch):
    archive=root/entry["name"]
    if not archive.exists():
        if not fetch:raise ValueError("compiler archive absent; explicit --fetch required")
        partial=root/(entry["name"]+".partial")
        with urllib.request.urlopen(entry["url"],timeout=60) as source,partial.open("xb") as target:
            shutil.copyfileobj(source,target,4*1024*1024)
        if common.sha(partial)!=entry["sha256"] or partial.stat().st_size!=entry["size"]:
            raise ValueError("download fingerprint mismatch; partial retained")
        partial.rename(archive)
    destination=root/("llvm-"+entry["version"])
    if not destination.exists():
        temporary=root/("compiler-attempt-"+uuid.uuid4().hex)
        temporary.mkdir()
        extract_compiler(archive,temporary,entry)
        temporary.rename(destination)
    files=json.loads((destination/"compiler-files.json").read_text())
    actual={name:row for name,row in common.snapshot(destination).items() if name!="compiler-files.json"}
    if actual!=files:raise ValueError("extracted compiler changed")
    version=run([destination/"bin/clang++.exe","--version"])
    if not re.search(r"clang version "+re.escape(entry["version"])+r"\b",version):raise ValueError("unexpected compiler version")
    return destination,dict(archive_sha256=entry["sha256"],files_sha256=common.digest(files),version=version.splitlines()[0])


def msvc_environment(lock, compiler_root):
    vswhere=Path(os.environ.get("ProgramFiles(x86)","C:/Program Files (x86)"))/"Microsoft Visual Studio/Installer/vswhere.exe"
    install=Path(run([vswhere,"-latest","-products","*","-requires","Microsoft.VisualStudio.Component.VC.Tools.x86.x64","-property","installationPath"]).strip())
    batch=install/"VC/Auxiliary/Build/vcvars64.bat"
    # Capture privately. Never print `set`: the inherited environment may hold credentials.
    command='"'+str(batch)+'" '+lock["windows_sdk"]+' -vcvars_ver='+lock["msvc_tools"]+' >nul && set'
    command_line=subprocess.list2cmdline([os.environ.get("COMSPEC","cmd.exe")])+' /d /s /c "'+command+'"'
    result=subprocess.run(command_line,capture_output=True,text=True,timeout=60)
    if result.returncode:raise ValueError("MSVC environment preparation failed")
    env={name.upper():value for name,value in os.environ.items()}
    for line in result.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            name,value=line.split("=",1);env[name.upper()]=value
    if env.get("VCTOOLSVERSION","").strip("\\/")!=lock["msvc_tools"] or env.get("WINDOWSSDKVERSION","").strip("\\/")!=lock["windows_sdk"]:
        raise ValueError("installed MSVC/Windows SDK differs from locked profile")
    cmake=install/"Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
    ninja=install/"Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe"
    env["PATH"]=str(compiler_root/"bin")+os.pathsep+str(ninja.parent)+os.pathsep+env.get("PATH","")
    return env,cmake,ninja,dict(msvc=env["VCTOOLSVERSION"],windows_sdk=env["WINDOWSSDKVERSION"],
                              cmake_sha256=common.sha(cmake),ninja_sha256=common.sha(ninja),
                              python_sha256=common.sha(sys.executable),python_version=sys.version,
                              include=env.get("INCLUDE",""),lib=env.get("LIB",""))


def source(root, entry, fetch, output):
    destination=root/"sources"/entry["name"]
    if not destination.exists():
        if not fetch:raise ValueError("pinned source absent: "+entry["name"])
        run(["git","init",destination],output/(entry["name"]+"-init.log"))
        run(["git","-C",destination,"remote","add","origin",entry["url"]])
        run(["git","-C",destination,"fetch","--depth","1","origin",entry["commit"]],output/(entry["name"]+"-fetch.log"))
        run(["git","-C",destination,"checkout","--detach",entry["commit"]],output/(entry["name"]+"-checkout.log"))
    if fetch and entry["submodules"]:
        run(["git","-C",destination,"submodule","update","--init","--recursive","--depth","1","--jobs","2"],output/(entry["name"]+"-submodules.log"))
    if entry["name"]!="rexglue-sdk":common.verify_source(destination,entry)
    return destination


def sdk_derivative(source, lock, output):
    pins=json.loads((common.EXPERIMENT/"pins.json").read_text())
    base=pins["rexglue_memory_derivative"]
    extra=LOCK.parent/lock["compatibility_patch"]["path"]
    if common.sha(extra)!=lock["compatibility_patch"]["sha256"]:
        raise ValueError("Windows compatibility patch fingerprint mismatch")
    combined=output/"combined-sdk.patch"
    combined.write_bytes((common.EXPERIMENT/base["patch_path"]).read_bytes()+b"\n"+extra.read_bytes())
    pin=dict(commit=base["commit"],patch_sha256=common.sha(combined))
    try:
        return common.derive(source,combined,pin)
    except ValueError:
        # Upgrade only an exactly verified earlier base derivative; never
        # discard an unknown contributor edit to make the patch apply.
        common.derive(source,common.EXPERIMENT/base["patch_path"],base)
        run(["git","-C",source,"apply","--check",extra])
        run(["git","-C",source,"apply",extra])
        return common.derive(source,combined,pin)


def stage_reference(reference, destination, identity, expected_manifest_sha256):
    """Copy only a locally reviewed immutable generation receipt and payload."""
    reference=common.no_symlink_path(reference)
    if common.sha(reference/"manifest.json")!=expected_manifest_sha256:
        raise ValueError("reference generation receipt fingerprint mismatch")
    receipt=json.loads((reference/"manifest.json").read_text())
    inputs=receipt["inputs"]
    pins=json.loads((common.EXPERIMENT/"pins.json").read_text())
    base=pins["rexglue_memory_derivative"]
    expected_patch=base["patch_sha256"]
    if "memory_profile" in inputs["toolchain"]:
        import prepare_runtime_memory as memory
        patch,profile=memory.composition(False)
        if (inputs["toolchain"]["memory_profile"]!=profile["profile"] or
                inputs["toolchain"]["memory_lock_sha256"]!=common.sha(memory.LOCK)):
            raise ValueError("unreviewed reference memory profile")
        import hashlib
        expected_patch=hashlib.sha256(patch).hexdigest()
    if (receipt["key"]!=reference.name or common.digest(inputs)!=reference.name or inputs["title"]!=identity
            or inputs["recipe"]!=common.validate_recipe(json.loads(common.RECIPE.read_text()))
            or inputs["recipe_sha256"]!=common.sha(common.RECIPE)
            or inputs["driver_sha256"]!=common.sha(common.__file__)
            or inputs["title_manifest_sha256"]!=common.sha(common.DEFAULT)
            or inputs["helper_sha256"]!={name:common.sha(common.EXPERIMENT/name) for name in ("prepare.py","mw2_tools.py","inspect_owned.py")}
            or inputs["toolchain"]["source"]["commit"]!=base["commit"]
            or inputs["toolchain"]["derivative"]["base_commit"]!=base["commit"]
            or inputs["toolchain"]["derivative"]["patch_sha256"]!=expected_patch):
        raise ValueError("reference generation does not match reviewed title/source/recipe contract")
    common.read_cache(reference,reference.name,inputs)
    destination=common.no_symlink_path(destination)
    if destination.is_relative_to(reference) or reference.is_relative_to(destination):
        raise ValueError("staging destination overlaps immutable reference")
    if destination.exists():
        common.read_cache(destination,reference.name,inputs)
        return destination,receipt
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.parent/("stage-attempt-"+uuid.uuid4().hex)
    shutil.copytree(reference,temporary,symlinks=False)
    common.read_cache(temporary,reference.name,inputs)
    temporary.rename(destination)
    return destination,receipt


def calibrate_sanitizer(output,clang,env):
    """An original inert positive/overflow pair proves trap checks are active."""
    source=output/"original-sanitizer-calibration.cpp"
    source.write_text('#include <cstdio>\nint main(int argc,char**) { volatile int value=argc==1?41:2147483647; '
                      'int result=value+1; std::printf("ORIGINAL_CALIBRATION:%d\\n",result); return 0; }\n')
    binary=output/"original-sanitizer-calibration.exe"
    command=[clang/"bin/clang++.exe","-std=c++20","-O2","-fms-runtime-lib=dll","-fsanitize=undefined",
             "-fno-sanitize=vptr","-fsanitize-trap=all","-fuse-ld=lld",source,"-o",binary]
    run(command,output/"calibration-build.log",env)
    results=[]
    for case,arguments in (("positive",[]),("signed-overflow",["mutation"])):
        result=subprocess.run([str(binary),*arguments],env=env,capture_output=True,timeout=20,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        (output/("calibration-"+case+".log")).write_bytes(result.stdout+result.stderr)
        passed=(result.returncode==0 and result.stdout.strip()==b"ORIGINAL_CALIBRATION:42") if case=="positive" else (
            result.returncode&0xffffffff)==0xc000001d
        results.append(dict(case=case,returncode=result.returncode,status="PASS" if passed else "FAIL"))
    if not all(row["status"]=="PASS" for row in results):raise ValueError("Windows UBSan trap calibration failed")
    return dict(mode="undefined-trap-no-vptr",source_sha256=common.sha(source),binary_sha256=common.sha(binary),
                command=list(map(str,command)),results=results)


def windows_probe(args, root, output, lock, clang, env, cmake, ninja, report):
    import runtime_probe as guarded
    if not all((args.sdk_report,args.owned,args.metadata,args.role,args.expected_generation_sha256)):
        raise ValueError("probe requires SDK receipt, owned pair, metadata, role and expected generation receipt SHA")
    if args.build or args.fetch:raise ValueError("probe consumes a verified SDK; prepare/build it separately")
    identity=common.verify(args.owned,json.loads(common.DEFAULT.read_text()))
    sdk_receipt=json.loads(args.sdk_report.read_text())
    sdk=Path(sdk_receipt["sdk_prefix"])
    source=root/"sources/rexglue-sdk"
    if "profile" in sdk_receipt:
        import prepare_runtime_memory as memory
        sdk,_=memory.verify_prepared(root,args.sdk_report)
        if sdk_receipt["compiler"]!=report["compiler"]:raise ValueError("memory SDK compiler mismatch")
    else:
        actual=sdk_derivative(source,lock,output)
        if (sdk_receipt.get("status")!="PASS" or sdk_receipt.get("source")!=actual
            or sdk_receipt.get("lock_sha256")!=common.sha(LOCK)
            or sdk_receipt.get("compiler")!=report["compiler"]
            or sdk_receipt["sdk_files"]!=common.snapshot(sdk)):
            raise ValueError("native SDK receipt/source/package mismatch")
    for entry in lock["sources"]:
        if entry["name"]!="rexglue-sdk":common.verify_source(root/"sources"/entry["name"],entry)
    staged,receipt=stage_reference(args.reference_cache,root/"generated"/args.reference_cache.name,
                                   identity,args.expected_generation_sha256)
    analysis=json.loads((guarded.HOST/"analysis-lock.json").read_text())
    meta=args.metadata/(args.role+"-image.json")
    if common.sha(meta)!=analysis[args.role]["metadata_sha256"]:raise ValueError("unreviewed title analysis metadata")
    prefix="mw3_"+args.role
    traps,address=guarded.guarded_traps(json.loads(meta.read_text()),prefix,analysis[args.role]["function_imports"])
    (output/"traps.cpp").write_text(traps)
    (output/"data-import.h").write_text('#pragma once\n#define MW3_MODULE_HANDLE_IMPORT '+hex(address)+'u\n')
    report.update(role=args.role,identity=identity,host_sanitizers="undefined-trap-no-vptr" if args.host_sanitizers else "none",reference_manifest_sha256=common.sha(staged/"manifest.json"),
                  sdk_receipt_sha256=common.sha(args.sdk_report),metadata_sha256=common.sha(meta),
                  host_sources={p.name:common.sha(p) for p in guarded.HOST.iterdir() if p.is_file()},
                  parser_sources={str(p.relative_to(ROOT)):common.sha(p) for p in (ROOT/"include/mw3/xex.hpp",ROOT/"src/xex.cpp")},
                  traps_sha256=common.sha(output/"traps.cpp"),data_import_sha256=common.sha(output/"data-import.h"),results=[])
    if args.host_sanitizers:report["sanitizer_calibration"]=calibrate_sanitizer(output,clang,env)
    build=output/"build"
    command=[cmake,"-S",guarded.HOST,"-B",build,"-G","Ninja","-DCMAKE_MAKE_PROGRAM="+str(ninja),
             "-DCMAKE_CXX_COMPILER="+(clang/"bin/clang++.exe").as_posix(),"-DCMAKE_BUILD_TYPE=Release",
             "-DCMAKE_CXX_FLAGS=-march=x86-64-v2","-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG",
             "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld","-DCMAKE_PREFIX_PATH="+sdk.as_posix(),
             "-DMW3_GENERATED_DIR="+(staged/"payload"/args.role/"generated").as_posix(),"-DMW3_GENERATED_PREFIX="+prefix,
             "-DMW3_PRIVATE_TRAPS="+(output/"traps.cpp").as_posix(),"-DMW3_DATA_IMPORT_HEADER="+(output/"data-import.h").as_posix(),
             "-DMW3_PROBE_SANITIZERS="+("ON" if args.host_sanitizers else "OFF")]
    report["configure_command"]=list(map(str,command))
    run(command,output/"probe-configure.log",env)
    run([cmake,"--build",build,"--parallel","2"],output/"probe-build.log",env,timeout=1800)
    binary=build/"mw3-header-probe.exe"
    report["binary_sha256"]=common.sha(binary)
    report["libraries"]={p.name:common.sha(p) for p in build.glob("*.dll")}
    for case in ("positive-0","positive-1","positive-2","bad-binding","bad-pointer","bad-oracle"):
        profile=output/case;profile.mkdir();(profile/"tmp").mkdir();(profile/"config").mkdir()
        filename="default.xex" if args.role=="sp" else "default_mp.xex"
        command=[str(binary),"--kernel.headless=true","--title.game_root="+str(args.owned.resolve()),"--title.entry="+filename,
                 "--app.root="+str(profile/"app"),"--app.user_root="+str(profile/"user"),
                 "--ui.driver=none","--hid.drivers=none","--apu.driver=none","--gpu.driver=none"]
        child={k:v for k,v in env.items() if not k.startswith(("REX_","MW3_HEADER_","ASAN_","UBSAN_","LD_"))}
        child.update(MW3_HEADER_OWNED_FILE=str((args.owned/filename).resolve()),TMP=str(profile/"tmp"),TEMP=str(profile/"tmp"),
                     XDG_CONFIG_HOME=str(profile/"config"),SDL_VIDEODRIVER="dummy",SDL_AUDIODRIVER="dummy")
        if args.host_sanitizers:
            child["UBSAN_OPTIONS"]="halt_on_error=1:print_stacktrace=1"
        if case=="bad-binding":child["MW3_HEADER_TEST_BAD_BINDING"]="1"
        if case=="bad-pointer":child["MW3_HEADER_TEST_BAD_POINTER"]="1"
        if case=="bad-oracle":child["MW3_HEADER_TEST_BAD_ORACLE"]="1"
        with (profile/"run.log").open("wb") as log:
            result=subprocess.run(command,cwd=build,env=child,stdout=log,stderr=subprocess.STDOUT,timeout=20,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        text=(profile/"run.log").read_text(errors="replace")
        events=[line for line in text.splitlines() if line.startswith("MW3_")]
        if case.startswith("positive"):
            passed=(result.returncode==86 and text.count("MW3_HEADER_ORACLE_CASE_PASS:")==4
                    and "MW3_HEADER_QUERY_PASS:" in text and "MW3_PROBE_UNREVIEWED_IMPORT:NtAllocateVirtualMemory" in text
                    and "MW3_HEADER_GUARD_FAILED:" not in text)
            report["guest_executed"] |= passed
        else:
            reason={"bad-binding":"function binding verification","bad-pointer":"unexpected header pointer",
                    "bad-oracle":"SDK header result differs from independent oracle"}[case]
            passed=result.returncode==87 and "MW3_HEADER_GUARD_FAILED:"+reason in text and "MW3_HEADER_QUERY_PASS:" not in text
        if any(marker in text for marker in ("ERROR: AddressSanitizer","ERROR: LeakSanitizer","runtime error:","UndefinedBehaviorSanitizer:")):
            passed=False
        row=dict(case=case,status="PASS" if passed else "FAIL",returncode=result.returncode,events=events,
                 log_sha256=common.sha(profile/"run.log"),command=command)
        report["results"].append(row)
        (output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps(dict(case=case,status=row["status"],events=events)),flush=True)
    common.verify(args.owned,json.loads(common.DEFAULT.read_text()))
    common.read_cache(staged,receipt["key"],receipt["inputs"])
    if sdk_receipt["sdk_files"]!=common.snapshot(sdk):raise ValueError("SDK package changed during probe")
    report["status"]="PASS" if all(row["status"]=="PASS" for row in report["results"]) else "INCOMPLETE"
    (output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    return int(report["status"]!="PASS")
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",required=True,type=Path)
    parser.add_argument("--fetch",action="store_true")
    parser.add_argument("--build",action="store_true")
    parser.add_argument("--compiler-only",action="store_true")
    parser.add_argument("--reference-cache",type=Path,help="locally reviewed immutable Linux generation entry, accessible on this machine")
    parser.add_argument("--expected-generation-sha256",help="independently checked generation manifest SHA-256")
    parser.add_argument("--sdk-report",type=Path)
    parser.add_argument("--owned",type=Path)
    parser.add_argument("--metadata",type=Path)
    parser.add_argument("--role",choices=("sp","mp"))
    parser.add_argument("--host-sanitizers",action="store_true",help="Windows UBSan trap mode (excluding vptr) for host harness/parser only; guest objects and SDK unchanged")
    args=parser.parse_args()
    output=None
    report=dict(schema_version=1,guest_executed=False,release_package=False,script_sha256=common.sha(__file__),lock_sha256=common.sha(LOCK))
    try:
        if sys.platform!="win32" or platform.machine().lower() not in ("amd64","x86_64"):
            raise ValueError("this profile requires native Windows x86-64")
        root=common.private_cache(args.root,ROOT/"game")
        root.mkdir(parents=True,exist_ok=True)
        if shutil.disk_usage(root).free<12*1024**3:raise ValueError("less than 12 GiB available")
        output=root/"runs"/uuid.uuid4().hex;output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output),guest_executed=False)),flush=True)
        lock=json.loads(LOCK.read_text())
        clang,report["compiler"]=compiler(root,lock["compiler"],args.fetch)
        env,cmake,ninja,report["host_tools"]=msvc_environment(lock,clang)
        if args.reference_cache:
            return windows_probe(args,root,output,lock,clang,env,cmake,ninja,report)
        if args.compiler_only:
            report["status"]="PASS";(output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
            print(json.dumps(dict(status="PASS",compiler_root=str(clang))),flush=True);return 0
        paths={entry["name"]:source(root,entry,args.fetch,output) for entry in lock["sources"]}
        report["other_sources"]={entry["name"]:common.verify_source(paths[entry["name"]],entry)
                                 for entry in lock["sources"] if entry["name"]!="rexglue-sdk"}
        report["source"]=sdk_derivative(paths["rexglue-sdk"],lock,output)
        definition=paths["loader"]/"loader/vulkan-1.def"
        import_lib=root/"vulkan-import/vulkan-1.lib";import_lib.parent.mkdir(exist_ok=True)
        run([clang/"bin/llvm-dlltool.exe","-m","i386:x86-64","-d",definition,"-l",import_lib],output/"vulkan-import.log",env)
        report["vulkan_import"]=dict(definition_sha256=common.sha(definition),library_sha256=common.sha(import_lib))
        build=root/"build/rexglue-release"
        command=[cmake,"-S",paths["rexglue-sdk"],"-B",build,"-G","Ninja",
                 "-DCMAKE_MAKE_PROGRAM="+str(ninja),"-DCMAKE_C_COMPILER="+str(clang/"bin/clang.exe"),
                 "-DCMAKE_CXX_COMPILER="+str(clang/"bin/clang++.exe"),"-DCMAKE_BUILD_TYPE=Release",
                 "-DPYTHON_EXECUTABLE="+sys.executable,"-DPython3_EXECUTABLE="+sys.executable,
                 "-DCMAKE_C_FLAGS=-march=x86-64-v2","-DCMAKE_CXX_FLAGS=-march=x86-64-v2",
                 "-DCMAKE_C_FLAGS_RELEASE=-O2 -DNDEBUG","-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG",
                 "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld","-DCMAKE_SHARED_LINKER_FLAGS=-fuse-ld=lld",
                 "-DREX_OUTPUT_DIR="+str(build/"sdk-output"),"-DCMAKE_INSTALL_PREFIX="+str(root/"install/rexglue"),
                 "-DREXGLUE_ENABLE_TRACY=OFF","-DREXGLUE_REGISTER_PACKAGE=OFF","-DREXGLUE_BUILD_TESTS=ON",
                 "-DREXGLUE_BUILD_PPC_TESTS=OFF","-DVulkan_INCLUDE_DIR="+str(paths["headers"]/"include"),
                 "-DVulkan_LIBRARY="+str(import_lib),"-DREXGLUE_VMA_INCLUDE_DIR="+str(paths["vma"]/"include")]
        report["configure_command"]=list(map(str,command))
        run(command,output/"configure.log",env)
        if args.build:
            run([cmake,"--build",build,"--parallel","2"],output/"build.log",env,timeout=3600)
            run([cmake,"--install",build],output/"install.log",env)
            report["sdk_prefix"]=str(root/"install/rexglue")
            report["sdk_files"]=common.snapshot(root/"install/rexglue")
        report["status"]="PASS"
        (output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps(dict(status="PASS",built=args.build,output=str(output))),flush=True)
        return 0
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        report.update(status="ERROR",error=str(error))
        if output:(output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
        parser.exit(2,f"Windows SDK preparation failed: {error}; private output={output}\n")


if __name__=="__main__":raise SystemExit(main())
