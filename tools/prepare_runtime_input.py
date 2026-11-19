#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build an isolated initial-input snapshot provider on a verified private XMA SDK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import prepare_runtime_xma as xma
import prepare_runtime_memory as memory
import recompile as common

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "config/toolchains/rexglue-input-snapshot/lock.json"
CPP = "src/hid/sdl3/sdl3_input_driver.cpp"
HEADER = "src/hid/sdl3/sdl3_input_driver.h"


def configuration():
    lock = json.loads(LOCK.read_text())
    parent = json.loads(xma.LOCK.read_text())
    patch = LOCK.parent / lock["patch_path"]
    if (lock.get("schema_version") != 1 or lock.get("profile") != "input-snapshot-v1"
            or lock["commit"] != parent["commit"] or set(lock["source_files"]) != {CPP, HEADER}
            or lock["parent_xma_lock_sha256"] != common.sha(xma.LOCK)
            or common.sha(patch) != lock["patch_sha256"]):
        raise ValueError("input snapshot patch/parent configuration changed")
    return lock, patch


def replacement(windows):
    return "bin/rexhid-sdl3.dll" if windows else "lib/librexhid-sdl3.so"


def verify_source(source, lock):
    files = common.snapshot(source)
    expected = {CPP: lock["derived_source_sha256"], HEADER: lock["source_files"][HEADER],
                "CMakeLists.txt": common.sha(LOCK.parent / "CMakeLists.txt")}
    if set(files) != set(expected) or any(files[name]["sha256"] != value for name, value in expected.items()):
        raise ValueError("derived input source/recipe changed")
    return files


