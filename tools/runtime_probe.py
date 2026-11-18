#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build verified private modules; admit one audited header query, stop elsewhere."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

import recompile as prep
from verify_inputs import DEFAULT, verify
from rexglue_probe import make_traps

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "runtime/bringup"


def guarded_traps(metadata, prefix, expected_count):
    result = make_traps(metadata, prefix)
    rows = [r for lib in metadata["import_audit"]["libraries"] for r in lib["records"]]
    if len([r for r in rows if r["type"] == 1]) != expected_count:
        raise ValueError("function import coverage differs from reviewed inventory")
    variable = [r for r in rows if r["export_name"] == "XexExecutableModuleHandle" and r["type"] == 0]
    if len(variable) != 1 or variable[0]["export_kind"] != "kVariable":
        raise ValueError("module-handle data import missing/ambiguous")
    address = variable[0]["address"]
    if type(address) is not int or not 0 <= address < 2**32 or address % 4:
        raise ValueError("invalid module-handle import address")
    marker = 'extern "C" void __imp__RtlImageXexHeaderField('
    lines = result.splitlines()
    selected = [n for n, line in enumerate(lines) if line.startswith(marker)]
    if len(selected) != 1:
        raise ValueError("header query import missing/ambiguous")
    lines[selected[0]] = marker + 'PPCContext&, u8*);'
    header_rows=[r for r in rows if r["type"]==1 and r["export_name"]=="RtlImageXexHeaderField"]
    others=[r for r in rows if r["type"]==1 and r["export_name"]!="RtlImageXexHeaderField"]
    if len(header_rows)!=1 or not others:raise ValueError("missing binding mutation fixture")
    original='runtime.FindFunction('+hex(header_rows[0]["address"])+')'
    mutated='runtime.FindFunction(std::getenv("MW3_HEADER_TEST_BAD_BINDING") ? '+hex(others[0]["address"])+' : '+hex(header_rows[0]["address"])+')'
    source='\n'.join(lines)+'\n'
    if source.count(original)!=1:raise ValueError("binding guard anchor differs")
    return source.replace(original,mutated), address


