#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build an isolated packet-lifetime repair on an explicitly verified stop SDK."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import prepare_runtime_memory as memory
import prepare_runtime_stop as stop
import recompile as common

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "config/toolchains/rexglue-xma/lock.json"


def composition(windows):
    lock = json.loads(LOCK.read_text())
    parent, parent_lock = stop.composition(windows)
    patch = LOCK.parent / lock["patch_path"]
    if (lock["commit"] != parent_lock["commit"]
            or lock["parent_stop_lock_sha256"] != common.sha(stop.LOCK)
            or common.sha(patch) != lock["patch_sha256"]):
        raise ValueError("XMA patch/parent mismatch")
    return parent + b"\n" + patch.read_bytes(), lock


def source_identity(root, output, windows, existing=False):
    patch, lock = composition(windows)
    path = output / "combined-xma.patch"
    if path.exists():
        if path.read_bytes() != patch:
            raise ValueError("recorded XMA composition changed")
    elif existing:
        raise ValueError("recorded XMA composition missing")
    else:
        path.write_bytes(patch)
    source = root / "sources/rexglue-xma"
    if existing:
        from mw2_tools import git
        if git(source, "diff", "--quiet", lock["commit"], "--ignore-submodules=none", check=False).returncode == 0:
            raise ValueError("XMA source reset to baseline")
    return common.derive(source, path, dict(commit=lock["commit"], patch_sha256=common.sha(path)))


def replacement(windows):
    return "bin/rexkernel.dll" if windows else "lib/librexkernel.so"


