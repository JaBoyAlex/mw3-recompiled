#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build an isolated allocation-import safety repair on a verified XMA SDK."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import prepare_runtime_memory as memory
import prepare_runtime_xma as parent_profile
import recompile as common

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "config/toolchains/rexglue-memory-imports/lock.json"


def helpers():
    names = ("tools/recompile.py", "tools/prepare_runtime_xma.py", "tools/prepare_runtime_stop.py",
             "tools/prepare_runtime_memory.py", "tools/prepare_windows_runtime.py",
             "experiments/runtime-bakeoff/mw2_tools.py", "experiments/runtime-bakeoff/prepare.py")
    return {name: common.sha(ROOT / name) for name in names}


def composition(windows):
    lock = json.loads(LOCK.read_text())
    parent, parent_lock = parent_profile.composition(windows)
    patch = LOCK.parent / lock["patch_path"]
    if (lock.get("schema_version") != 1 or lock.get("profile") != "memory-imports-v1"
            or lock["source_path"] != "src/kernel/xboxkrnl/xboxkrnl_memory.cpp"
            or lock["commit"] != parent_lock["commit"]
            or lock["parent_xma_lock_sha256"] != common.sha(parent_profile.LOCK)
            or common.sha(patch) != lock["patch_sha256"]
            or common.sha(LOCK.parent / "LICENSE.ReXGlue") != lock["license_sha256"]):
        raise ValueError("allocation-import patch/parent mismatch")
    return parent + b"\n" + patch.read_bytes(), lock


def source_identity(root, output, windows, existing=False):
    patch, lock = composition(windows)
    path = output / "combined-memory-imports.patch"
    if path.exists():
        if path.read_bytes() != patch:
            raise ValueError("recorded allocation-import composition changed")
    elif existing:
        raise ValueError("recorded allocation-import composition missing")
    else:
        path.write_bytes(patch)
    source = common.no_symlink_path(root / "sources/rexglue-memory-imports")
    if existing:
        from mw2_tools import git
        if git(source, "diff", "--quiet", lock["commit"], "--ignore-submodules=none", check=False).returncode == 0:
            raise ValueError("allocation-import source reset to baseline")
    identity = common.derive(source, path, dict(commit=lock["commit"], patch_sha256=common.sha(path)))
    expected = {**lock["contract_files"], lock["source_path"]: lock["derived_source_sha256"],
                "LICENSE": lock["license_sha256"]}
    if any(common.sha(source / name) != value for name, value in expected.items()):
        raise ValueError("allocation-import source/contract/license differs")
    return identity


def replacement(windows):
    return "bin/rexkernel.dll" if windows else "lib/librexkernel.so"


def compiler_identity(root):
    if sys.platform == "win32":
        import prepare_windows_runtime as win
        return win.compiler(root, json.loads(win.LOCK.read_text())["compiler"], False)[1]
    path = Path(shutil.which("clang++-20") or "missing")
    return dict(sha256=common.sha(path), version=subprocess.check_output(
        [path, "--version"], text=True).splitlines()[0])