def verify_prepared(root, report_path, allow_sanitized=False):
    lock, patch = configuration()
    receipt = json.loads(report_path.read_text())
    if (receipt.get("status") != "PASS" or receipt.get("profile") != lock["profile"]
            or receipt.get("script_sha256") != common.sha(__file__)
            or receipt.get("lock_sha256") != common.sha(LOCK)
            or receipt.get("patch_sha256") != common.sha(patch)
            or type(receipt.get("provider_sanitizers")) is not bool
            or receipt["provider_sanitizers"] != receipt.get("core_sanitizers")
            or receipt.get("core_sanitizers") and not allow_sanitized):
        raise ValueError("unreviewed or validation-only input snapshot preparation")
    baseline = Path(receipt["baseline_report"])
    if common.sha(baseline) != receipt["baseline_report_sha256"]:
        raise ValueError("input snapshot parent receipt changed")
    _, parent = xma.verify_prepared(root, baseline, allow_sanitized=allow_sanitized)
    if parent != receipt["baseline_identity"] or parent["core_sanitizers"] != receipt["core_sanitizers"]:
        raise ValueError("input snapshot parent/instrumentation changed")
    if receipt["compiler"] != json.loads(baseline.read_text())["compiler"]:
        raise ValueError("input snapshot compiler differs from parent")
    if verify_source(report_path.parent / "source", lock) != receipt["derived_source"]:
        raise ValueError("recorded derived source differs")
    sdk = Path(receipt["sdk_prefix"])
    files = memory.package_files(sdk)
    name = replacement(sys.platform == "win32")
    if (files != receipt["sdk_files"] or receipt.get("replaced_files") != {name: files[name]["sha256"]}
            or {n: v for n, v in files.items() if n != name} != {n: v for n, v in parent["sdk_files"].items() if n != name}
            or files[name]["sha256"] == parent["sdk_files"][name]["sha256"]):
        raise ValueError("input provider or unaffected package artifact changed")
    if common.sha(report_path.parent / "compile_commands.json") != receipt["compile_commands_sha256"]:
        raise ValueError("input provider compile commands changed")
    return sdk, dict(profile=lock["profile"], preparation_sha256=common.sha(report_path),
                     lock_sha256=common.sha(LOCK), patch_sha256=common.sha(patch),
                     derived_source=receipt["derived_source"], compiler=receipt["compiler"],
                     baseline=parent, sdk_files=files, sdk_tree_sha256=common.digest(files),
                     core_sanitizers=receipt["core_sanitizers"], provider_sanitizers=receipt["provider_sanitizers"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path, required=True)
    parser.add_argument("--core-sanitizers", action="store_true")
    args = parser.parse_args()
    output = None
    report = dict(schema_version=1, status="IN_PROGRESS", guest_executed=False, release_package=False,
                  script_sha256=common.sha(__file__), lock_sha256=common.sha(LOCK),
                  core_sanitizers=args.core_sanitizers, provider_sanitizers=args.core_sanitizers)
    try:
        lock, patch = configuration()
        root = common.private_cache(args.root, ROOT / "game")
        baseline = args.baseline_report.resolve()
        sdk, parent = xma.verify_prepared(root, baseline, allow_sanitized=args.core_sanitizers)
        if parent["core_sanitizers"] != args.core_sanitizers:
            raise ValueError("parent instrumentation differs from requested profile")
        if sys.platform == "win32" and args.core_sanitizers:
            raise ValueError("Windows provider/core ASan profile is unsupported")
        output = root / "input-preparations" / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        report.update(profile=lock["profile"], patch_sha256=common.sha(patch), baseline_report=str(baseline),
                      baseline_report_sha256=common.sha(baseline), baseline_identity=parent)
        source = output / "source"
        original = root / "sources/rexglue-xma"
        for name, expected in lock["source_files"].items():
            data = subprocess.check_output(["git", "-C", str(original), "show", lock["commit"] + ":" + name])
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("canonical provider source differs")
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        shutil.copy2(LOCK.parent / "CMakeLists.txt", source / "CMakeLists.txt")
        apply = ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "apply", "--no-index"]
        subprocess.run([*apply, "--check", str(patch.resolve())], cwd=source, check=True, capture_output=True)
        subprocess.run([*apply, str(patch.resolve())], cwd=source, check=True, capture_output=True)
        report["derived_source"] = verify_source(source, lock)
        windows = sys.platform == "win32"
        if windows:
            import prepare_windows_runtime as win
            wlock = json.loads(win.LOCK.read_text())
            clang, report["compiler"] = win.compiler(root, wlock["compiler"], False)
            env, cmake, ninja, report["host_tools"] = win.msvc_environment(wlock, clang)
            compiler = clang / "bin/clang++.exe"
            flags = "-march=x86-64-v2"
            extra = ["-DCMAKE_MAKE_PROGRAM=" + ninja.as_posix(), "-DCMAKE_SHARED_LINKER_FLAGS=-fuse-ld=lld"]
        else:
            if sys.platform != "linux": raise ValueError("unsupported host")
            env, cmake = dict(os.environ), "cmake"
            compiler = Path(shutil.which("clang++-20") or "missing")
            report["compiler"] = dict(sha256=common.sha(compiler), version=subprocess.check_output([compiler, "--version"], text=True).splitlines()[0])
            sanitizer = " -fsanitize=address,undefined -fno-sanitize=vptr -fno-omit-frame-pointer" if args.core_sanitizers else ""
            flags = "-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13" + sanitizer
            extra = ["-DCMAKE_SHARED_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2" + sanitizer]
        if report["compiler"] != json.loads(baseline.read_text())["compiler"]:
            raise ValueError("provider compiler differs from parent")
        build = output / "build"
        commands = [("configure", [cmake, "-S", source, "-B", build, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                     "-DCMAKE_CXX_COMPILER=" + compiler.as_posix(), "-DCMAKE_CXX_FLAGS=" + flags,
                     "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG", "-DCMAKE_PREFIX_PATH=" + sdk.as_posix(),
                     "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON", *extra]),
                    ("build", [cmake, "--build", build, "--parallel", "2"])]
        report["commands"] = []
        for label, command in commands:
            report["commands"].append(list(map(str, command)))
            with (output / (label + ".log")).open("wb") as log:
                subprocess.run(list(map(str, command)), env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        package = output / "sdk"
        shutil.copytree(sdk, package, symlinks=not windows)
        name = replacement(windows)
        shutil.copy2(build / Path(name).name, package / name)
        shutil.copy2(build / "compile_commands.json", output / "compile_commands.json")
        report.update(sdk_prefix=str(package), sdk_files=memory.package_files(package),
                      replaced_files={name: common.sha(package / name)},
                      compile_commands_sha256=common.sha(output / "compile_commands.json"))
        _, after = xma.verify_prepared(root, baseline, allow_sanitized=args.core_sanitizers)
        if parent != after: raise ValueError("parent changed during input preparation")
        report["status"] = "PASS"
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        verify_prepared(root, output / "manifest.json", allow_sanitized=args.core_sanitizers)
        print(json.dumps(dict(status="PASS", report=str(output / "manifest.json"))), flush=True)
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output: (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"Input preparation failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
