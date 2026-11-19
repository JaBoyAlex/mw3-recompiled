#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Exercise actual SDK audio-pool teardown using a game-free empty title."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

import prepare_runtime_stop as stop
import prepare_runtime_xma as xma
import recompile as common

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/xma"
CASES = ("unloaded", "loaded", "launch-failure", "repeat")


def classify(case, code, text):
    if case not in CASES:
        raise ValueError("unknown XMA case")
    if code != 0 or any(n in text for n in ("Sanitizer", "runtime error:", "MW3_XMA_FAILURE:", "the APU failed to start")):
        return False
    cycles = 4 if case == "repeat" else 1
    matches = re.findall(r"^MW3_XMA_COMPLETE:case=(\S+) cycles=(\d+) threads_before=(\d+) threads_after=(\d+)$", text, re.MULTILINE)
    pools = re.findall(r"^MW3_XMA_POOL_DESTROYED:cycle=(\d+)$", text, re.MULTILINE)
    expected = list(map(str, range(cycles))) if case in ("repeat", "launch-failure") else []
    return (len(matches) == 1 and matches[0][:2] == (case, str(cycles))
            and matches[0][2] == matches[0][3] and pools == expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "sdk-report", "output-root"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--sdk-profile", choices=("stop", "xma"), required=True)
    parser.add_argument("--sanitizers", action="store_true")
    args = parser.parse_args()
    output = None
    verifier = xma if args.sdk_profile == "xma" else stop
    report = dict(schema_version=1, status="IN_PROGRESS", game_free=True, guest_executed=False,
                  script_sha256=common.sha(__file__), sdk_profile=args.sdk_profile,
                  host_sanitizers=args.sanitizers, results=[])
    try:
        sdk, evidence = verifier.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        output = common.private_cache(args.output_root, ROOT / "game") / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        shutil.copytree(SOURCE, output / "maintained-source", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(__file__, output / "maintained-driver.py")
        host_sources = common.snapshot(output / "maintained-source")
        report.update(sdk=evidence, host_sources=host_sources)
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
            env = dict(os.environ)
            cmake = "cmake"
            compiler = Path(shutil.which("clang++-20") or "missing")
            report["compiler"] = dict(sha256=common.sha(compiler), version=subprocess.check_output([compiler, "--version"], text=True).splitlines()[0])
            extra = ["-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13",
                     "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2"]
        build = output / "build"
        command = [cmake, "-S", output / "maintained-source", "-B", build, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                   "-DCMAKE_CXX_COMPILER=" + compiler.as_posix(), "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG",
                   "-DCMAKE_PREFIX_PATH=" + sdk.as_posix(), "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                   "-DMW3_XMA_SANITIZERS=" + ("ON" if args.sanitizers else "OFF"), *extra]
        for label, cmd in (("configure", command), ("build", [cmake, "--build", build, "--parallel", "2"])):
            report.setdefault("commands", []).append(list(map(str, cmd)))
            with (output / (label + ".log")).open("wb") as log:
                subprocess.run(list(map(str, cmd)), env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        binary = build / ("xma-lifecycle.exe" if windows else "xma-lifecycle")
        report["binary_sha256"] = common.sha(binary)
        for case in CASES:
            lane = output / case
            (lane / "tmp").mkdir(parents=True)
            (lane / "config").mkdir()
            child = {k: v for k, v in env.items() if not k.startswith(("REX_", "MW3_", "LD_", "ASAN_", "LSAN_", "UBSAN_"))}
            child.update(MW3_XMA_CASE=case, TMPDIR=str(lane / "tmp"), TMP=str(lane / "tmp"), TEMP=str(lane / "tmp"),
                         XDG_CONFIG_HOME=str(lane / "config"), SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                         ASAN_OPTIONS="detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
            if windows:
                child["PATH"] = str(sdk / "bin") + os.pathsep + child.get("PATH", "")
            else:
                child["LD_LIBRARY_PATH"] = str(sdk / "lib")
            cmd = [str(binary), "--kernel.headless=true", "--title.game_root=" + str(lane),
                   "--app.root=" + str(lane / "app"), "--app.user_root=" + str(lane / "user"),
                   "--ui.driver=none", "--hid.drivers=none", "--apu.driver=none", "--gpu.driver=none"]
            with (lane / "run.log").open("wb") as log:
                try:
                    code = subprocess.run(cmd, env=child, cwd=lane, stdout=log, stderr=subprocess.STDOUT, timeout=45).returncode
                except subprocess.TimeoutExpired:
                    code = -999
            text = (lane / "run.log").read_text(errors="replace")
            row = dict(case=case, returncode=code, status="PASS" if classify(case, code, text) else "FAIL",
                       command=cmd, log_sha256=common.sha(lane / "run.log"), events=[l for l in text.splitlines() if l.startswith("MW3_")])
            report["results"].append(row)
            print(json.dumps({k: row[k] for k in ("case", "status", "returncode")}), flush=True)
        _, after = verifier.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        if (after != evidence or common.sha(binary) != report["binary_sha256"]
                or common.snapshot(output / "maintained-source") != host_sources
                or common.sha(__file__) != report["script_sha256"]):
            raise ValueError("verified source, SDK or binary changed")
        report["status"] = "PASS" if all(r["status"] == "PASS" for r in report["results"]) else "FAIL"
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return int(report["status"] != "PASS")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output:
            (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"XMA test failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
