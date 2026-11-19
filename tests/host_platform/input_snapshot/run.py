#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Exercise undiscovered provider-handle teardown in a private verified SDK."""
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
import prepare_runtime_input as profile
import test_sdk_input as raw

SOURCE = Path(__file__).resolve().parent
CASES = ("pending-live", "pending-removed")
PREFIX = "MW3_SNAPSHOT_COMPLETE:"


def classify(case, nonce, code, text):
    if case not in CASES or not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise ValueError("invalid lifecycle case or nonce")
    lines = [line[len(PREFIX):] for line in text.splitlines() if line.startswith(PREFIX)]
    if code != 0 or len(lines) != 1 or any(s in text for s in ("Sanitizer", "runtime error:", "FAILURE:")):
        return None
    try:
        value = json.loads(lines[0], object_pairs_hook=raw.unique_object)
        expected = dict(schema=1, case=case, nonce=nonce, created=5, cleaned=5, pending=0, sdl_init_after=0)
        if not isinstance(value, dict) or set(value) != set(expected) | {"checks", "loaded"}:
            return None
        if any(type(value[k]) is not type(v) or value[k] != v for k, v in expected.items()):
            return None
        if type(value["checks"]) is not int or value["checks"] < 50:
            return None
        if set(value["loaded"]) != {"provider", "sdl", "base"}:
            return None
        if any(not isinstance(p, str) or not p or "\n" in p or "\r" in p for p in value["loaded"].values()):
            return None
        return value
    except (ValueError, TypeError, KeyError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "sdk-report", "output-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--sanitizers", action="store_true")
    args = parser.parse_args()
    output = None
    report = dict(status="IN_PROGRESS", game_free=True, guest_executed=False, physical_devices=False,
                  script_sha256=raw.common.sha(__file__), host_sanitizers=args.sanitizers, results=[])
    try:
        sdk, identity = profile.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        output = raw.common.private_cache(args.output_root, ROOT / "game") / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        source = output / "maintained-source"
        source.mkdir()
        for name in ("contracts.cpp", "CMakeLists.txt"):
            shutil.copy2(SOURCE / name, source / name)
        shutil.copy2(ROOT / "tests/host_platform/sdk_input/contracts.cpp", source / "baseline-contracts.cpp")
        shutil.copy2(__file__, output / "maintained-driver.py")
        report.update(sdk=identity, host_sources=raw.common.snapshot(source))
        windows = sys.platform == "win32"
        if windows:
            import prepare_windows_runtime as win
            lock = json.loads(win.LOCK.read_text())
            clang, report["compiler"] = win.compiler(args.root.resolve(), lock["compiler"], False)
            env, cmake, ninja, report["host_tools"] = win.msvc_environment(lock, clang)
            compiler = clang / "bin/clang++.exe"
            extra = ["-DCMAKE_MAKE_PROGRAM=" + ninja.as_posix(), "-DCMAKE_CXX_FLAGS=-march=x86-64-v2", "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld"]
            if args.sanitizers: report["calibration"] = win.calibrate_sanitizer(output, clang, env)
        else:
            env, cmake = dict(os.environ), "cmake"
            compiler = Path(shutil.which("clang++-20") or "missing")
            report["compiler"] = dict(sha256=raw.common.sha(compiler), version=subprocess.check_output([compiler, "--version"], text=True).splitlines()[0])
            extra = ["-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13", "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2"]
        build = output / "build"
        commands = [("configure", [cmake, "-S", source, "-B", build, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                     "-DCMAKE_CXX_COMPILER=" + compiler.as_posix(), "-DCMAKE_PREFIX_PATH=" + sdk.as_posix(),
                     "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON", "-DMW3_INPUT_SANITIZERS=" + ("ON" if args.sanitizers else "OFF"), *extra]),
                    ("build", [cmake, "--build", build, "--parallel", "2"])]
        report["commands"] = []
        for label, cmd in commands:
            report["commands"].append(list(map(str, cmd)))
            with (output / (label + ".log")).open("wb") as log:
                subprocess.run(list(map(str, cmd)), env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        binary = build / ("input-snapshot-contracts.exe" if windows else "input-snapshot-contracts")
        report.update(binary_sha256=raw.common.sha(binary), compile_commands_sha256=raw.common.sha(build / "compile_commands.json"))
        for repeat in range(2):
            for case in CASES if repeat == 0 else reversed(CASES):
                lane = output / f"{repeat}-{case}"
                for folder in ("tmp", "config", "data", "runtime"): (lane / folder).mkdir(parents=True, exist_ok=True)
                child = {k: v for k, v in env.items() if not k.startswith(("REX_", "MW3_", "SDL_", "LD_", "ASAN_", "LSAN_", "UBSAN_"))}
                child.update(TMPDIR=str(lane / "tmp"), TMP=str(lane / "tmp"), TEMP=str(lane / "tmp"), XDG_CONFIG_HOME=str(lane / "config"),
                             XDG_DATA_HOME=str(lane / "data"), XDG_RUNTIME_DIR=str(lane / "runtime"), SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                             ASAN_OPTIONS="detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
                if windows: child["PATH"] = str(sdk / "bin") + os.pathsep + child.get("PATH", "")
                else: child["LD_LIBRARY_PATH"] = str(sdk / "lib")
                nonce = uuid.uuid4().hex
                cmd = [str(binary), case, nonce, str(sdk / ("bin/rexhid-sdl3.dll" if windows else "lib/librexhid-sdl3.so"))]
                code = raw.run_process(cmd, cwd=lane, env=child, log=lane / "run.log", timeout=30)
                record = classify(case, nonce, code, (lane / "run.log").read_text(errors="replace"))
                loaded = raw.loaded_identity(record, sdk, windows) if record else None
                row = dict(case=case, repeat=repeat, returncode=code, status="PASS" if record else "FAIL", command=cmd,
                           record=record, loaded=loaded, log_sha256=raw.common.sha(lane / "run.log"))
                report["results"].append(row)
                print(json.dumps(dict(case=case, status=row["status"])), flush=True)
        _, after = profile.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        if after != identity or raw.common.snapshot(source) != report["host_sources"] or raw.common.sha(binary) != report["binary_sha256"] or raw.common.sha(__file__) != report["script_sha256"]:
            raise ValueError("SDK, source, binary or runner changed")
        report["status"] = "PASS" if all(r["status"] == "PASS" for r in report["results"]) else "FAIL"
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return int(report["status"] != "PASS")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output: (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"Lifecycle diagnostic failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
