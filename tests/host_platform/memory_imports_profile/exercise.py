#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Exercise an explicitly verified repair with MW3-046's original real-kernel callbacks."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import prepare_runtime_memory_imports as profile
import recompile as common
from test_startup_memory import CASES, MUTATIONS, classify, mutation_rejected

SOURCE = ROOT / "tests/startup_memory"
CONTRACT_DRIVER = ROOT / "tools/test_startup_memory.py"


def output_directory(root, sdk, receipt, requested):
    output = common.private_cache(requested, ROOT / "game")
    protected = [sdk, receipt.parent, SOURCE, ROOT / "tools", ROOT / "config"]
    protected.extend(root / name for name in (
        "sources", "build", "install", "memory-preparations", "stop-preparations",
        "xma-preparations", "memory-imports-preparations"))
    if any(output.is_relative_to(path.resolve()) or path.resolve().is_relative_to(output)
           for path in protected):
        raise ValueError("exercise output overlaps maintained sources or SDK preparation")
    return output / uuid.uuid4().hex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "sdk-report", "output-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--sanitizers", action="store_true")
    parser.add_argument("--cases", nargs="+", choices=CASES, default=CASES)
    args = parser.parse_args()
    output = None
    report = dict(schema_version=1, status="IN_PROGRESS", game_free=True, translated_guest_executed=False,
                  script_sha256=common.sha(__file__), contract_driver_sha256=common.sha(CONTRACT_DRIVER), host_sanitizers=args.sanitizers, results=[])
    try:
        if len(set(args.cases)) != len(args.cases):
            raise ValueError("duplicate case selection")
        sdk, evidence = profile.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        output = output_directory(args.root.resolve(), sdk, args.sdk_report, args.output_root)
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        shutil.copytree(SOURCE, output / "maintained-source", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(__file__, output / "maintained-driver.py")
        sources = common.snapshot(output / "maintained-source")
        report.update(sdk=evidence, sdk_report_sha256=common.sha(args.sdk_report), host_sources=sources,
                      selected_cases=list(args.cases))
        windows = sys.platform == "win32"
        if windows:
            import prepare_windows_runtime as win
            lock = json.loads(win.LOCK.read_text())
            clang, report["compiler"] = win.compiler(args.root.resolve(), lock["compiler"], False)
            env, cmake, ninja, report["host_tools"] = win.msvc_environment(lock, clang)
            compiler = clang / "bin/clang++.exe"
            extra = ["-DCMAKE_MAKE_PROGRAM=" + ninja.as_posix(), "-DCMAKE_CXX_FLAGS=-march=x86-64-v2", "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld"]
            if args.sanitizers:
                report["calibration"] = win.calibrate_sanitizer(output, clang, env)
        else:
            env, cmake = dict(os.environ), "cmake"
            compiler = Path(shutil.which("clang++-20") or "missing")
            report["compiler"] = dict(sha256=common.sha(compiler), version=subprocess.check_output([compiler, "--version"], text=True).splitlines()[0])
            extra = ["-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13",
                     "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2"]
        build = output / "build"
        configure = [cmake, "-S", output / "maintained-source", "-B", build, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                     "-DCMAKE_CXX_COMPILER=" + compiler.as_posix(), "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG",
                     "-DCMAKE_PREFIX_PATH=" + sdk.as_posix(), "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                     "-DMW3_SDK_SOURCE=" + (args.root.resolve() / "sources/rexglue-xma").as_posix(),
                     "-DMW3_ALLOCATION_SANITIZERS=" + ("ON" if args.sanitizers else "OFF"), *extra]
        for label, command in (("configure", configure), ("build", [cmake, "--build", build, "--parallel", "2"])):
            report.setdefault("commands", []).append(list(map(str, command)))
            with (output / (label + ".log")).open("wb") as log:
                subprocess.run(list(map(str, command)), env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        binary = build / ("allocation-contracts.exe" if windows else "allocation-contracts")
        report.update(binary_sha256=common.sha(binary), compile_commands_sha256=common.sha(build / "compile_commands.json"))
        kernel = "bin/rexkernel.dll" if windows else "lib/librexkernel.so"
        for case in args.cases:
            nonce = uuid.uuid4().hex
            lane = output / case
            (lane / "tmp").mkdir(parents=True)
            (lane / "config").mkdir()
            child = {k: v for k, v in env.items() if not k.startswith(("REX_", "MW3_", "LD_", "ASAN_", "LSAN_", "UBSAN_"))}
            child.update(MW3_ALLOC_CASE=case, MW3_ALLOC_NONCE=nonce, TMPDIR=str(lane / "tmp"), TMP=str(lane / "tmp"), TEMP=str(lane / "tmp"),
                         XDG_CONFIG_HOME=str(lane / "config"), SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                         ASAN_OPTIONS="detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
            if not windows:
                symbolizer = shutil.which("llvm-symbolizer-20") or shutil.which("llvm-symbolizer-19")
                if symbolizer:
                    child["ASAN_SYMBOLIZER_PATH"] = symbolizer
                    child["UBSAN_OPTIONS"] += ":external_symbolizer_path=" + symbolizer
                    report["symbolizer"] = dict(path=symbolizer, sha256=common.sha(symbolizer))
            if windows:
                child["PATH"] = str(sdk / "bin") + os.pathsep + child.get("PATH", "")
            else:
                child["LD_LIBRARY_PATH"] = str(sdk / "lib")
            command = [str(binary), "--kernel.headless=true", "--title.game_root=" + str(lane),
                       "--app.root=" + str(lane / "app"), "--app.user_root=" + str(lane / "user"),
                       "--ui.driver=none", "--hid.drivers=none", "--apu.driver=none", "--gpu.driver=none"]
            with (lane / "run.log").open("wb") as log:
                try:
                    code = subprocess.run(command, env=child, cwd=lane, stdout=log, stderr=subprocess.STDOUT,
                                          timeout=5 if case == "mutation-late" else 30).returncode
                except subprocess.TimeoutExpired:
                    code = -999
            text = (lane / "run.log").read_text(errors="replace")
            loaded = re.findall(r"module 'rexkernel' loaded from '([^']+)'", text)
            actual = common.sha(Path(loaded[0])) if len(loaded) == 1 else None
            identity_ok = actual == evidence["sdk_files"][kernel]["sha256"]
            accepted = mutation_rejected(case, code, text, nonce) if case in MUTATIONS else classify(case, code, text, nonce)
            row = dict(case=case, nonce=nonce, returncode=code, status="PASS" if identity_ok and accepted else "FAIL",
                       command=command, log_sha256=common.sha(lane / "run.log"), loaded_kernel_sha256=actual,
                       loaded_kernel_paths=loaded, events=[line for line in text.splitlines() if line.startswith("MW3_")])
            report["results"].append(row)
            print(json.dumps({k: row[k] for k in ("case", "status", "returncode")}), flush=True)
        _, after = profile.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        if (after != evidence or common.sha(binary) != report["binary_sha256"]
                or common.sha(args.sdk_report) != report["sdk_report_sha256"]
                or common.snapshot(output / "maintained-source") != sources
                or common.sha(__file__) != report["script_sha256"]
                or common.sha(CONTRACT_DRIVER) != report["contract_driver_sha256"]):
            raise ValueError("SDK, source or executed artifact changed")
        report["status"] = "PASS" if all(row["status"] == "PASS" for row in report["results"]) else "FAIL"
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return int(report["status"] != "PASS")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output:
            (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"allocation import test failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
