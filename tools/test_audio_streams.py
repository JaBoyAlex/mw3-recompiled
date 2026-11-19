#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Verify original host lifetime admission through an unchanged actual SDK bridge."""
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
import test_sdk_audio as audio

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/host_platform/audio_streams"
CORE = ROOT / "runtime/audio/streams"
CASES = ("reuse", "owners", "queue", "lifecycle")
COMPLETE = "MW3_AUDIO_GATE_COMPLETE:"


def positive(row):
    if row["opens"] != row["closes"] or row["checks"] < 8:
        return False
    if len(row["accepted_ns"]) != row["valid_submits"]:
        return False
    blocks = sum(row[k] for k in ("stale_blocks", "owner_blocks", "instance_blocks", "frame_blocks"))
    if len(row["rejected_ns"]) != blocks:
        return False
    name = row["name"]
    if name == "reuse":
        return (row["raw_checked"] and row["raw_stale_accepted"] and row["raw_old"] == row["raw_new"] == 2 and
                len(row["raw_ns"]) == 2 and row["opens"] == 6 and row["sdk_submits"] == 5 and
                row["valid_submits"] == row["credits"] == 3 and row["stale_blocks"] == 1 and blocks == 1 and
                row["queue_refusals"] == 0)
    if row["raw_checked"] or row["raw_stale_accepted"] or row["raw_old"] or row["raw_new"] or row["raw_ns"]:
        return False
    if name == "owners":
        return (row["opens"] == 3 and row["sdk_submits"] == row["valid_submits"] == row["credits"] == 2 and
                row["stale_blocks"] == row["owner_blocks"] == row["instance_blocks"] == 1 and blocks == 3 and
                row["queue_refusals"] == 0)
    if name == "queue":
        return (row["opens"] == 2 and row["valid_submits"] >= 6 and row["credits"] == row["valid_submits"] and
                row["sdk_submits"] == row["valid_submits"] + 1 and row["frame_blocks"] == blocks == 2 and
                row["queue_refusals"] == 1)
    return (row["opens"] == 64 and row["valid_submits"] == row["sdk_submits"] == 160 and
            row["credits"] == row["stale_blocks"] == blocks == 32 and row["queue_refusals"] == 0)


def classify(cases, mode, nonce, code, text):
    if (mode not in audio.MODES or not re.fullmatch(r"[0-9a-f]{32}", nonce) or not cases or
            len(cases) > 16 or any(case not in CASES for case in cases)):
        raise ValueError("invalid case/mode/nonce")
    if (code not in (0, 42) or not audio.clean_output(text) or "MW3_AUDIO_GATE_FATAL:" in text or
            "MW3_AUDIO_GATE_INCOMPLETE:" in text or audio.COMPLETE in text):
        return None
    try:
        libs = audio.library_record(mode, nonce, text)
        value = audio.one_record(text, COMPLETE)
        keys = {"schema", "nonce", "mode", "backend", "channels", "threads_before", "threads_after",
                "open_after", "queued_after", "sdl_audio_after", "cases"}
        if not isinstance(value, dict) or set(value) != keys:
            return None
        if (type(value["schema"]) is not int or value["schema"] != 1 or
                any(type(value[k]) is not str or value[k] != libs[k] for k in ("nonce", "mode", "backend")) or
                type(value["channels"]) is not int or value["channels"] != (6 if mode == "sdl" else 2)):
            return None
        for key in ("threads_before", "threads_after", "open_after", "queued_after", "sdl_audio_after"):
            if not audio.integer(value[key], 0, 1024):
                return None
        if (value["threads_before"] != value["threads_after"] or
                any(value[k] != 0 for k in ("open_after", "queued_after", "sdl_audio_after"))):
            return None
        rows = value["cases"]
        fields = {"name", "status", "reason", "checks", "opens", "closes", "sdk_submits", "valid_submits", "credits",
                  "stale_blocks", "owner_blocks", "instance_blocks", "frame_blocks", "queue_refusals", "raw_checked",
                  "raw_stale_accepted", "raw_old", "raw_new", "elapsed_us", "accepted_ns", "rejected_ns", "raw_ns"}
        if not isinstance(rows, list) or len(rows) != len(cases):
            return None
        for expected, row in zip(cases, rows):
            if not isinstance(row, dict) or set(row) != fields or row["name"] != expected:
                return None
            if (row["status"] not in ("PASS", "FAIL") or type(row["reason"]) is not str or
                    len(row["reason"]) > 256 or bool(row["reason"]) != (row["status"] == "FAIL")):
                return None
            for key in fields - {"name", "status", "reason", "raw_checked", "raw_stale_accepted", "accepted_ns", "rejected_ns", "raw_ns"}:
                if not audio.integer(row[key], 0, 30_000_000):
                    return None
            if (type(row["raw_checked"]) is not bool or type(row["raw_stale_accepted"]) is not bool or
                    row["checks"] > 4096 or row["sdk_submits"] > 512 or row["valid_submits"] > 512 or
                    row["opens"] > 64 or row["closes"] > 64 or row["credits"] > 512):
                return None
            for key in ("accepted_ns", "rejected_ns", "raw_ns"):
                samples = row[key]
                if not isinstance(samples, list) or len(samples) > 512 or any(not audio.integer(n, 0, 30_000_000_000) for n in samples):
                    return None
            if row["status"] == "PASS" and not positive(row):
                return None
        failed = any(row["status"] == "FAIL" for row in rows)
        if code != (42 if failed else 0):
            return None
        return dict(status="FAIL" if failed else "PASS", complete=value, libraries=libs)
    except (ValueError, TypeError, KeyError):
        return None


