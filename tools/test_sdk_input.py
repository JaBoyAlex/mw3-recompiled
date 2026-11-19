#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Audit the real verified SDL3 input provider using private original virtual devices."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

import prepare_runtime_xma as xma
import recompile as common

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/host_platform/sdk_input"
CASES = ("four-devices", "state", "reconnect", "lifetime")
PREFIX = "MW3_INPUT_COMPLETE:"


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value: raise ValueError("duplicate result field")
        value[key] = item
    return value


def wrong_result(code, output):
    failures = [line for line in output.splitlines() if line.startswith("MW3_INPUT_FAILURE:")]
    return (code == 1 and failures == ["MW3_INPUT_FAILURE:deliberate wrong-result rejected"]
            and PREFIX not in output and not any(s in output for s in ("Sanitizer", "runtime error:")))


def classify(case, nonce, code, output):
    """Require the complete original-process protocol; no crash/partial/stale acceptance."""
    if case not in CASES or not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise ValueError("unknown input case or nonce")
    if code != 0 or any(s in output for s in ("Sanitizer", "runtime error:", "MW3_INPUT_FAILURE:")):
        return None
    records = [line[len(PREFIX):] for line in output.splitlines() if line.startswith(PREFIX)]
    if len(records) != 1:
        return None
    try:
        value = json.loads(records[0], object_pairs_hook=unique_object)
    except (ValueError, TypeError):
        return None
    cycles = 4 if case == "lifetime" else 1
    cleaned = 5 if case == "reconnect" else cycles * 4
    expected = dict(schema=1, case=case, nonce=nonce, cycles=cycles, devices=4,
                    cleaned=cleaned, pending=0, sdl_init_after=0, sdl_version=3004014)
    if not isinstance(value, dict) or set(value) != set(expected) | {"checks", "loaded"}:
        return None
    if any(type(value[k]) is not type(v) or value[k] != v for k, v in expected.items()):
        return None
    if type(value["checks"]) is not int or value["checks"] < 50:
        return None
    loaded = value["loaded"]
    if not isinstance(loaded, dict) or set(loaded) != {"provider", "sdl", "base"}:
        return None
    if any(not isinstance(p, str) or not p or "\n" in p or "\r" in p for p in loaded.values()):
        return None
    return value


