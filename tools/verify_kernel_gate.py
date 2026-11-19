#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build and verify a bounded owned-title lifecycle checkpoint."""
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
import prepare_runtime_stop as stop
import runtime_probe as audit

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "runtime/lifecycle"
CASES = ("positive-0", "positive-1", "positive-2", "bad-binding", "bad-pointer", "bad-oracle", "interrupt")


def classify(case, code, text):
    if case not in CASES:
        raise ValueError("unknown lifecycle case")
    if any(marker in text for marker in ("AddressSanitizer", "LeakSanitizer", "runtime error:", "UndefinedBehaviorSanitizer")):
        return False
    expected = 86 if case.startswith("positive") else 88 if case == "interrupt" else 87
    if code != expected or text.count(f"MW3_LIFECYCLE_COMPLETE:exit={expected}") != 1:
        return False
    if text.count("MW3_LIFECYCLE_UNLOADED:reservation_released=1") != 1:
        return False
    if text.count("MW3_LIFECYCLE_MAPPING_RELEASED:bytes=4831838208") != 1:
        return False
    counts = re.findall(r"MW3_LIFECYCLE_SHUTDOWN:result=0 threads_before=(\d+) threads_after=(\d+)", text)
    if len(counts) != 1 or counts[0][0] != counts[0][1]:
        return False
    if case.startswith("positive"):
        return (text.count("MW3_HEADER_ORACLE_CASE_PASS:") == 4
                and text.count("MW3_HEADER_QUERY_PASS:") == 1
                and text.count("MW3_PROBE_UNREVIEWED_IMPORT:NtAllocateVirtualMemory ") == 1
                and "MW3_LIFECYCLE_REJECT:" not in text
                and text.count("MW3_LIFECYCLE_THREAD_STOPPED:exit=86 queries=1") == 1)
    if case == "interrupt":
        return (text.count("MW3_HEADER_QUERY_PASS:") == 1
                and text.count("MW3_LIFECYCLE_INTERRUPT_REQUESTED:exit=88") == 1
                and text.count("MW3_LIFECYCLE_THREAD_STOPPED:exit=88 queries=1") == 1
                and "MW3_PROBE_UNREVIEWED_IMPORT:" not in text and "MW3_LIFECYCLE_REJECT:" not in text)
    reason = {"bad-binding": "function binding verification", "bad-pointer": "unexpected header pointer",
              "bad-oracle": "SDK header result differs from independent oracle"}[case]
    rejects = re.findall(r"^MW3_LIFECYCLE_REJECT:(.*)$", text, re.MULTILINE)
    metadata_checked = case == "bad-binding" or text.count("MW3_LIFECYCLE_THREAD_STOPPED:exit=87 queries=1") == 1
    return rejects == [reason] and metadata_checked and "MW3_HEADER_QUERY_PASS:" not in text


