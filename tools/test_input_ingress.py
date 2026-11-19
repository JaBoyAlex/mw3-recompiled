#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Exercise explicit local-owner ingress through a verified real SDL3 provider."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

import prepare_runtime_input as input_profile
import recompile as common
import test_sdk_input as raw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/host_platform/input_ingress"
CASES = ("held", "orders", "hotplug", "restart", "rejections", "control-map")
PREFIX = "MW3_INGRESS_COMPLETE:"
REJECTED = "MW3_INGRESS_REJECTED:"
LOADED = "MW3_INGRESS_LOADED:"
run_process = raw.run_process
loaded_identity = raw.loaded_identity


def inputs():
    result = {"CMakeLists.txt": SOURCE / "SDK-CMakeLists.txt",
              "sdk_contracts.cpp": SOURCE / "sdk_contracts.cpp",
              "baseline-contracts.cpp": ROOT / "tests/host_platform/sdk_input/contracts.cpp"}
    for name in ("input/slot_router.hpp", "input/slot_router.cpp", "input/ingress/ingress.hpp", "input/ingress/ingress.cpp"):
        result["runtime/" + name] = ROOT / "runtime" / name
    return result


def output_root(root, receipt, sdk, destination):
    destination = common.private_cache(destination, ROOT / "game")
    protected = (sdk.resolve(), receipt.resolve().parent, root.resolve() / "sources")
    if any(destination == p or destination.is_relative_to(p) or p.is_relative_to(destination) for p in protected):
        raise ValueError("diagnostic output overlaps SDK preparation/source input")
    return destination


def one(prefix, text):
    lines = [line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)]
    if len(lines) != 1: return None
    try: return json.loads(lines[0], object_pairs_hook=raw.unique_object)
    except (ValueError, TypeError): return None


def valid_libraries(value):
    return (isinstance(value, dict) and set(value) == {"provider", "sdl", "base"} and
            all(isinstance(p, str) and p and "\n" not in p and "\r" not in p for p in value.values()))


def loading(nonce, text):
    if not re.fullmatch(r"[0-9a-f]{32}", nonce): return None
    value = one(LOADED, text)
    if (not isinstance(value, dict) or set(value) != {"schema", "nonce", "loaded"} or
            type(value["schema"]) is not int or value["schema"] != 1 or value["nonce"] != nonce or
            not valid_libraries(value["loaded"])): return None
    return value


def record(case, nonce, prefix, text):
    if case not in CASES or not re.fullmatch(r"[0-9a-f]{32}", nonce): raise ValueError("invalid case or nonce")
    value = one(prefix, text)
    cycles = 24 if case == "orders" else 2 if case == "restart" else 1
    created = 5 if case == "hotplug" else cycles * 4
    expected = dict(schema=1, case=case, nonce=nonce, cycles=cycles, created=created, cleaned=created,
                    owners=4, connected_after=0, sources_after=0, pending=0, sdl_init_after=0, sdl_version=3004014)
    if not isinstance(value, dict) or set(value) != set(expected) | {"checks", "loaded"}: return None
    if any(type(value[k]) is not type(v) or value[k] != v for k, v in expected.items()): return None
    if type(value["checks"]) is not int or value["checks"] < 60 or not valid_libraries(value["loaded"]): return None
    return value


def classify(case, nonce, code, text):
    if code != 0 or REJECTED in text or any(s in text for s in ("Sanitizer", "runtime error:", "MW3_INGRESS_FAILURE:")): return None
    if case == "control-map" and guide_policy(text) is None: return None
    return record(case, nonce, PREFIX, text)


def guide_policy(text):
    lines = [line for line in text.splitlines() if line.startswith("MW3_INGRESS_POLICY:")]
    if len(lines) != 1: return None
    match = re.fullmatch(r"MW3_INGRESS_POLICY:guide_pending=([01]) release_ms=(\d+) source_released=1", lines[0])
    if match is None or int(match[2]) > 1000: return None
    return dict(guide_pending=int(match[1]), release_ms=int(match[2]), source_released=1)