def run_process(command, *, cwd, env, log, timeout):
    with Path(log).open("wb") as stream:
        try:
            return subprocess.run(command, cwd=cwd, env=env, stdout=stream,
                                  stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            return -999  # subprocess.run kills and waits only for its own child.


def loaded_identity(record, sdk, windows):
    folder = "bin" if windows else "lib"
    names = {"provider": "rexhid-sdl3", "sdl": "SDL3", "base": "rexbase"}
    result = {}
    for role, name in names.items():
        filename = name + ".dll" if windows else "lib" + name + ".so" + (".0" if role == "sdl" else "")
        expected = (sdk / folder / filename).resolve(strict=True)
        actual = Path(record["loaded"][role]).resolve(strict=True)
        if actual != expected:
            raise ValueError("unexpected loaded " + role + " library")
        result[role] = dict(path=str(actual), sha256=common.sha(actual))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "sdk-report", "output-root"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--sanitizers", action="store_true")
    parser.add_argument("--repeat", type=int, default=2, choices=range(1, 9))
    args = parser.parse_args()
    output = None
    report = dict(schema_version=1, status="IN_PROGRESS", game_free=True, guest_executed=False,
                  physical_devices=False, script_sha256=common.sha(__file__),
                  host_sanitizers=args.sanitizers, results=[])
    try:
        sdk, identity = xma.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        output = common.private_cache(args.output_root, ROOT / "game") / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        shutil.copytree(SOURCE, output / "maintained-source", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(__file__, output / "maintained-driver.py")
        host_sources = common.snapshot(output / "maintained-source")
        report.update(sdk=identity, host_sources=host_sources, repeat=args.repeat)
        windows = sys.platform == "win32"
        if windows:
            import prepare_windows_runtime as win
            lock = json.loads(win.LOCK.read_text())
            clang, report["compiler"] = win.compiler(args.root.resolve(), lock["compiler"], False)
            env, cmake, ninja, report["host_tools"] = win.msvc_environment(lock, clang)
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
        build = output / "build"
        configure = [cmake, "-S", output / "maintained-source", "-B", build, "-G", "Ninja",
                     "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_CXX_COMPILER=" + compiler.as_posix(),
                     "-DCMAKE_PREFIX_PATH=" + sdk.as_posix(), "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                     "-DMW3_INPUT_SANITIZERS=" + ("ON" if args.sanitizers else "OFF"), *extra]
        report["commands"] = []
        for label, command in (("configure", configure), ("build", [cmake, "--build", build, "--parallel", "2"])):
            report["commands"].append(list(map(str, command)))
            with (output / (label + ".log")).open("wb") as log:
                subprocess.run(list(map(str, command)), env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        binary = build / ("sdk-input-contracts.exe" if windows else "sdk-input-contracts")
        report["binary_sha256"] = common.sha(binary)
        report["compile_commands_sha256"] = common.sha(build / "compile_commands.json")
        provider = sdk / ("bin/rexhid-sdl3.dll" if windows else "lib/librexhid-sdl3.so")
        library_identity = None
        for repeat in range(args.repeat):
            order = CASES if repeat % 2 == 0 else tuple(reversed(CASES))
            for case in (*order, "wrong-result"):
                lane = output / f"{repeat}-{case}"
                for folder in ("tmp", "config", "data", "runtime"):
                    (lane / folder).mkdir(parents=True, exist_ok=True)
                child = {k: v for k, v in env.items() if not k.startswith(("REX_", "MW3_", "SDL_", "LD_", "ASAN_", "LSAN_", "UBSAN_"))}
                child.update(TMPDIR=str(lane / "tmp"), TMP=str(lane / "tmp"), TEMP=str(lane / "tmp"),
                             XDG_CONFIG_HOME=str(lane / "config"), XDG_DATA_HOME=str(lane / "data"),
                             XDG_RUNTIME_DIR=str(lane / "runtime"), SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                             ASAN_OPTIONS="detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
                if windows:
                    child["PATH"] = str(sdk / "bin") + os.pathsep + child.get("PATH", "")
                else:
                    child["LD_LIBRARY_PATH"] = str(sdk / "lib")
                nonce = uuid.uuid4().hex
                actual_case = "state" if case == "wrong-result" else case
                command = [str(binary), actual_case, nonce, str(provider)]
                if case == "wrong-result": command.append("--wrong-result")
                code = run_process(command, cwd=lane, env=child, log=lane / "run.log", timeout=30)
                text = (lane / "run.log").read_text(errors="replace")
                record = classify(actual_case, nonce, code, text)
                observed = None
                if case == "wrong-result":
                    passed = wrong_result(code, text)
                else:
                    passed = record is not None
                    if passed:
                        observed = loaded_identity(record, sdk, windows)
                        if library_identity is None: library_identity = observed
                        elif library_identity != observed: raise ValueError("loaded library identities changed between cases")
                row = dict(case=case, repeat=repeat, returncode=code, status="PASS" if passed else "FAIL",
                           command=command, log_sha256=common.sha(lane / "run.log"), record=record, loaded=observed)
                report["results"].append(row)
                print(json.dumps({key: row[key] for key in ("case", "repeat", "status", "returncode")}), flush=True)
        _, after = xma.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        if (after != identity or common.sha(binary) != report["binary_sha256"] or
                common.snapshot(output / "maintained-source") != host_sources or common.sha(__file__) != report["script_sha256"]):
            raise ValueError("verified source, SDK or binary changed")
        report["status"] = "PASS" if all(row["status"] == "PASS" for row in report["results"]) else "FAIL"
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return int(report["status"] != "PASS")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output: (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"Input diagnostic failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