def verify_prepared(root, report_path, allow_sanitized=False):
    receipt = json.loads(report_path.read_text())
    _, lock = composition(sys.platform == "win32")
    if (type(receipt.get("schema_version")) is not int or receipt["schema_version"] != 1 or receipt.get("status") != "PASS"
            or receipt.get("profile") != lock["profile"]
            or receipt.get("owned_title_executed") is not False or receipt.get("release_package") is not False
            or receipt.get("memory_imports_lock_sha256") != common.sha(LOCK)
            or receipt.get("script_sha256") != common.sha(__file__)
            or receipt.get("helper_sha256") != helpers()
            or type(receipt.get("core_sanitizers")) is not bool
            or receipt.get("core_sanitizers") and not allow_sanitized):
        raise ValueError("unreviewed or validation-only allocation-import preparation")
    baseline = Path(receipt["baseline_report"])
    if common.sha(baseline) != receipt["baseline_report_sha256"]:
        raise ValueError("XMA receipt changed")
    _, parent = parent_profile.verify_prepared(root, baseline, allow_sanitized=allow_sanitized)
    if parent != receipt["baseline_identity"] or parent["core_sanitizers"] != receipt["core_sanitizers"]:
        raise ValueError("XMA baseline/instrumentation changed")
    if receipt["compiler"] != json.loads(baseline.read_text())["compiler"]:
        raise ValueError("compiler identity differs")
    if receipt["compiler"] != compiler_identity(root):
        raise ValueError("current compiler differs")
    actual = source_identity(root, report_path.parent, sys.platform == "win32", existing=True)
    if actual != receipt["source"]:
        raise ValueError("allocation-import source changed")
    sdk = Path(receipt["sdk_prefix"])
    files = memory.package_files(sdk)
    changed = replacement(sys.platform == "win32")
    if (files != receipt["sdk_files"]
            or receipt.get("replaced_files") != {changed: files[changed]["sha256"]}
            or files[changed]["sha256"] == parent["sdk_files"][changed]["sha256"]
            or {n: v for n, v in files.items() if n != changed}
            != {n: v for n, v in parent["sdk_files"].items() if n != changed}):
        raise ValueError("allocation-import SDK artifact or unaffected parent file changed")
    if common.sha(report_path.parent / "compile_commands.json") != receipt["compile_commands_sha256"]:
        raise ValueError("compile command record changed")
    for name, value in receipt["log_sha256"].items():
        if name not in ("configure.log", "build.log") or common.sha(report_path.parent / name) != value:
            raise ValueError("preparation log changed")
    if set(receipt["log_sha256"]) != {"configure.log", "build.log"}:
        raise ValueError("preparation log missing")
    return sdk, dict(derivative=actual, memory_imports_profile=lock["profile"], memory_imports_lock_sha256=common.sha(LOCK),
                     parent_xma_lock_sha256=common.sha(parent_profile.LOCK), preparation_sha256=common.sha(report_path),
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
                  script_sha256=common.sha(__file__), helper_sha256=helpers(), memory_imports_lock_sha256=common.sha(LOCK),
                  core_sanitizers=args.core_sanitizers)
    try:
        root = common.private_cache(args.root, ROOT / "game")
        baseline = args.baseline_report.resolve()
        sdk, parent = parent_profile.verify_prepared(root, baseline, allow_sanitized=args.core_sanitizers)
        if parent["core_sanitizers"] != args.core_sanitizers:
            raise ValueError("baseline instrumentation differs")
        _, lock = composition(sys.platform == "win32")
        original = root / "sources/rexglue-xma"
        if common.sha(original / lock["source_path"]) != lock["parent_source_sha256"]:
            raise ValueError("original import source differs")
        output = common.no_symlink_path(root / "memory-imports-preparations" / uuid.uuid4().hex)
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
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
        source = common.no_symlink_path(root / "sources/rexglue-memory-imports")

        def run(label, command, timeout):
            with (output / (label + ".log")).open("wb") as log:
                subprocess.run(list(map(str, command)), env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=timeout)

        # The source and build caches are shared only by this explicitly serialized lane.
        with common.writer_lock(root, "memory-imports-preparation"):
            if not source.exists():
                if not args.fetch:
                    raise ValueError("isolated allocation-import source absent; explicit --fetch required")
                run("source-worktree", ["git", "-C", root / "sources/rexglue-sdk", "worktree", "add", "--detach", source, lock["commit"]], 60)
            if args.fetch:
                run("source-submodules", ["git", "-C", source, "submodule", "update", "--init", "--recursive", "--depth", "1", "--jobs", "2"], 900)
            report.update(source=source_identity(root, output, windows), profile=lock["profile"])
            build = common.no_symlink_path(root / "build" / ("rexglue-memory-imports-asan" if args.core_sanitizers else "rexglue-memory-imports"))
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
                          compile_commands_sha256=common.sha(output / "compile_commands.json"),
                          log_sha256={n: common.sha(output / n) for n in ("configure.log", "build.log")})
        _, after = parent_profile.verify_prepared(root, baseline, allow_sanitized=args.core_sanitizers)
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
        parser.exit(2, f"allocation-import preparation failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