def rejected(nonce, code, text):
    failures = [line for line in text.splitlines() if line.startswith("MW3_INGRESS_FAILURE:")]
    if (code != 1 or PREFIX in text or failures != ["MW3_INGRESS_FAILURE:deliberate wrong-route rejected"] or
            any(s in text for s in ("Sanitizer", "runtime error:"))): return None
    return record("held", nonce, REJECTED, text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "sdk-report", "output-root"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--sanitizers", action="store_true")
    parser.add_argument("--repeat", type=int, default=2, choices=range(1, 9))
    args = parser.parse_args()
    output = None
    verifier = input_profile
    report = dict(schema_version=1, status="IN_PROGRESS", game_free=True, guest_executed=False,
                  physical_devices=False, script_sha256=common.sha(__file__),
                  host_sanitizers=args.sanitizers, results=[])
    try:
        sdk, identity = verifier.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        output = output_root(args.root, args.sdk_report, sdk, args.output_root) / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        maintained = inputs()
        input_hashes = {name: common.sha(path) for name, path in maintained.items()}
        stage = output / "maintained-source"
        for name, path in maintained.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        shutil.copy2(__file__, output / "maintained-driver.py")
        host_sources = common.snapshot(stage)
        report.update(sdk=identity, host_sources=host_sources, repeat=args.repeat,
                      helper_sha256=common.sha(raw.__file__))
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
        if report["compiler"] != identity["compiler"]:
            raise ValueError("host adapter compiler differs from verified provider")
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
        binary = build / ("input-ingress-contracts.exe" if windows else "input-ingress-contracts")
        report["binary_sha256"] = common.sha(binary)
        report["compile_commands_sha256"] = common.sha(build / "compile_commands.json")
        report["cmake_cache_sha256"] = common.sha(build / "CMakeCache.txt")
        provider = sdk / ("bin/rexhid-sdl3.dll" if windows else "lib/librexhid-sdl3.so")
        library_identity = None
        for repeat in range(args.repeat):
            order = CASES if repeat % 2 == 0 else tuple(reversed(CASES))
            for case in (*order, "wrong-route"):
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
                actual_case = "held" if case == "wrong-route" else case
                command = [str(binary), actual_case, nonce, str(provider)]
                if case == "wrong-route": command.append("--wrong-route")
                code = run_process(command, cwd=lane, env=child, log=lane / "run.log", timeout=30)
                text = (lane / "run.log").read_text(errors="replace")
                record = rejected(nonce, code, text) if case == "wrong-route" else classify(actual_case, nonce, code, text)
                loader = loading(nonce, text)
                passed = record is not None and loader is not None and record["loaded"] == loader["loaded"]
                observed = None
                if loader is not None:
                    observed = loaded_identity(loader, sdk, windows)
                    if library_identity is None: library_identity = observed
                    elif library_identity != observed: raise ValueError("loaded library identities changed between cases")
                row = dict(case=case, repeat=repeat, returncode=code, status="PASS" if passed else "FAIL",
                           command=command, log_sha256=common.sha(lane / "run.log"), record=record, loaded=observed,
                           policy=guide_policy(text) if actual_case == "control-map" else None)
                report["results"].append(row)
                print(json.dumps({key: row[key] for key in ("case", "repeat", "status", "returncode")}), flush=True)
        _, after = verifier.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        if (after != identity or common.sha(binary) != report["binary_sha256"] or
                common.snapshot(output / "maintained-source") != host_sources or common.sha(__file__) != report["script_sha256"] or
                common.sha(raw.__file__) != report["helper_sha256"] or
                common.sha(build / "CMakeCache.txt") != report["cmake_cache_sha256"] or
                {name: common.sha(path) for name, path in inputs().items()} != input_hashes):
            raise ValueError("verified source, SDK or binary changed")
        report["status"] = "PASS" if all(row["status"] == "PASS" for row in report["results"]) else "FAIL"
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return int(report["status"] != "PASS")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output: (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"Ingress diagnostic failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
