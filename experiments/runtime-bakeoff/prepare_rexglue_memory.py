#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build a private ReXGlue core derivative without changing the baseline SDK.

Reuses the baseline package's unchanged components, replacing only core shared
libraries built from the exact reviewed derivative. This is not a release SDK.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import uuid

from prepare import HERE, sha, run, verify_source
from mw2_tools import derive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--core-sanitizers", action="store_true",
                        help="instrument base/PPC/kernel for validation; never use this package for code generation")
    args = parser.parse_args()
    root = args.root.resolve()
    output = root / "runs" / uuid.uuid4().hex
    output.mkdir(parents=True)
    report = dict(schema_version=1, guest_executed=False, release_package=False,
                  core_sanitizers=args.core_sanitizers, codegen_compatible=not args.core_sanitizers,
                  script_sha256=sha(__file__), pins_sha256=sha(HERE / "pins.json"))
    print(json.dumps(dict(output=str(output), guest_executed=False)), flush=True)
    try:
        if shutil.disk_usage(root).free < 10*1024**3:
            raise ValueError("less than 10 GiB available")
        lock = json.loads((HERE / "pins.json").read_text())
        entry = next(e for e in lock["sources"] if e["name"] == "rexglue-sdk")
        baseline = root / "sources/rexglue-sdk"
        verify_source(baseline, entry)
        source = root / "sources/rexglue-memory"
        if not source.exists():
            run(["git", "-C", baseline, "worktree", "add", "--detach", source, entry["commit"]], log=output / "worktree.log")
        if args.fetch:
            run(["git", "-C", source, "submodule", "update", "--init", "--recursive", "--depth", "1", "--jobs", "2"], log=output / "submodules.log")
        pin = lock["rexglue_memory_derivative"]
        report["source"] = derive(source, HERE / pin["patch_path"], pin)
        compiler, _ = run(["clang++-20", "--version"])
        if not re.search(r"clang version " + re.escape(lock["compiler"]) + r"\b", compiler):
            raise ValueError("compiler differs from common profile")
        report.update(compiler=compiler.splitlines()[0], compiler_sha256=sha(shutil.which("clang++-20")))
        build = root / ("build/rexglue-memory-asan" if args.core_sanitizers else "build/rexglue-memory")
        sdk_output = build / "sdk-output"
        sanitizer_flags = " -fsanitize=address,undefined -fno-sanitize=vptr -fno-omit-frame-pointer" if args.core_sanitizers else ""
        linker_flags = "-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2" + sanitizer_flags
        command = ["cmake", "-S", source, "-B", build, "-G", "Ninja",
                   "-DCMAKE_C_COMPILER=clang-20", "-DCMAKE_CXX_COMPILER=clang++-20", "-DCMAKE_BUILD_TYPE=Release",
                   "-DCMAKE_CXX_FLAGS=" + lock["common_cxx_flags"] + sanitizer_flags, "-DCMAKE_C_FLAGS=" + lock["common_cxx_flags"] + sanitizer_flags,
                   "-DCMAKE_CXX_FLAGS_RELEASE=" + lock["common_release_flags"], "-DCMAKE_C_FLAGS_RELEASE=" + lock["common_release_flags"],
                   "-DCMAKE_EXE_LINKER_FLAGS=" + linker_flags,
                   "-DCMAKE_SHARED_LINKER_FLAGS=" + linker_flags,
                   "-DREX_OUTPUT_DIR=" + str(sdk_output),
                   "-DREXGLUE_GCC_INSTALL_DIR=/usr/lib/gcc/x86_64-linux-gnu/13",
                   "-DREXGLUE_BUILD_TESTS=OFF", "-DREXGLUE_BUILD_PPC_TESTS=OFF", "-DREXGLUE_ENABLE_TRACY=OFF", "-DREXGLUE_REGISTER_PACKAGE=OFF",
                   "-DVulkan_INCLUDE_DIR=" + str(root / "sources/headers/include"),
                   "-DVulkan_LIBRARY=/usr/lib/x86_64-linux-gnu/libvulkan.so",
                   "-DREXGLUE_VMA_INCLUDE_DIR=" + str(root / "sources/vma/include")]
        report["configure_command"] = list(map(str, command))
        _, report["configure_seconds"] = run(command, log=output / "configure.log")
        _, report["build_seconds"] = run(["cmake", "--build", build, "--target", "rexkernel", "--parallel", "2"], log=output / "build.log", timeout=1200)
        # A fresh prefix per experiment preserves both baseline and previous runs.
        package = output / "sdk"
        shutil.copytree(root / "install/rexglue", package)
        changed = {}
        for name in ("librexbase.so", "librexppc.so", "librexkernel.so"):
            library = sdk_output / name
            shutil.copy2(library, package / "lib" / library.name)
            changed[library.name] = sha(library)
        if "librexkernel.so" not in changed:
            raise ValueError("derived core library missing")
        report.update(status="PASS", sdk_prefix=str(package), replaced_libraries=changed,
                      final_libraries={p.name: sha(p) for p in sorted((package / "lib").glob("*.so*")) if p.is_file()})
        (output / "manifest.json").write_text(json.dumps(report, indent=2)+"\n")
        print(json.dumps(dict(status="PASS", sdk_prefix=str(package), replaced_libraries=changed)), flush=True)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        (output / "manifest.json").write_text(json.dumps(report, indent=2)+"\n")
        parser.exit(2, f"derived core preparation failed: {type(error).__name__}; inspect private logs\n")


if __name__ == "__main__":
    raise SystemExit(main())
