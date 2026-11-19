#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Run original private-tree contracts against the verified selected SDK filesystem."""
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

import prepare_runtime_xma as xma
import prepare_runtime_memory as memory
import recompile as common

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/profile_storage"
CASES = ("profiles", "read-only", "bounds", "relative", "rename-remove", "file-link", "directory-link", "directory-junction")
CORE = CASES[:5]


def verify_package(report_path, validation=None, lock_path=None):
    """Bind all executed package bytes to a previously merged approved receipt.

    Source checkout state cannot change these immutable library/header identities.
    This read-only verifier never regenerates or repairs a shared SDK worktree.
    """
    validation = validation or ROOT / "config/toolchains/rexglue-xma/validation.json"
    lock_path = lock_path or xma.LOCK
    approved = json.loads(validation.read_text())
    receipt_sha = common.sha(report_path)
    candidates = [row for row in approved["sdk_preparations"]
                  if row["receipt_sha256"] == receipt_sha and not row["core_sanitizers"]]
    if len(candidates) != 1 or approved["status"] != "PASS":
        raise ValueError("receipt is not an approved native SDK preparation")
    receipt = json.loads(report_path.read_text())
    lock = json.loads(lock_path.read_text())
    if (receipt.get("status") != "PASS" or receipt.get("profile") != lock["profile"]
            or receipt.get("core_sanitizers") or receipt.get("xma_lock_sha256") != common.sha(lock_path)
            or receipt.get("script_sha256") != common.sha(xma.__file__)):
        raise ValueError("stale or non-native SDK receipt")
    sdk = common.no_symlink_path(receipt["sdk_prefix"])
    files = memory.package_files(sdk)
    if files != receipt["sdk_files"]:
        raise ValueError("approved SDK package changed")
    return sdk, dict(preparation_sha256=receipt_sha, validation_sha256=common.sha(validation),
                     sdk_tree_sha256=common.digest(files), sdk_files=files,
                     source=receipt["source"], compiler=receipt["compiler"], core_sanitizers=False)


def classify(cases, code, text, mutation=False, incomplete=False):
    """Strict result accounting; a retained SDK failure remains FAIL."""
    if any(token in text for token in ("Sanitizer", "runtime error:", "MW3_STORAGE_FATAL:")):
        return "FAIL"
    if len(re.findall(r"^MW3_STORAGE_LIBRARY:.+$", text, re.M)) != 1:
        return "FAIL"
    complete = re.findall(r"^MW3_STORAGE_COMPLETE:count=(\d+) failures=(\d+) skips=(\d+) threads_before=(\d+) threads_after=(\d+)$", text, re.M)
    rows = re.findall(r"^MW3_STORAGE_CASE:name=(\S+) status=(PASS|FAIL|SKIP) microseconds=(\d+)$", text, re.M)
    failed = re.findall(r"^MW3_STORAGE_FAILURE:case=(\S+) reason=(\S+)$", text, re.M)
    skipped = re.findall(r"^MW3_STORAGE_SKIP:case=(\S+) reason=host-link-permission-or-unsupported$", text, re.M)
    if incomplete:
        return "PASS" if (code == 43 and not rows and not complete and not failed
                          and text.count("MW3_STORAGE_INCOMPLETE:armed\n") == 1) else "FAIL"
    if (not cases or any(case not in CASES for case in cases) or len(complete) != 1
            or [r[0] for r in rows] != list(cases)):
        return "FAIL"
    count, failures, skips, before, after = map(int, complete[0])
    if (count != len(cases) or before != after or failures != sum(r[1] == "FAIL" for r in rows)
            or skips != sum(r[1] == "SKIP" for r in rows) or len(failed) != failures
            or [r[0] for r in failed] != [r[0] for r in rows if r[1] == "FAIL"]
            or skipped != [r[0] for r in rows if r[1] == "SKIP"]
            or any(r[0] not in ("file-link", "directory-link", "directory-junction") for r in rows if r[1] == "SKIP")):
        return "FAIL"
    if mutation:
        return "PASS" if (list(cases) == ["profiles"] and code == 42 and failed == [("profiles", "deliberate-wrong-profile")]
                          and skips == 0 and text.count("MW3_STORAGE_MUTATION:wrong-profile\n") == 1) else "FAIL"
    if "MW3_STORAGE_MUTATION:" in text or "MW3_STORAGE_INCOMPLETE:" in text or code != 0 or failures:
        return "FAIL"
    return "SKIP" if skips else "PASS"


def loaded_library(text, sdk, windows):
    rows = re.findall(r"^MW3_STORAGE_LIBRARY:(.+)$", text, re.M)
    if len(rows) != 1:
        raise ValueError("missing/duplicate filesystem library identity")
    loaded = Path(rows[0]).resolve(strict=True)
    expected = (sdk / ("bin/rexfilesystem.dll" if windows else "lib/librexfilesystem.so")).resolve(strict=True)
    # A configured CMake target may stage a verified copy beside the executable.
    if loaded.name.lower() != expected.name.lower() or common.sha(loaded) != common.sha(expected):
        raise ValueError("another filesystem module was loaded")
    return dict(path=str(loaded), sha256=common.sha(loaded), package_path=str(expected))