def controlled_traps(metadata, prefix, expected_count):
    source, address = audit.guarded_traps(metadata, prefix, expected_count)
    expression = re.compile(
        r'extern "C" void __imp__(\w+)\(PPCContext& ctx, u8\*\) \{ [^\n]+std::_Exit\(86\); \}')
    changed = []

    def replace(match):
        name = match.group(1)
        changed.append(name)
        return f'extern "C" void __imp__{name}(PPCContext& ctx, u8*) {{ StopUnreviewedImport("{name}",ctx); }}'

    source = expression.sub(replace, source)
    if len(changed) != expected_count - 1 or "std::_Exit" in source:
        raise ValueError("unrecognized audited import-stop template")
    declaration = 'extern "C" [[noreturn]] void StopUnreviewedImport(const char*,PPCContext&);\n'
    first, remainder = source.split("\n", 1)
    return first + "\n" + declaration + remainder, address


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "sdk-report", "owned", "metadata", "output-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--role", choices=("sp", "mp"), required=True)
    parser.add_argument("--generation", type=Path, help="immutable generation receipt, required on Windows")
    parser.add_argument("--expected-generation-sha256")
    parser.add_argument("--sanitizers", action="store_true")
    args = parser.parse_args()
    output = None
    report = dict(schema_version=1, status="IN_PROGRESS", playable=False, guest_executed=False,
                  script_sha256=common.sha(__file__), role=args.role, results=[],
                  host_sources=common.snapshot(HOST), host_sanitizers=args.sanitizers)
    report["supporting_sources"] = {str(path.relative_to(ROOT)): common.sha(path) for path in (
        ROOT / "src/xex.cpp", ROOT / "include/mw3/xex.hpp", Path(common.__file__), Path(stop.__file__),
        Path(audit.__file__), ROOT / "experiments/runtime-bakeoff/rexglue_probe.py",
        ROOT / "runtime/bringup/analysis-lock.json", common.DEFAULT, common.RECIPE)}
    try:
        for task in ("036", "037", "038", "039", "040", "042", "043"):
            if json.loads((ROOT / f"tasks/MW3-{task}.json").read_text())["status"] != "done":
                raise ValueError(f"unfinished child MW3-{task}")
        owned = args.owned.resolve()
        identity = common.verify(owned, json.loads(common.DEFAULT.read_text()))
        output = common.private_cache(args.output_root, owned) / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        shutil.copytree(HOST, output / "maintained-host")
        shutil.copy2(__file__, output / "maintained-driver.py")
        sdk, evidence = stop.verify_prepared(args.root.resolve(), args.sdk_report)
        report.update(identity=identity, sdk=evidence, sdk_report_sha256=common.sha(args.sdk_report))
        recipe = common.validate_recipe(json.loads(common.RECIPE.read_text()))
        windows = sys.platform == "win32"
        if args.generation:
            if not args.expected_generation_sha256 or common.sha(args.generation) != args.expected_generation_sha256:
                raise ValueError("generation receipt differs from explicit binding")
            generation = json.loads(args.generation.read_text())
            payload = args.generation.parent / "payload"
            if (generation.get("status") != "GENERATED" or generation["identity"] != identity
                    or generation["recipe"] != recipe or generation["files"] != common.snapshot(payload)
                    or generation["recipe_sha256"] != common.sha(common.RECIPE)
                    or generation["driver_sha256"] != common.sha(common.__file__)
                    or generation["sdk"]["stop_lock_sha256"] != common.sha(stop.LOCK)):
                raise ValueError("generation payload or identity changed")
        else:
            if windows:
                raise ValueError("Windows requires a verified independent generation receipt")
            common.generate(output, sdk, owned, recipe)
            payload = output / "payload"
            generation = dict(schema_version=1, status="GENERATED", identity=identity, recipe=recipe,
                              recipe_sha256=common.sha(common.RECIPE),
                              driver_sha256=common.sha(common.__file__), sdk=evidence,
                              generator_sha256=common.sha(sdk / "bin/rexglue"), files=common.snapshot(payload))
            (output / "generation.json").write_text(json.dumps(generation, indent=2) + "\n")
        report["generation"] = generation
        metadata = args.metadata / (args.role + "-image.json")
        analysis = json.loads((ROOT / "runtime/bringup/analysis-lock.json").read_text())
        if common.sha(metadata) != analysis[args.role]["metadata_sha256"]:
            raise ValueError("unreviewed analysis metadata")
        prefix = "mw3_" + args.role
        traps, address = controlled_traps(json.loads(metadata.read_text()), prefix, analysis[args.role]["function_imports"])
        (output / "traps.cpp").write_text(traps)
        (output / "data-import.h").write_text(f"#pragma once\n#define MW3_MODULE_HANDLE_IMPORT {hex(address)}u\n")
        report.update(metadata_sha256=common.sha(metadata), traps_sha256=common.sha(output / "traps.cpp"),
                      data_import_sha256=common.sha(output / "data-import.h"))
        if windows:
            import prepare_windows_runtime as win
            lock = json.loads(win.LOCK.read_text())
            clang, report["compiler"] = win.compiler(args.root.resolve(), lock["compiler"], False)
            env, cmake, ninja, report["host"] = win.msvc_environment(lock, clang)
            compiler = clang / "bin/clang++.exe"
            extra = ["-DCMAKE_MAKE_PROGRAM=" + ninja.as_posix(), "-DCMAKE_CXX_FLAGS=-march=x86-64-v2",
                     "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld"]
            if args.sanitizers:
                report["calibration"] = win.calibrate_sanitizer(output, clang, env)
        else:
            env = dict(os.environ)
            cmake = "cmake"
            compiler = Path(shutil.which("clang++-20") or "missing")
            report["compiler"] = dict(sha256=common.sha(compiler), version=subprocess.check_output([compiler, "--version"], text=True).splitlines()[0])
            extra = ["-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13",
                     "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2"]
        cache = common.private_cache(output.parent / "build-cache", owned)
        cache.mkdir(exist_ok=True)
        build_key = common.digest(dict(sdk=evidence, generation=generation["files"], role=args.role,
                                       compiler=report["compiler"], cmake_sha256=common.sha(HOST / "CMakeLists.txt")))
        build = cache / build_key
        configure = [cmake, "-S", HOST, "-B", build, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                     "-DCMAKE_CXX_COMPILER=" + compiler.as_posix(), "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG",
                     "-DCMAKE_PREFIX_PATH=" + sdk.as_posix(), "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                     "-DMW3_GENERATED_DIR=" + (payload / args.role / "generated").as_posix(),
                     "-DMW3_GENERATED_PREFIX=" + prefix, "-DMW3_PRIVATE_TRAPS=" + (output / "traps.cpp").as_posix(),
                     "-DMW3_DATA_IMPORT_HEADER=" + (output / "data-import.h").as_posix(),
                     "-DMW3_LIFECYCLE_SANITIZERS=" + ("ON" if args.sanitizers else "OFF"), *extra]
        execution = output / "execution"
        execution.mkdir()
        with common.writer_lock(cache, build_key):
            for label, command in (("configure", configure), ("build", [cmake, "--build", build, "--parallel", "2"])):
                report.setdefault("commands", []).append(list(map(str, command)))
                print(json.dumps(dict(stage=label)), flush=True)
                with (output / (label + ".log")).open("wb") as log:
                    subprocess.run(list(map(str, command)), env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1800)
            name = "mw3-lifecycle.exe" if windows else "mw3-lifecycle"
            shutil.copy2(build / name, execution / name)
            if windows:
                for library in build.glob("*.dll"):
                    shutil.copy2(library, execution / library.name)
            shutil.copy2(build / "compile_commands.json", output / "compile_commands.json")
        binary = execution / name
        report.update(execution_files=common.snapshot(execution), build_key=build_key,
                      compile_commands_sha256=common.sha(output / "compile_commands.json"))
        report["binary_sha256"] = common.sha(binary)
        for case in CASES:
            lane = output / case
            (lane / "tmp").mkdir(parents=True)
            (lane / "config").mkdir()
            name = "default.xex" if args.role == "sp" else "default_mp.xex"
            command = [str(binary), "--kernel.headless=true", "--title.game_root=" + str(owned), "--title.entry=" + name,
                       "--app.root=" + str(lane / "app"), "--app.user_root=" + str(lane / "user"),
                       "--ui.driver=none", "--hid.drivers=none", "--apu.driver=none", "--gpu.driver=none"]
            child = {k: v for k, v in env.items() if not k.startswith(("REX_", "MW3_", "LD_", "ASAN_", "UBSAN_", "LSAN_"))}
            child.update(MW3_HEADER_OWNED_FILE=str(owned / name), MW3_LIFECYCLE_CASE="positive" if case.startswith("positive") else case,
                         TMPDIR=str(lane / "tmp"), TMP=str(lane / "tmp"), TEMP=str(lane / "tmp"),
                         XDG_CONFIG_HOME=str(lane / "config"), SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                         ASAN_OPTIONS="detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
            if case == "bad-binding":
                child["MW3_HEADER_TEST_BAD_BINDING"] = "1"
            if windows:
                child["PATH"] = str(sdk / "bin") + os.pathsep + child.get("PATH", "")
            else:
                child["LD_LIBRARY_PATH"] = str(sdk / "lib")
            with (lane / "run.log").open("wb") as log:
                try:
                    code = subprocess.run(command, cwd=execution, env=child, stdout=log, stderr=subprocess.STDOUT, timeout=30).returncode
                except subprocess.TimeoutExpired:
                    code = -999
            text = (lane / "run.log").read_text(errors="replace")
            row = dict(case=case, status="PASS" if classify(case, code, text) else "FAIL", returncode=code,
                       command=command, log_sha256=common.sha(lane / "run.log"),
                       events=[line for line in text.splitlines() if line.startswith("MW3_")])
            report["results"].append(row)
            print(json.dumps({key: row[key] for key in ("case", "status", "returncode")}), flush=True)
            (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        _, after = stop.verify_prepared(args.root.resolve(), args.sdk_report)
        if after != evidence or common.sha(binary) != report["binary_sha256"]:
            raise ValueError("SDK or executed binary changed")
        if common.snapshot(execution) != report["execution_files"]:
            raise ValueError("executed package changed")
        if common.snapshot(HOST) != report["host_sources"] or common.sha(__file__) != report["script_sha256"]:
            raise ValueError("maintained lifecycle source changed during verification")
        if any(common.sha(ROOT / path) != digest for path, digest in report["supporting_sources"].items()):
            raise ValueError("supporting source changed during verification")
        common.verify(owned, json.loads(common.DEFAULT.read_text()))
        if common.snapshot(payload) != generation["files"]:
            raise ValueError("generated payload changed")
        report["status"] = "PASS" if all(row["status"] == "PASS" for row in report["results"]) else "FAIL"
        report["guest_executed"] = any(row["case"].startswith("positive") and row["status"] == "PASS" for row in report["results"])
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return int(report["status"] != "PASS")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output:
            (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"lifecycle verification failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
