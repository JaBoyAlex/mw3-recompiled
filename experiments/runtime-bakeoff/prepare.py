#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Prepare pinned, private Linux runtime experiments; no game inputs or guest execution."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import time
import uuid

HERE = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command, *, cwd=None, log=None, timeout=1800):
    start = time.monotonic()
    if log:
        with log.open("wb") as stream:
            result = subprocess.run(list(map(str, command)), cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        output = ""
    else:
        result = subprocess.run(list(map(str, command)), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        output = result.stdout.decode(errors="replace")
    if result.returncode:
        raise ValueError(f"command failed ({result.returncode}); inspect private log {log.name if log else 'not captured'}")
    return output, time.monotonic() - start


def verify_source(path, entry):
    commit, _ = run(["git", "-C", path, "rev-parse", "HEAD"])
    dirty, _ = run(["git", "-C", path, "status", "--porcelain"])
    if commit.strip() != entry["commit"] or dirty.strip():
        raise ValueError(f"source identity/cleanliness mismatch: {entry['name']}")
    submodules, _ = run(["git", "-C", path, "submodule", "status", "--recursive"])
    if any(not row.startswith(" ") for row in submodules.splitlines()):
        raise ValueError(f"submodule identity/uninitialized source: {entry['name']}")
    return dict(name=entry["name"], commit=commit.strip(), recursive_submodules=submodules.splitlines())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="private cache, preferably on WSL's Linux filesystem")
    parser.add_argument("--fetch", action="store_true", help="fetch only exact locked source commits/submodules")
    parser.add_argument("--configure-rexglue", action="store_true")
    parser.add_argument("--build-rexglue", action="store_true")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    logs = None
    report = dict(schema_version=1, experiment="host-preparation-only", guest_executed=False, runtime_selected=False,
                  pin_sha256=sha(HERE / "pins.json"), preparation_sha256=sha(__file__), sources=[], performance_result="not-measured")
    try:
        if platform.system() != "Linux" or platform.machine() != "x86_64" or not 1 <= args.jobs <= 2:
            raise ValueError("this bounded experiment uses Linux x86-64 and one or two build workers")
        if args.build_rexglue and not args.configure_rexglue:
            raise ValueError("build requires a locked reconfigure in the same invocation")
        lock = json.loads((HERE / "pins.json").read_text())
        root = args.root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        logs = root / "runs" / uuid.uuid4().hex
        logs.mkdir(parents=True)
        print(json.dumps(dict(log_directory=str(logs), guest_executed=False)), flush=True)
        free = shutil.disk_usage(root).free
        if Path("/mnt/c").is_dir(): free = min(free, shutil.disk_usage("/mnt/c").free)
        if free < 10 * 1024**3:
            raise ValueError("less than 10 GiB available for bounded runtime experiments")
        observations = []
        for entry in lock["sources"]:
            source = root / "sources" / entry["name"]
            if not source.exists():
                if not args.fetch:
                    raise ValueError(f"source missing: {entry['name']}; explicit --fetch required")
                run(["git", "init", source], log=logs / f"{entry['name']}-init.log")
                run(["git", "-C", source, "remote", "add", "origin", entry["url"]])
                run(["git", "-C", source, "fetch", "--depth", "1", "origin", entry["commit"]], log=logs / f"{entry['name']}-fetch.log")
                run(["git", "-C", source, "checkout", "--detach", entry["commit"]], log=logs / f"{entry['name']}-checkout.log")
            if args.fetch and entry["submodules"]:
                run(["git", "-C", source, "submodule", "update", "--init", "--recursive", "--depth", "1", "--jobs", "2"], log=logs / f"{entry['name']}-submodules.log")
            observations.append(verify_source(source, entry))
            report["sources"] = observations
        compiler, _ = run(["clang++-20", "--version"])
        if not re.search(r"clang version " + re.escape(lock["compiler"]) + r"\b", compiler):
            raise ValueError("experiment compiler version differs from lock")
        report.update(compiler=compiler.splitlines()[0], compiler_sha256=sha(shutil.which("clang++-20")))
        gcc_dir = Path("/usr/lib/gcc/x86_64-linux-gnu/13")
        if not gcc_dir.is_dir():
            raise ValueError("common GCC 13 standard library not available")
        build = root / "build" / "rexglue-release"
        configure_seconds = build_seconds = None
        if args.configure_rexglue:
            _, configure_seconds = run(["cmake", "-S", root / "sources/rexglue-sdk", "-B", build, "-G", "Ninja",
                "-DCMAKE_C_COMPILER=clang-20", "-DCMAKE_CXX_COMPILER=clang++-20", "-DCMAKE_BUILD_TYPE=Release",
                f"-DCMAKE_CXX_FLAGS={lock['common_cxx_flags']}", f"-DCMAKE_C_FLAGS={lock['common_cxx_flags']}",
                f"-DCMAKE_CXX_FLAGS_RELEASE={lock['common_release_flags']}", f"-DCMAKE_C_FLAGS_RELEASE={lock['common_release_flags']}",
                "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2",
                "-DCMAKE_SHARED_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2",
                f"-DREXGLUE_GCC_INSTALL_DIR={gcc_dir}", "-DREXGLUE_BUILD_TESTS=ON", "-DREXGLUE_BUILD_PPC_TESTS=OFF",
                "-DREXGLUE_ENABLE_TRACY=OFF", "-DREXGLUE_REGISTER_PACKAGE=OFF",
                f"-DVulkan_INCLUDE_DIR={root / 'sources/headers/include'}",
                "-DVulkan_LIBRARY=/usr/lib/x86_64-linux-gnu/libvulkan.so",
                f"-DREXGLUE_VMA_INCLUDE_DIR={root / 'sources/vma/include'}",
                f"-DCMAKE_INSTALL_PREFIX={root / 'install/rexglue'}"], log=logs / "rexglue-configure.log")
            cache = (build / "CMakeCache.txt").read_text()
            if "_REXGLUE_STDLIB_DETECTED_RELEASE:INTERNAL=13" not in cache:
                raise ValueError("configured standard library release differs from common profile")
        if args.build_rexglue:
            if not (build / "CMakeCache.txt").exists():
                raise ValueError("configure the locked ReXGlue build first")
            _, build_seconds = run(["cmake", "--build", build, "--parallel", args.jobs], log=logs / "rexglue-build.log", timeout=3600)
        report.update(status="PASS", standard_library_release=lock["stdlib_release"],
                      configure_seconds=configure_seconds, build_seconds=build_seconds)
        (logs / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(dict(status="PASS", log_directory=str(logs), sources=len(observations), guest_executed=False,
                             configure_seconds=configure_seconds, build_seconds=build_seconds), indent=2))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        if logs is not None:
            report.update(status="FAIL", error=str(error))
            (logs / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(1, f"runtime preparation failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
