#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Audit actual selected-kernel memory imports using original game-free callbacks."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

import prepare_runtime_xma as profile
import recompile as common

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/startup_memory"
POSITIVE = ("basic", "lifecycle", "negative-small", "physical-alias", "double-release", "repeat")
POINTERS = tuple(f"{api}-{kind}-{word}" for api in ("alloc", "free")
                 for kind in ("null", "unaligned", "outside", "wrapping", "readonly") for word in ("base", "size"))
REJECTIONS = ("alloc-zero-size", "alloc-type", "alloc-protection", "alloc-region", "alloc-alias",
              "free-type", "free-region", "free-unallocated", "free-alias", "alloc-alias-physical", "free-alias-physical")
MUTATIONS = ("mutation-result", "mutation-incomplete", "mutation-late")
CASES = (*POSITIVE, "negative-intmin", *POINTERS, *REJECTIONS, *MUTATIONS)
DIAGNOSTICS = ("Sanitizer", "runtime error:", "crash report", "exception:")


def steps(case):
    if case == "repeat":
        forward = ["basic", "lifecycle", "negative-small", "double-release"]
        return forward + list(reversed(forward)) + forward
    return [case]


def calls_match(case, calls):
    alloc, free = "NtAllocateVirtualMemory", "NtFreeVirtualMemory"
    if case.startswith(("alloc-", "free-")):
        if case.startswith("free-") and case != "free-unallocated":
            return (len(calls) == 3 and calls[0] == (alloc, "00000000") and calls[1][0] == free
                    and calls[1][1] != "00000000" and calls[2] == (free, "00000000"))
        return len(calls) == 1 and calls[0][0] == (free if case.startswith("free-") else alloc) and calls[0][1] != "00000000"
    if case == "negative-intmin":
        return ((len(calls) == 1 and calls[0][0] == alloc and calls[0][1] != "00000000")
                or calls == [(alloc, "00000000"), (free, "00000000")])
    expected = [alloc, alloc, free, alloc, free] if case == "lifecycle" else [alloc, free]
    if case == "double-release":
        return (len(calls) == 3 and calls[:2] == [(alloc, "00000000"), (free, "00000000")]
                and calls[2][0] == free and calls[2][1] != "00000000")
    return calls == [(name, "00000000") for name in expected]


def classify(case, code, text, nonce):
    if case not in CASES or case in MUTATIONS:
        raise ValueError("unknown allocation case")
    if code != 0 or any(word in text for word in (*DIAGNOSTICS, "MW3_ALLOC_FAILURE:")):
        return False
    if not re.fullmatch(r"[a-f0-9]{32}", nonce):
        return False
    rows = re.findall(r"^MW3_ALLOC_COMPLETE:case=(\S+) result=(\d+) verified=(\d+) threads_before=(\d+) threads_after=(\d+) nonce=([a-f0-9]{32})$", text, re.MULTILINE)
    verified = re.findall(r"^MW3_ALLOC_VERIFIED:case=(\S+)$", text, re.MULTILINE)
    armed = re.findall(r"^MW3_ALLOC_ARMED:case=(\S+) nonce=([a-f0-9]{32})$", text, re.MULTILINE)
    if (len(rows) != 1 or rows[0][:3] != (case, "0", str(len(steps(case)))) or rows[0][3] != rows[0][4]
            or rows[0][5] != nonce or armed != [(case, nonce)] or verified != steps(case) or "MW3_ALLOC_MUTATION:" in text):
        return False
    # Every call must return in order before its verified marker; no unmatched/late events pass.
    events = [line for line in text.splitlines() if line.startswith("MW3_ALLOC_")]
    if events[0] != f"MW3_ALLOC_ARMED:case={case} nonce={nonce}" or not events[-1].startswith("MW3_ALLOC_COMPLETE:"):
        return False
    at = 1
    for step in steps(case):
        calls = []
        while at < len(events) and events[at].startswith("MW3_ALLOC_CALL:"):
            name = events[at].split(":", 1)[1]
            at += 1
            if at >= len(events):
                return False
            returned = re.fullmatch(r"MW3_ALLOC_RETURN:(\w+) status=([a-f0-9]{8})", events[at])
            if not returned or returned[1] != name:
                return False
            calls.append(returned.groups())
            at += 1
        if not calls_match(step, calls) or at >= len(events) or events[at] != f"MW3_ALLOC_VERIFIED:case={step}":
            return False
        at += 1
    return at == len(events) - 1


def mutation_rejected(case, code, text, nonce):
    if case not in MUTATIONS:
        raise ValueError("unknown mutation")
    if not re.fullmatch(r"[a-f0-9]{32}", nonce) or any(word in text for word in DIAGNOSTICS):
        return False
    events = [line for line in text.splitlines() if line.startswith("MW3_ALLOC_")]
    expected = [f"MW3_ALLOC_ARMED:case={case} nonce={nonce}",
                "MW3_ALLOC_CALL:NtAllocateVirtualMemory",
                "MW3_ALLOC_RETURN:NtAllocateVirtualMemory status=00000000",
                "MW3_ALLOC_CALL:NtFreeVirtualMemory",
                "MW3_ALLOC_RETURN:NtFreeVirtualMemory status=00000000",
                "MW3_ALLOC_VERIFIED:case=basic", f"MW3_ALLOC_MUTATION:{case}"]
    if case == "mutation-result":
        if len(events) != len(expected) + 2:
            return False
        footer = re.fullmatch(r"MW3_ALLOC_COMPLETE:case=mutation-result result=2 verified=1 threads_before=(\d+) threads_after=(\d+) nonce=" + nonce, events[-1])
        return (code == 2 and events[:-2] == expected
                and events[-2] == "MW3_ALLOC_FAILURE:intentional wrong result"
                and footer is not None and footer[1] == footer[2])
    return code == (-999 if case == "mutation-late" else 0) and events == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "sdk-report", "output-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--sanitizers", action="store_true")
    parser.add_argument("--cases", nargs="+", choices=CASES, default=CASES)
    args = parser.parse_args()
    output = None
    report = dict(schema_version=1, status="IN_PROGRESS", game_free=True, translated_guest_executed=False,
                  script_sha256=common.sha(__file__), host_sanitizers=args.sanitizers, results=[])
    try:
        if len(set(args.cases)) != len(args.cases):
            raise ValueError("duplicate case selection")
        sdk, evidence = profile.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        output = common.private_cache(args.output_root, ROOT / "game") / uuid.uuid4().hex
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
                or common.sha(__file__) != report["script_sha256"]):
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
