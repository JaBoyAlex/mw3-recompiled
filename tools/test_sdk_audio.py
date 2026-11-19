#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Investigate actual approved SDK host audio with original PCM and private silent sinks."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

import prepare_windows_runtime as win
import recompile as common
import test_profile_storage as storage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/host_platform/sdk_audio"
CASES = ("capacity", "identity", "queue", "lifecycle")
MODES = ("timer", "sdl")
COMPLETE = "MW3_AUDIO_COMPLETE:"
LIBRARIES = "MW3_AUDIO_LIBRARIES:"
ROLES = {"audio": "rexapu", "app": "rexapp", "base": "rexbase", "sdl": "SDL3", "provider": "rexapu-sdl3"}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate result field")
        result[key] = value
    return result


def one_record(text, prefix):
    rows = [line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)]
    if len(rows) != 1:
        raise ValueError("missing or duplicate record")
    return json.loads(rows[0], object_pairs_hook=unique_object)


def integer(value, minimum=0, maximum=2**63 - 1):
    return type(value) is int and minimum <= value <= maximum


def clean_output(text):
    return not any(token in text for token in ("Sanitizer", "runtime error:", "MW3_AUDIO_FATAL:", "end of crash report"))


def library_record(mode, nonce, text):
    value = one_record(text, LIBRARIES)
    expected = dict(nonce=nonce, mode=mode, backend="dummy" if mode == "sdl" else "none")
    if not isinstance(value, dict) or set(value) != set(expected) | {"loaded"}:
        raise ValueError("invalid library record")
    if any(type(value[k]) is not str or value[k] != v for k, v in expected.items()):
        raise ValueError("stale library record")
    loaded = value["loaded"]
    if not isinstance(loaded, dict) or set(loaded) != set(ROLES):
        raise ValueError("invalid loaded roles")
    for role, path in loaded.items():
        if role == "provider" and mode == "timer" and path is None:
            continue
        if not isinstance(path, str) or not path or len(path) > 32768 or any(c in path for c in "\r\n\0"):
            raise ValueError("invalid loaded path")
    if mode == "timer" and loaded["provider"] is not None:
        raise ValueError("timer record claims an audio provider")
    return value


