#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Prepare a pinned private native Windows SDK; never install globally or run a title."""
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


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",required=True,type=Path)
    parser.add_argument("--fetch",action="store_true")
    parser.add_argument("--build",action="store_true")
    parser.add_argument("--compiler-only",action="store_true")
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
