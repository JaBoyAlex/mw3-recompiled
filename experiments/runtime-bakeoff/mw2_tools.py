#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build the pinned MW2 project's host-tool patch privately; no title addresses/configuration copied."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

from prepare import HERE, run, sha, verify_source


def git(source, *args, env=None, check=True):
    result = subprocess.run(["git", "-C", str(source), *map(str, args)], env=env, capture_output=True, text=True)
    if check and result.returncode:
        raise ValueError(f"derived-source Git operation failed: {args[0]}")
    return result


def derive(source, patch, pin):
    """Compare actual files with the tree produced from base+patch, not a trusted cache stamp."""
    if sha(patch) != pin["patch_sha256"] or git(source, "rev-parse", "HEAD").stdout.strip() != pin["commit"]:
        raise ValueError("generator base/patch identity mismatch")
    submodules = git(source, "submodule", "status", "--recursive").stdout.splitlines()
    if any(not row.startswith(" ") for row in submodules):
        raise ValueError("generator submodule identity mismatch")
    # Git's temporary index computes the reviewed derivative without changing the
    # source's real index or discarding a contributor's local edits.
    with tempfile.TemporaryDirectory() as temp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temp) / "index"))
        git(source, "read-tree", pin["commit"], env=env)
        git(source, "apply", "--cached", patch, env=env)
        expected = git(source, "write-tree", env=env).stdout.strip()
        if git(source, "ls-files", "--others", "--exclude-standard", env=env).stdout.strip():
            raise ValueError("untracked generator source outside reviewed patch")
        matches = git(source, "diff", "--quiet", "--ignore-submodules=none", env=env, check=False).returncode == 0
        if not matches:
            base_clean = git(source, "diff", "--quiet", pin["commit"], "--ignore-submodules=none", check=False).returncode == 0
            untracked = git(source, "ls-files", "--others", "--exclude-standard").stdout.strip()
            if not base_clean or untracked:
                raise ValueError("generator differs from exact base plus reviewed patch; local edits preserved")
            git(source, "apply", "--check", patch)
            git(source, "apply", patch)
        if git(source, "diff", "--quiet", "--ignore-submodules=none", env=env, check=False).returncode:
            raise ValueError("generator differs from exact base plus reviewed patch; local edits preserved")
    return dict(base_commit=pin["commit"], patch_sha256=pin["patch_sha256"], derived_tree=expected,
                recursive_submodules=submodules)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    logs = None
    report = dict(schema_version=1, guest_executed=False, runtime_selected=False,
                  script_sha256=sha(__file__), helper_sha256=sha(HERE / "prepare.py"), pin_sha256=sha(HERE / "pins.json"))
    try:
        if os.name != "posix" or not 1 <= args.jobs <= 2:
            raise ValueError("use the bounded Linux environment and one/two build workers")
        root = args.root.resolve()
        logs = root / "runs" / uuid.uuid4().hex
        logs.mkdir(parents=True)
        print(json.dumps(dict(log_directory=str(logs), guest_executed=False)), flush=True)
        lock = json.loads((HERE / "pins.json").read_text())
        parent = next(x for x in lock["sources"] if x["name"] == "mw2-recompiled")
        verify_source(root / "sources/mw2-recompiled", parent)
        pin = lock["mw2_generator"]
        patch = root / "sources/mw2-recompiled" / pin["patch_path"]
        source = root / "sources/mw2-xenon"
        if not source.exists():
            if not args.fetch: raise ValueError("derived source missing; explicit --fetch required")
            run(["git", "init", source], log=logs / "init.log")
            run(["git", "-C", source, "remote", "add", "origin", pin["url"]])
            run(["git", "-C", source, "fetch", "--depth", "1", "origin", pin["commit"]], log=logs / "fetch.log")
            run(["git", "-C", source, "checkout", "--detach", pin["commit"]], log=logs / "checkout.log")
        if args.fetch:
            run(["git", "-C", source, "submodule", "update", "--init", "--recursive", "--depth", "1", "--jobs", "2"], log=logs / "submodules.log")
        report["generator"] = derive(source, patch, pin)
        compiler, _ = run(["clang++-20", "--version"])
        if not re.search(r"clang version " + re.escape(lock["compiler"]) + r"\b", compiler):
            raise ValueError("compiler differs from common profile")
        report.update(compiler=compiler.splitlines()[0], compiler_sha256=sha(shutil.which("clang++-20")))
        if args.build:
            build = root / "build/mw2-tools"
            _, report["configure_seconds"] = run(["cmake", "-S", source, "-B", build, "-G", "Ninja",
                "-DCMAKE_C_COMPILER=clang-20", "-DCMAKE_CXX_COMPILER=clang++-20", "-DCMAKE_BUILD_TYPE=Release",
                f"-DCMAKE_CXX_FLAGS={lock['common_cxx_flags']} --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13",
                f"-DCMAKE_CXX_FLAGS_RELEASE={lock['common_release_flags']}",
                f"-DCMAKE_C_FLAGS_RELEASE={lock['common_release_flags']}",
                "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2"], log=logs / "configure.log")
            _, report["build_seconds"] = run(["cmake", "--build", build, "--target", "XenonAnalyse", "XenonRecomp", "--parallel", args.jobs], log=logs / "build.log")
            report["tools"] = {name: sha(build / name / name) for name in ("XenonAnalyse", "XenonRecomp")}
        report["status"] = "PASS"
        (logs / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(dict(status="PASS", guest_executed=False, derived_tree=report["generator"]["derived_tree"])))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        if logs:
            report.update(status="FAIL", error=str(error))
            (logs / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(1, f"MW2 tool preparation failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