def classify(cases, mode, nonce, code, text):
    """Return a fully accounted observation. A recorded SDK FAIL stays FAIL."""
    if (mode not in MODES or not re.fullmatch(r"[0-9a-f]{32}", nonce) or not cases or
            len(cases) > 16 or any(case not in CASES for case in cases)):
        raise ValueError("invalid requested cases/mode/nonce")
    if code not in (0, 42) or not clean_output(text):
        return None
    if "MW3_AUDIO_INCOMPLETE:" in text or "MW3_AUDIO_BACKEND_REJECTED:" in text:
        return None
    try:
        libs = library_record(mode, nonce, text)
        value = one_record(text, COMPLETE)
        fields = {"schema", "nonce", "mode", "backend", "channels", "threads_before", "threads_after",
                  "open_after", "queued_after", "sdl_audio_after", "cases"}
        if not isinstance(value, dict) or set(value) != fields:
            return None
        if (type(value["schema"]) is not int or value["schema"] != 1 or
                any(type(value[k]) is not str or value[k] != libs[k] for k in ("nonce", "mode", "backend")) or
                not integer(value["channels"], 2, 6) or value["channels"] not in (2, 6) or
                (mode == "timer" and value["channels"] != 2)):
            return None
        for key in ("threads_before", "threads_after", "open_after", "queued_after", "sdl_audio_after"):
            if not integer(value[key], 0, 1024):
                return None
        if (value["threads_before"] != value["threads_after"] or
                any(value[k] != 0 for k in ("open_after", "queued_after", "sdl_audio_after"))):
            return None
        rows = value["cases"]
        if not isinstance(rows, list) or len(rows) != len(cases):
            return None
        keys = {"name", "status", "reason", "checks", "opened", "accepted", "callbacks", "queue_peak",
                "old_id", "new_id", "stale_ok", "underruns", "elapsed_us", "submit_ns"}
        for expected, row in zip(cases, rows):
            if not isinstance(row, dict) or set(row) != keys or row["name"] != expected:
                return None
            if (row["status"] not in ("PASS", "FAIL") or type(row["reason"]) is not str or
                    bool(row["reason"]) != (row["status"] == "FAIL") or len(row["reason"]) > 256):
                return None
            for key in keys - {"name", "status", "reason", "stale_ok", "submit_ns"}:
                if not integer(row[key]):
                    return None
            if (type(row["stale_ok"]) is not bool or row["checks"] > 4096 or row["opened"] > 64 or
                    row["accepted"] > 512 or row["callbacks"] > 512 or row["queue_peak"] > 32 or
                    row["old_id"] > 2**32 - 1 or row["new_id"] > 2**32 - 1 or row["elapsed_us"] > 30_000_000):
                return None
            times = row["submit_ns"]
            if not isinstance(times, list) or len(times) > 512 or any(not integer(n, 0, 30_000_000_000) for n in times):
                return None
            if row["status"] == "PASS":
                if row["checks"] < 8 or row["queue_peak"] > 4 or row["stale_ok"]:
                    return None
                if expected != "identity" and (row["old_id"] or row["new_id"]):
                    return None
                if expected == "capacity" and (row["opened"] != 8 or row["accepted"] or row["callbacks"] or times):
                    return None
                if expected == "identity" and (row["opened"] != 3 or row["accepted"] != 1 or
                                               row["callbacks"] != 1 or not row["old_id"] or not row["new_id"]):
                    return None
                if expected == "queue" and (row["opened"] != 2 or row["accepted"] < 5 or
                                            row["callbacks"] != row["accepted"] or not row["underruns"] or
                                            len(times) != row["accepted"] + 1):
                    return None
                if expected == "lifecycle" and (row["opened"] != 64 or row["accepted"] != 160 or
                                                not 32 <= row["callbacks"] <= 160 or len(times) != 160):
                    return None
        failed = any(row["status"] == "FAIL" for row in rows)
        if code != (42 if failed else 0):
            return None
        return dict(status="FAIL" if failed else "PASS", complete=value, libraries=libs)
    except (ValueError, TypeError, KeyError):
        return None


def control(kind, mode, nonce, code, text):
    if not clean_output(text):
        return False
    try:
        if kind == "wrong-result":
            result = classify(("capacity",), mode, nonce, code, text)
            if not result or result["status"] != "FAIL":
                return False
            row = result["complete"]["cases"][0]
            return (row["reason"] == "deliberate-wrong-result" and row["opened"] == 8 and row["checks"] >= 18 and
                    all(row[k] == 0 for k in ("accepted", "callbacks", "queue_peak", "old_id", "new_id", "underruns")) and
                    row["stale_ok"] is False and row["submit_ns"] == [])
        if kind == "incomplete":
            library_record(mode, nonce, text)
            return (code == 43 and COMPLETE not in text and "MW3_AUDIO_BACKEND_REJECTED:" not in text and
                    [line for line in text.splitlines() if line.startswith("MW3_AUDIO_INCOMPLETE:")] ==
                    ["MW3_AUDIO_INCOMPLETE:" + nonce])
        if kind == "invalid-driver":
            value = one_record(text, "MW3_AUDIO_BACKEND_REJECTED:")
            return (mode == "sdl" and code == 44 and COMPLETE not in text and LIBRARIES not in text and
                    "MW3_AUDIO_INCOMPLETE:" not in text and isinstance(value, dict) and
                    set(value) == {"nonce", "message", "category", "shutdown", "threads_before", "threads_after", "sdl_audio_after"} and value["nonce"] == nonce and
                    isinstance(value["message"], str) and
                    "module 'rexapu' failed to init, no audio driver is available" in value["message"] and
                    type(value["category"]) is int and value["category"] == 12 and
                    type(value["shutdown"]) is int and value["shutdown"] == 1 and
                    integer(value["threads_before"], 0, 1024) and integer(value["threads_after"], 0, 1024) and
                    value["threads_before"] == value["threads_after"] and
                    type(value["sdl_audio_after"]) is int and value["sdl_audio_after"] == 0)
    except (ValueError, TypeError, KeyError):
        return False
    return False