def verify_prepared(root, report_path, allow_sanitized=False):
    receipt = json.loads(report_path.read_text())
    lock = json.loads(LOCK.read_text())
    if (receipt.get("status") != "PASS" or receipt.get("profile") != lock["profile"]
            or receipt.get("xma_lock_sha256") != common.sha(LOCK)
            or receipt.get("script_sha256") != common.sha(__file__)
            or receipt.get("core_sanitizers") and not allow_sanitized):
        raise ValueError("unreviewed or validation-only XMA preparation")
    baseline = Path(receipt["baseline_report"])
    if common.sha(baseline) != receipt["baseline_report_sha256"]:
        raise ValueError("stop receipt changed")
    _, parent = stop.verify_prepared(root, baseline, allow_sanitized=allow_sanitized)
    if parent != receipt["baseline_identity"] or parent["core_sanitizers"] != receipt["core_sanitizers"]:
        raise ValueError("stop baseline/instrumentation changed")
    if receipt["compiler"] != json.loads(baseline.read_text())["compiler"]:
        raise ValueError("compiler identity differs")
    actual = source_identity(root, report_path.parent, sys.platform == "win32", existing=True)
    if actual != receipt["source"]:
        raise ValueError("XMA source changed")
    sdk = Path(receipt["sdk_prefix"])
    files = memory.package_files(sdk)
    changed = replacement(sys.platform == "win32")
    if (files != receipt["sdk_files"]
            or receipt.get("replaced_files") != {changed: files[changed]["sha256"]}
            or {n: v for n, v in files.items() if n != changed}
            != {n: v for n, v in parent["sdk_files"].items() if n != changed}):
        raise ValueError("XMA SDK artifact or unaffected parent file changed")
    return sdk, dict(derivative=actual, xma_profile=lock["profile"], xma_lock_sha256=common.sha(LOCK),
                     stop_lock_sha256=common.sha(stop.LOCK), preparation_sha256=common.sha(report_path),
                     baseline=parent, sdk_files=files, sdk_tree_sha256=common.digest(files),
                     core_sanitizers=receipt["core_sanitizers"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "baseline-report"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--core-sanitizers", action="store_true")
    args = parser.parse_args()
    output = None
    report = dict(schema_version=1, owned_title_executed=False, release_package=False,
                  script_sha256=common.sha(__file__), xma_lock_sha256=common.sha(LOCK),
                  core_sanitizers=args.core_sanitizers)
    try:
        root = common.private_cache(args.root, ROOT / "game")
        output = root / "xma-preparations" / uuid.uuid4().hex
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        baseline = args.baseline_report.resolve()
        sdk, parent = stop.verify_prepared(root, baseline, allow_sanitized=args.core_sanitizers)
        if parent["core_sanitizers"] != args.core_sanitizers:
            raise ValueError("baseline instrumentation differs")
        report.update(baseline_report=str(baseline), baseline_report_sha256=common.sha(baseline), baseline_identity=parent)
        windows = sys.platform == "win32"
        lock = json.loads(LOCK.read_text())
        env = dict(os.environ)
        if windows:
            if args.core_sanitizers:
                raise ValueError("Windows instrumented core is unsupported")
            import prepare_windows_runtime as win
            wlock = json.loads(win.LOCK.read_text())
            clang, report["compiler"] = win.compiler(root, wlock["compiler"], False)
            env, cmake, ninja, report["host_tools"] = win.msvc_environment(wlock, clang)
            cc = (clang / "bin/clang.exe").as_posix()
            cxx = (clang / "bin/clang++.exe").as_posix()
            flags = "-march=x86-64-v2"
            extra = ["-DCMAKE_MAKE_PROGRAM=" + ninja.as_posix(), "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld",
                     "-DCMAKE_SHARED_LINKER_FLAGS=-fuse-ld=lld", "-DVulkan_LIBRARY=" + (root / "vulkan-import/vulkan-1.lib").as_posix()]
        else:
            if sys.platform != "linux":
                raise ValueError("unsupported host")
            cmake, cc, cxx = "cmake", "clang-20", "clang++-20"
            compiler = Path(shutil.which(cxx) or "missing")
            report["compiler"] = dict(sha256=common.sha(compiler), version=subprocess.check_output([compiler, "--version"], text=True).splitlines()[0])
            san = " -fsanitize=address,undefined -fno-sanitize=vptr -fno-omit-frame-pointer" if args.core_sanitizers else ""
            flags = "-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13" + san
            link = "-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2" + san
            extra = ["-DCMAKE_EXE_LINKER_FLAGS=" + link, "-DCMAKE_SHARED_LINKER_FLAGS=" + link,
                     "-DREXGLUE_GCC_INSTALL_DIR=/usr/lib/gcc/x86_64-linux-gnu/13", "-DVulkan_LIBRARY=/usr/lib/x86_64-linux-gnu/libvulkan.so"]
        if report["compiler"] != json.loads(baseline.read_text())["compiler"]:
            raise ValueError("build compiler differs from parent")
        source = root / "sources/rexglue-xma"

        def run(label, command, timeout):
            with (output / (label + ".log")).open("wb") as log:
                subprocess.run(list(map(str, command)), env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout)

        # The source and build caches are shared only by this explicitly serialized lane.
        with common.writer_lock(root, "xma-preparation"):
            if not source.exists():
                if not args.fetch:
                    raise ValueError("isolated XMA source absent; explicit --fetch required")
                run("source-worktree", ["git", "-C", root / "sources/rexglue-sdk", "worktree", "add", "--detach", source, lock["commit"]], 60)
            if args.fetch:
                run("source-submodules", ["git", "-C", source, "submodule", "update", "--init", "--recursive", "--depth", "1", "--jobs", "2"], 900)
            report.update(source=source_identity(root, output, windows), profile=lock["profile"])
            build = root / "build" / ("rexglue-xma-asan" if args.core_sanitizers else "rexglue-xma")
            command = [cmake, "-S", source, "-B", build, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                       "-DCMAKE_C_COMPILER=" + cc, "-DCMAKE_CXX_COMPILER=" + cxx, "-DCMAKE_C_FLAGS=" + flags, "-DCMAKE_CXX_FLAGS=" + flags,
                       "-DCMAKE_C_FLAGS_RELEASE=-O2 -DNDEBUG", "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG",
                       "-DPYTHON_EXECUTABLE=" + sys.executable, "-DREX_OUTPUT_DIR=" + (build / "sdk-output").as_posix(),
                       "-DCMAKE_INSTALL_PREFIX=" + (build / "unused-install-prefix").as_posix(), "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                       "-DREXGLUE_BUILD_TESTS=OFF", "-DREXGLUE_BUILD_PPC_TESTS=OFF", "-DREXGLUE_ENABLE_TRACY=OFF", "-DREXGLUE_REGISTER_PACKAGE=OFF",
                       "-DVulkan_INCLUDE_DIR=" + (root / "sources/headers/include").as_posix(),
                       "-DREXGLUE_VMA_INCLUDE_DIR=" + (root / "sources/vma/include").as_posix(), *extra]
            report["configure_command"] = list(map(str, command))
            run("configure", command, 180)
            print(json.dumps(dict(stage="build", log=str(output / "build.log"))), flush=True)
            run("build", [cmake, "--build", build, "--target", "rexkernel", "--parallel", "2"], 1800)
            package = output / "sdk"
            shutil.copytree(sdk, package, symlinks=not windows)
            name = replacement(windows)
            shutil.copy2(build / "sdk-output" / Path(name).name, package / name)
            shutil.copy2(build / "compile_commands.json", output / "compile_commands.json")
            report.update(sdk_prefix=str(package), sdk_files=memory.package_files(package),
                          replaced_files={name: common.sha(package / name)},
                          compile_commands_sha256=common.sha(output / "compile_commands.json"))
        _, after = stop.verify_prepared(root, baseline, allow_sanitized=args.core_sanitizers)
        if parent != after:
            raise ValueError("parent changed during preparation")
        report["status"] = "PASS"
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        verify_prepared(root, output / "manifest.json", allow_sanitized=args.core_sanitizers)
        print(json.dumps(dict(status="PASS", report=str(output / "manifest.json"))), flush=True)
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output:
            (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"XMA preparation failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