def verify_generation(directory, owned, root, sdk_report):
    manifest = json.loads((directory / "manifest.json").read_text())
    inputs = manifest["inputs"]
    key = directory.name
    if not re.fullmatch(r"[a-f0-9]{64}", key) or prep.digest(inputs) != key:
        raise ValueError("unrecognized generation cache key")
    recipe = prep.validate_recipe(json.loads(prep.RECIPE.read_text()))
    identity = verify(owned, json.loads(DEFAULT.read_text()))
    sdk, toolchain = prep.toolchain(root, sdk_report)
    expected = dict(title=identity, recipe=recipe, toolchain=toolchain,
                    recipe_sha256=prep.sha(prep.RECIPE), driver_sha256=prep.sha(prep.__file__),
                    title_manifest_sha256=prep.sha(DEFAULT),
                    helper_sha256={name: prep.sha(prep.EXPERIMENT / name) for name in ("prepare.py", "mw2_tools.py", "inspect_owned.py")})
    if inputs != expected:
        raise ValueError("generation does not match current reviewed inputs/toolchain/recipe")
    return sdk, prep.read_cache(directory, key, expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("owned", "cache-entry", "bakeoff-root", "sdk-report", "metadata", "output-root"):
        parser.add_argument("--"+name, required=True, type=Path)
    parser.add_argument("--role", choices=("sp", "mp"), required=True)
    parser.add_argument("--execute", action="store_true", help="three bounded runs plus deliberate guard failures")
    parser.add_argument("--host-sanitizers", action="store_true", help="instrument host harness/parser; generated guest code and SDK remain uninstrumented")
    args = parser.parse_args()
    output = None
    report = dict(schema_version=1, guest_executed=False, playable=False, service="RtlImageXexHeaderField",
                  script_sha256=prep.sha(__file__), results=[])
    try:
        if sys.platform != "linux": raise ValueError("this bring-up profile is Linux-only; native Windows is task 040")
        owned = args.owned.resolve()
        entry = prep.no_symlink_path(args.cache_entry)
        sdk, generated = verify_generation(entry, owned, args.bakeoff_root.resolve(), args.sdk_report.resolve())
        lock = json.loads((HOST / "analysis-lock.json").read_text())
        meta = args.metadata / (args.role + "-image.json")
        if prep.sha(meta) != lock[args.role]["metadata_sha256"]:
            raise ValueError("metadata differs from reviewed exact-title import inventory")
        metadata = json.loads(meta.read_text())
        prefix = "mw3_" + args.role
        traps, address = guarded_traps(metadata, prefix, lock[args.role]["function_imports"])
        output = prep.private_cache(args.output_root, owned) / uuid.uuid4().hex
        if output.is_relative_to(entry) or entry.is_relative_to(output):
            raise ValueError("probe output overlaps immutable generation cache")
        output.mkdir(parents=True)
        (output / "traps.cpp").write_text(traps)
        (output / "data-import.h").write_text('#pragma once\n#define MW3_MODULE_HANDLE_IMPORT '+hex(address)+'u\n')
        report.update(role=args.role, host_sanitizers=args.host_sanitizers, generation_manifest_sha256=prep.sha(entry/"manifest.json"),
                      metadata_sha256=prep.sha(meta), host_sources={p.name:prep.sha(p) for p in HOST.iterdir() if p.is_file()},
                      parser_sources={str(p.relative_to(ROOT)):prep.sha(p) for p in (ROOT/"include/mw3/xex.hpp",ROOT/"src/xex.cpp")},
                      traps_sha256=prep.sha(output/"traps.cpp"), data_import_sha256=prep.sha(output/"data-import.h"))
        print(json.dumps(dict(output=str(output),guest_executed=False)),flush=True)
        build = output / "build"
        commands = [["cmake","-S",str(HOST),"-B",str(build),"-G","Ninja",
                     "-DCMAKE_CXX_COMPILER=clang++-20","-DCMAKE_BUILD_TYPE=Release",
                     "-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13",
                     "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG","-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2",
                     "-DCMAKE_PREFIX_PATH="+str(sdk),"-DMW3_GENERATED_DIR="+str(entry/"payload"/args.role/"generated"),
                     "-DMW3_GENERATED_PREFIX="+prefix,"-DMW3_PRIVATE_TRAPS="+str(output/"traps.cpp"),
                     "-DMW3_DATA_IMPORT_HEADER="+str(output/"data-import.h"),
                     "-DMW3_PROBE_SANITIZERS="+("ON" if args.host_sanitizers else "OFF")],
                    ["cmake","--build",str(build),"--parallel","2"]]
        report["commands"] = commands
        for i,command in enumerate(commands):
            with (output/f"build-{i}.log").open("wb") as log:
                subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=1800,check=True)
        binary = build/"mw3-header-probe"
        report["binary_sha256"] = prep.sha(binary)
        if args.execute:
            for case in ("positive-0","positive-1","positive-2","bad-binding","bad-pointer","bad-oracle"):
                profile=output/case;profile.mkdir()
                (profile/"tmp").mkdir();(profile/"config").mkdir()
                filename="default.xex" if args.role=="sp" else "default_mp.xex"
                command=[str(binary),"--kernel.headless=true","--title.game_root="+str(owned),"--title.entry="+filename,
                         "--app.root="+str(profile/"app"),"--app.user_root="+str(profile/"user"),
                         "--ui.driver=none","--hid.drivers=none","--apu.driver=none","--gpu.driver=none"]
                env={k:v for k,v in os.environ.items() if not k.startswith(("REX_","LD_","MW3_HEADER_"))}
                env.update(MW3_HEADER_OWNED_FILE=str(owned/filename),TMPDIR=str(profile/"tmp"),XDG_CONFIG_HOME=str(profile/"config"),
                           SDL_VIDEODRIVER="dummy",SDL_AUDIODRIVER="dummy")
                if case=="bad-binding":env["MW3_HEADER_TEST_BAD_BINDING"]="1"
                if case=="bad-pointer":env["MW3_HEADER_TEST_BAD_POINTER"]="1"
                if case=="bad-oracle":env["MW3_HEADER_TEST_BAD_ORACLE"]="1"
                with (profile/"run.log").open("wb") as log:
                    result=subprocess.run(command,cwd=build,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=20)
                text=(profile/"run.log").read_text(errors="replace")
                events=[line for line in text.splitlines() if line.startswith("MW3_")]
                passed=(result.returncode==86 and text.count("MW3_HEADER_ORACLE_CASE_PASS:")==4
                        and "MW3_HEADER_QUERY_PASS:" in text and "MW3_MODULE_HEADER_AUDIT_PASS:" in text
                        and "MW3_PROBE_UNREVIEWED_IMPORT:" in text and "MW3_HEADER_GUARD_FAILED:" not in text) if case.startswith("positive") else (
                        result.returncode==87 and "MW3_HEADER_GUARD_FAILED:"+{
                            "bad-binding":"function binding verification", "bad-pointer":"unexpected header pointer",
                            "bad-oracle":"SDK header result differs from independent oracle"}[case] in text
                        and "MW3_HEADER_QUERY_PASS:" not in text)
                if any(error in text for error in ("ERROR: AddressSanitizer","runtime error:","UndefinedBehaviorSanitizer:")):
                    passed=False
                report["results"].append(dict(case=case,status="PASS" if passed else "FAIL",returncode=result.returncode,
                                              events=events,command=command,log_sha256=prep.sha(profile/"run.log")))
                report["guest_executed"] |= case.startswith("positive") and passed
                (output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
                print(json.dumps(dict(case=case,status="PASS" if passed else "FAIL",events=events)),flush=True)
        verify(owned,json.loads(DEFAULT.read_text()))
        prep.read_cache(entry,entry.name,generated["inputs"])
        report["status"]="PASS" if all(row["status"]=="PASS" for row in report["results"]) else "INCOMPLETE"
        (output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
        return int(report["status"]!="PASS")
    except (OSError,ValueError,KeyError,TypeError,StopIteration,subprocess.SubprocessError) as error:
        report.update(status="ERROR",error=str(error))
        if output and output.is_dir():(output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
        parser.exit(2,f"guarded runtime probe failed: {type(error).__name__}; private output={output}\n")


if __name__=="__main__":raise SystemExit(main())