def artifact_snapshot(root):
    """Record intentional fixture links without following redirected directories."""
    result = {}
    for folder, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(folder) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                if not path.resolve(strict=True).is_relative_to(root.resolve()):
                    raise ValueError("fixture link leaves private attempt")
                result[relative] = dict(link=os.readlink(path), directory=path.is_dir())
                if name in directories:
                    directories.remove(name)
            elif path.is_file():
                result[relative] = dict(sha256=common.sha(path), bytes=path.stat().st_size)
            elif not path.is_dir():
                raise ValueError("nonregular private artifact")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "sdk-report", "output-root"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--sanitizers", action="store_true")
    args = parser.parse_args()
    output = None
    report = dict(schema_version=1, task="MW3-060", status="IN_PROGRESS", game_free=True,
                  guest_executed=False, secure_save_support=False, host_sanitizers=args.sanitizers,
                  filesystem_instrumented=False, script_sha256=common.sha(__file__), results=[])
    try:
        verify_started = time.monotonic()
        sdk, evidence = verify_package(args.sdk_report)
        report["initial_package_verification_seconds"] = time.monotonic() - verify_started
        output = common.private_cache(args.output_root, ROOT / ".local/game") / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        shutil.copytree(SOURCE, output / "maintained-source", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(__file__, output / "maintained-driver.py")
        source_identity = common.snapshot(output / "maintained-source")
        report.update(sdk=evidence, sdk_report_sha256=common.sha(args.sdk_report), host_sources=source_identity)
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
            env, cmake = dict(os.environ), "cmake"
            compiler = Path(shutil.which("clang++-20") or "missing")
            report["compiler"] = dict(sha256=common.sha(compiler), version=subprocess.check_output([compiler, "--version"], text=True).splitlines()[0])
            extra = ["-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13",
                     "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2"]
        if report["compiler"] != evidence["compiler"]:
            raise ValueError("harness compiler differs from the approved SDK compiler")
        build = output / "build"
        configure = [cmake, "-S", output / "maintained-source", "-B", build, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                     "-DCMAKE_CXX_COMPILER=" + compiler.as_posix(), "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG",
                     "-DCMAKE_PREFIX_PATH=" + sdk.as_posix(), "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                     "-DMW3_STORAGE_SANITIZERS=" + ("ON" if args.sanitizers else "OFF"), *extra]
        for label, cmd in (("configure", configure), ("build", [cmake, "--build", build, "--parallel", "2"])):
            report.setdefault("commands", []).append(list(map(str, cmd)))
            with (output / (label + ".log")).open("wb") as log:
                subprocess.run(list(map(str, cmd)), env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        binary = build / ("profile-storage.exe" if windows else "profile-storage")
        report["binary_sha256"] = common.sha(binary)
        plans = [(f"{case}-{repeat}", (case,), False, False) for repeat in range(3) for case in CASES]
        plans += [("ordered", CORE, False, False), ("reversed", CORE[::-1], False, False),
                  ("wrong-result", ("profiles",), True, False), ("incomplete", (), False, True)]
        for label, cases, mutation, incomplete in plans:
            lane = output / label
            for name in ("tmp", "config", "tree"):
                (lane / name).mkdir(parents=True)
            (lane / "tree/.owner").write_text("mw3-profile-storage-v1")
            child = {k: v for k, v in env.items() if not k.startswith(("REX_", "MW3_", "LD_", "ASAN_", "LSAN_", "UBSAN_"))}
            child.update(MW3_STORAGE_TREE=str(lane / "tree"), MW3_STORAGE_CASES="incomplete" if incomplete else ",".join(cases),
                         TMPDIR=str(lane / "tmp"), TMP=str(lane / "tmp"), TEMP=str(lane / "tmp"),
                         XDG_CONFIG_HOME=str(lane / "config"), SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                         ASAN_OPTIONS="detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
            if mutation:
                child["MW3_STORAGE_MUTATION"] = "wrong-profile"
            if windows:
                child["PATH"] = str(sdk / "bin") + os.pathsep + child.get("PATH", "")
            else:
                child["LD_LIBRARY_PATH"] = str(sdk / "lib")
            cmd = [str(binary), "--kernel.headless=true", "--app.root=" + str(lane / "app"),
                   "--app.user_root=" + str(lane / "user"), "--ui.driver=none", "--hid.drivers=none",
                   "--apu.driver=none", "--gpu.driver=none"]
            started = time.monotonic()
            with (lane / "run.log").open("wb") as log:
                try:
                    code = subprocess.run(cmd, env=child, cwd=lane, stdout=log, stderr=subprocess.STDOUT, timeout=30).returncode
                except subprocess.TimeoutExpired:
                    code = -999
            text = (lane / "run.log").read_text(errors="replace")
            status = classify(cases, code, text, mutation, incomplete)
            try:
                library = loaded_library(text, sdk, windows)
            except (OSError, ValueError) as error:
                status, library = "FAIL", dict(error=str(error))
            row = dict(label=label, cases=cases, mutation=mutation, incomplete_detector=incomplete,
                       status=status, returncode=code, seconds=time.monotonic() - started, library=library,
                       command=cmd, log_sha256=common.sha(lane / "run.log"),
                       events=[line for line in text.splitlines() if line.startswith("MW3_STORAGE_")])
            report["results"].append(row)
            print(json.dumps({k: row[k] for k in ("label", "status", "returncode")}), flush=True)
        _, after = verify_package(args.sdk_report)
        if (after != evidence or common.sha(binary) != report["binary_sha256"]
                or common.snapshot(output / "maintained-source") != source_identity
                or any(common.sha(SOURCE / name) != entry["sha256"] for name, entry in source_identity.items())
                or common.sha(__file__) != report["script_sha256"]):
            raise ValueError("verified source, package or executed binary changed")
        report["status"] = "FAIL" if any(r["status"] == "FAIL" for r in report["results"]) else "PASS"
        report["artifacts"] = artifact_snapshot(output)
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return int(report["status"] != "PASS")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output:
            (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"Profile storage failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