def control(kind, mode, nonce, code, text):
    if not audio.clean_output(text) or "MW3_AUDIO_GATE_FATAL:" in text:
        return False
    if kind == "wrong-result":
        result = classify(("reuse",), mode, nonce, code, text)
        return bool(result and result["status"] == "FAIL" and
                    result["complete"]["cases"][0]["reason"] == "deliberate-wrong-result" and
                    positive(result["complete"]["cases"][0]))
    try:
        audio.library_record(mode, nonce, text)
        return (kind == "incomplete" and code == 43 and COMPLETE not in text and audio.COMPLETE not in text and
                [line for line in text.splitlines() if line.startswith("MW3_AUDIO_GATE_INCOMPLETE:")] ==
                ["MW3_AUDIO_GATE_INCOMPLETE:" + nonce])
    except (ValueError, TypeError, KeyError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "sdk-report", "output-root"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--sanitizers", action="store_true")
    parser.add_argument("--repeat", type=int, choices=range(1, 9), default=3)
    args = parser.parse_args()
    output = None
    report = dict(schema_version=1, task="MW3-062", status="IN_PROGRESS", game_free=True, guest_executed=False,
                  sdk_repaired=False, raw_lifetime_safe=False, audible_output_verified=False,
                  host_sanitizers=args.sanitizers, sdk_instrumented=False, script_sha256=common.sha(__file__), results=[])
    try:
        sdk, identity = audio.storage.verify_package(args.sdk_report)
        output = common.private_cache(args.output_root, ROOT / ".local/game") / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        shutil.copytree(SOURCE, output / "maintained-tests", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(CORE, output / "maintained-core", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(__file__, output / "maintained-driver.py")
        tests, core = common.snapshot(output / "maintained-tests"), common.snapshot(output / "maintained-core")
        report.update(sdk=identity, host_sources=tests, core_sources=core, repeat=args.repeat)
        windows = sys.platform == "win32"
        if windows:
            win = audio.win
            lock = json.loads(win.LOCK.read_text())
            clang, compiler_identity = win.compiler(args.root.resolve(), lock["compiler"], False)
            env, cmake, ninja, report["host_tools"] = win.msvc_environment(lock, clang)
            compiler = clang / "bin/clang++.exe"
            extra = ["-DCMAKE_MAKE_PROGRAM=" + ninja.as_posix(), "-DCMAKE_CXX_FLAGS=-march=x86-64-v2", "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld"]
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
        configure = [cmake, "-S", output / "maintained-tests", "-B", build, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                     "-DCMAKE_CXX_COMPILER=" + compiler.as_posix(), "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG",
                     "-DCMAKE_PREFIX_PATH=" + sdk.as_posix(), "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                     "-DMW3_AUDIO_CORE=" + (output / "maintained-core").as_posix(), "-DMW3_AUDIO_SDK_PROBE=ON",
                     "-DMW3_AUDIO_STREAM_SANITIZERS=" + ("ON" if args.sanitizers else "OFF"), *extra]
        report["commands"] = []
        for label, command in (("configure", configure), ("build", [cmake, "--build", build, "--parallel", "2"])):
            report["commands"].append(list(map(str, command)))
            with (output / (label + ".log")).open("wb") as log:
                subprocess.run(list(map(str, command)), env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        binary = build / ("audio-streams-sdk.exe" if windows else "audio-streams-sdk")
        report.update(binary_sha256=common.sha(binary), compile_commands_sha256=common.sha(build / "compile_commands.json"))
        plans = []
        for mode in audio.MODES:
            plans += [(f"{mode}-{case}-{n}", mode, (case,), None) for n in range(args.repeat) for case in CASES]
            plans += [(mode + "-ordered", mode, CASES, None), (mode + "-reversed", mode, CASES[::-1], None),
                      (mode + "-wrong-result", mode, ("reuse",), "wrong-result"), (mode + "-incomplete", mode, (), "incomplete")]
        for label, mode, cases, kind in plans:
            lane = output / label
            for name in ("tmp", "config", "data", "runtime", "tree"):
                (lane / name).mkdir(parents=True)
            nonce = uuid.uuid4().hex
            (lane / "tree/.owner").write_bytes(("mw3-audio-streams-v1\n" + nonce + "\n").encode("ascii"))
            child = {k: v for k, v in env.items() if not k.startswith(("REX_", "MW3_", "SDL_", "LD_", "ASAN_", "LSAN_", "UBSAN_"))}
            child.update(MW3_AUDIO_MODE=mode, MW3_AUDIO_CASES="incomplete" if kind == "incomplete" else ",".join(cases),
                         MW3_AUDIO_TREE=str(lane / "tree"), MW3_AUDIO_NONCE=nonce,
                         TMPDIR=str(lane / "tmp"), TMP=str(lane / "tmp"), TEMP=str(lane / "tmp"),
                         XDG_CONFIG_HOME=str(lane / "config"), XDG_DATA_HOME=str(lane / "data"), XDG_RUNTIME_DIR=str(lane / "runtime"),
                         SDL_VIDEO_DRIVER="dummy", SDL_AUDIO_DRIVER="dummy", ASAN_OPTIONS="detect_leaks=1",
                         UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
            if kind == "wrong-result": child["MW3_AUDIO_WRONG"] = "1"
            if windows: child["PATH"] = str(sdk / "bin") + os.pathsep + child.get("PATH", "")
            else: child["LD_LIBRARY_PATH"] = str(sdk / "lib")
            command = [str(binary), "--kernel.headless=true", "--app.root=" + str(lane / "app"), "--app.user_root=" + str(lane / "user"),
                       "--ui.driver=none", "--hid.drivers=none", "--gpu.driver=none",
                       "--apu.driver=" + ("sdl3" if mode == "sdl" else "none"), "--apu.max_queued_frames=4"]
            code = audio.run_process(command, cwd=lane, env=child, log=lane / "run.log", timeout=30)
            text = (lane / "run.log").read_text(errors="replace")
            record = None if kind else classify(cases, mode, nonce, code, text)
            status = ("PASS" if control(kind, mode, nonce, code, text) else "FAIL") if kind else record["status"] if record else "FAIL"
            loaded = None
            try:
                loaded = audio.loaded_identity(audio.library_record(mode, nonce, text), sdk, windows, build)
            except (OSError, ValueError, TypeError, KeyError):
                status = "FAIL"
            row = dict(label=label, mode=mode, cases=cases, control=kind, nonce=nonce, returncode=code, status=status,
                       command=command, record=record, loaded=loaded, log_sha256=common.sha(lane / "run.log"))
            report["results"].append(row)
            print(json.dumps({key: row[key] for key in ("label", "status", "returncode")}), flush=True)
        _, after = audio.storage.verify_package(args.sdk_report)
        if (after != identity or common.sha(binary) != report["binary_sha256"] or common.sha(__file__) != report["script_sha256"] or
                common.snapshot(output / "maintained-tests") != tests or common.snapshot(output / "maintained-core") != core or
                any(common.sha(SOURCE / name) != entry["sha256"] for name, entry in tests.items()) or
                any(common.sha(CORE / name) != entry["sha256"] for name, entry in core.items())):
            raise ValueError("SDK, core, host source, driver or binary changed")
        report["status"] = "PASS" if all(row["status"] == "PASS" for row in report["results"]) else "FAIL"
        report["artifacts"] = audio.storage.artifact_snapshot(output)
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return int(report["status"] != "PASS")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output: (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"Audio ownership diagnostic failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