def loaded_identity(libraries, sdk, windows, staging):
    result = {}
    sdk, staging = sdk.resolve(strict=True), staging.resolve(strict=True)
    for role, name in ROLES.items():
        path = libraries["loaded"][role]
        if path is None:
            result[role] = None
            continue
        filename = name + ".dll" if windows else "lib" + name + (".so.0" if role == "sdl" else ".so")
        expected = (sdk / ("bin" if windows else "lib") / filename).resolve(strict=True)
        actual = Path(path).resolve(strict=True)
        if (actual != expected and actual.parent != staging) or actual.name.lower() != expected.name.lower():
            raise ValueError("unexpected loaded " + role + " path")
        actual_hash = common.sha(actual)
        if actual_hash != common.sha(expected):
            raise ValueError("wrong loaded " + role + " bytes")
        result[role] = dict(path=str(actual), sha256=actual_hash, package_path=str(expected))
    return result


def run_process(command, *, cwd, env, log, timeout):
    with Path(log).open("wb") as stream:
        try:
            return subprocess.run(command, cwd=cwd, env=env, stdout=stream,
                                  stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            return -999  # run() kills and waits only for this captured child.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "sdk-report", "output-root"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--sanitizers", action="store_true")
    parser.add_argument("--repeat", type=int, choices=range(1, 9), default=3)
    args = parser.parse_args()
    output = None
    report = dict(schema_version=1, task="MW3-061", status="IN_PROGRESS", game_free=True, guest_executed=False,
                  audible_output_verified=False, physical_device_loss_tested=False, sdk_instrumented=False,
                  host_sanitizers=args.sanitizers, script_sha256=common.sha(__file__), results=[])
    try:
        sdk, identity = storage.verify_package(args.sdk_report)
        output = common.private_cache(args.output_root, ROOT / ".local/game") / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        shutil.copytree(SOURCE, output / "maintained-source", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(__file__, output / "maintained-driver.py")
        sources = common.snapshot(output / "maintained-source")
        report.update(sdk=identity, host_sources=sources, repeat=args.repeat)
        windows = sys.platform == "win32"
        if windows:
            lock = json.loads(win.LOCK.read_text())
            clang, compiler_identity = win.compiler(args.root.resolve(), lock["compiler"], False)
            env, cmake, ninja, report["host_tools"] = win.msvc_environment(lock, clang)
            compiler = clang / "bin/clang++.exe"
            extra = ["-DCMAKE_MAKE_PROGRAM=" + ninja.as_posix(), "-DCMAKE_CXX_FLAGS=-march=x86-64-v2",
                     "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld"]
            if args.sanitizers:
                report["calibration"] = win.calibrate_sanitizer(output, clang, env)
        else:
            env, cmake = dict(os.environ), "cmake"
            compiler = Path(shutil.which("clang++-20") or "missing")
            compiler_identity = dict(sha256=common.sha(compiler), version=subprocess.check_output([compiler, "--version"], text=True).splitlines()[0])
            extra = ["-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13",
                     "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2"]
        if compiler_identity != identity["compiler"]:
            raise ValueError("compiler differs from approved SDK compiler")
        report["compiler"] = compiler_identity
        build = output / "build"
        configure = [cmake, "-S", output / "maintained-source", "-B", build, "-G", "Ninja",
                     "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_CXX_COMPILER=" + compiler.as_posix(),
                     "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG", "-DCMAKE_PREFIX_PATH=" + sdk.as_posix(),
                     "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON", "-DMW3_AUDIO_SANITIZERS=" + ("ON" if args.sanitizers else "OFF"), *extra]
        report["commands"] = []
        for label, command in (("configure", configure), ("build", [cmake, "--build", build, "--parallel", "2"])):
            report["commands"].append(list(map(str, command)))
            with (output / (label + ".log")).open("wb") as log:
                subprocess.run(list(map(str, command)), env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        binary = build / ("sdk-audio-contracts.exe" if windows else "sdk-audio-contracts")
        report.update(binary_sha256=common.sha(binary), compile_commands_sha256=common.sha(build / "compile_commands.json"))
        plans = []
        for mode in MODES:
            plans += [(f"{mode}-{case}-{n}", mode, (case,), None) for n in range(args.repeat) for case in CASES]
            plans += [(mode + "-ordered", mode, CASES, None), (mode + "-reversed", mode, CASES[::-1], None),
                      (mode + "-wrong-result", mode, ("capacity",), "wrong-result"),
                      (mode + "-incomplete", mode, (), "incomplete")]
        plans += [("sdl-invalid-driver", "sdl", (), "invalid-driver")]
        for label, mode, cases, kind in plans:
            lane = output / label
            for name in ("tmp", "config", "data", "runtime", "tree"):
                (lane / name).mkdir(parents=True)
            nonce = uuid.uuid4().hex
            (lane / "tree/.owner").write_bytes(("mw3-sdk-audio-v1\n" + nonce + "\n").encode("ascii"))
            child = {k: v for k, v in env.items() if not k.startswith(("REX_", "MW3_", "SDL_", "LD_", "ASAN_", "LSAN_", "UBSAN_"))}
            child.update(MW3_AUDIO_MODE=mode, MW3_AUDIO_CASES=kind if kind in ("incomplete", "invalid-driver") else ",".join(cases),
                         MW3_AUDIO_TREE=str(lane / "tree"), MW3_AUDIO_NONCE=nonce,
                         TMPDIR=str(lane / "tmp"), TMP=str(lane / "tmp"), TEMP=str(lane / "tmp"),
                         XDG_CONFIG_HOME=str(lane / "config"), XDG_DATA_HOME=str(lane / "data"), XDG_RUNTIME_DIR=str(lane / "runtime"),
                         SDL_VIDEO_DRIVER="dummy", SDL_AUDIO_DRIVER="mw3_invalid_061" if kind == "invalid-driver" else "dummy",
                         ASAN_OPTIONS="detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
            if kind == "wrong-result":
                child["MW3_AUDIO_WRONG"] = "1"
            if windows:
                child["PATH"] = str(sdk / "bin") + os.pathsep + child.get("PATH", "")
            else:
                child["LD_LIBRARY_PATH"] = str(sdk / "lib")
            command = [str(binary), "--kernel.headless=true", "--app.root=" + str(lane / "app"),
                       "--app.user_root=" + str(lane / "user"), "--ui.driver=none", "--hid.drivers=none",
                       "--gpu.driver=none", "--apu.driver=" + ("sdl3" if mode == "sdl" else "none"), "--apu.max_queued_frames=4"]
            started = time.monotonic()
            code = run_process(command, cwd=lane, env=child, log=lane / "run.log", timeout=30)
            text = (lane / "run.log").read_text(errors="replace")
            observed, loaded = None, None
            if kind:
                status = "PASS" if control(kind, mode, nonce, code, text) else "FAIL"
            else:
                observed = classify(cases, mode, nonce, code, text)
                status = observed["status"] if observed else "FAIL"
            try:
                if kind != "invalid-driver":
                    libraries = library_record(mode, nonce, text)
                    loaded = loaded_identity(libraries, sdk, windows, build)
            except (OSError, ValueError, KeyError, TypeError):
                status = "FAIL"
            row = dict(label=label, mode=mode, cases=cases, control=kind, nonce=nonce, status=status, returncode=code,
                       seconds=time.monotonic() - started, command=command, record=observed, loaded=loaded,
                       log_sha256=common.sha(lane / "run.log"))
            report["results"].append(row)
            print(json.dumps({k: row[k] for k in ("label", "status", "returncode")}), flush=True)
        _, after = storage.verify_package(args.sdk_report)
        if (after != identity or common.sha(binary) != report["binary_sha256"] or common.sha(__file__) != report["script_sha256"] or
                common.snapshot(output / "maintained-source") != sources or
                any(common.sha(SOURCE / name) != entry["sha256"] for name, entry in sources.items())):
            raise ValueError("SDK, source, driver or binary changed")
        report["status"] = "FAIL" if any(row["status"] == "FAIL" for row in report["results"]) else "PASS"
        report["artifacts"] = storage.artifact_snapshot(output)
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return int(report["status"] != "PASS")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output:
            (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"Audio diagnostic failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
