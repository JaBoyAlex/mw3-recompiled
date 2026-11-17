#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Compare original synthetic service contracts on the two pinned runtimes.

No game bytes or translated instructions are used. SP/MP cases use only the
verified executable inventory's address geometry. Candidate failures remain
failures, even when they are useful architecture-selection evidence.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import uuid

from prepare import HERE, sha, verify_source, run
from mw2_tools import derive

ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify_inputs import DEFAULT


def classify(returncode, diagnostic):
    if any(s in diagnostic for s in ("ERROR: AddressSanitizer", "ERROR: LeakSanitizer", "runtime error:", "UndefinedBehaviorSanitizer:")):
        return "ERROR"
    passed = "CONFORMANCE_PASS" in diagnostic
    failed = "CONFORMANCE_FAIL:" in diagnostic
    if returncode == 0 and passed and not failed:
        return "PASS"
    if returncode == 1 and failed and not passed:
        return "FAIL"
    return "ERROR"


def geometry(metadata, expected):
    code = [s for s in metadata["sections"] if s["code"]]
    base = metadata["base"]
    size = metadata["size"]
    if not code or base != expected["base"] or size != expected["image_size"]:
        raise ValueError("layout metadata differs from its inventory summary")
    if any(type(n) is not int or n < 0 or n > 2**32 for n in (base,size)) or not size:
        raise ValueError("invalid image/code geometry")
    if any(type(s[k]) is not int or s[k] < 0 or s[k] > 2**32 for s in code for k in ("address","size")):
        raise ValueError("invalid image/code geometry")
    begin = min(s["address"] for s in code)
    end = max(s["address"] + s["size"] for s in code)
    if any(type(n) is not int or n < 0 or n % 4 for n in (base, size, begin, end)) or not base <= begin < end <= base+size <= 2**32:
        raise ValueError("invalid image/code geometry")
    return dict(PPC_IMAGE_BASE=base, PPC_IMAGE_SIZE=size, PPC_CODE_BASE=begin, PPC_CODE_SIZE=end-begin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--sanitizers", action="store_true")
    parser.add_argument("--derived-sdk-report", type=Path, help="verified preparation manifest for the isolated memory derivative")
    args = parser.parse_args()
    output = None
    report = dict(schema_version=1, evidence_class="original-synthetic-runtime-conformance",
                  owned_title_executed=False, host_callback_guest_threads=True, performance_measured=False,
                  script_sha256=sha(__file__), helper_sha256={n: sha(HERE/n) for n in ("prepare.py", "mw2_tools.py")},
                  pins_sha256=sha(HERE / "pins.json"), sanitizers=args.sanitizers, results=[])
    try:
        if platform.system() != "Linux" or platform.machine() != "x86_64":
            raise ValueError("this experiment requires Linux x86-64")
        root = args.root.resolve()
        lock = json.loads((HERE / "pins.json").read_text())
        compiler, _ = run(["clang++-20", "--version"])
        if not re.search(r"clang version " + re.escape(lock["compiler"]) + r"\b", compiler):
            raise ValueError("compiler differs from common profile")
        report.update(compiler=compiler.splitlines()[0], compiler_sha256=sha(shutil.which("clang++-20")))
        sdk = root / "install/rexglue"
        if args.derived_sdk_report:
            prepared = json.loads(args.derived_sdk_report.read_text())
            pin = lock["rexglue_memory_derivative"]
            actual = derive(root / "sources/rexglue-memory", HERE / pin["patch_path"], pin)
            if prepared["status"] != "PASS" or prepared["source"] != actual:
                raise ValueError("derived SDK source/preparation mismatch")
            if prepared.get("core_sanitizers") and not args.sanitizers:
                raise ValueError("sanitized core requires the sanitizer harness")
            report["sdk_core_sanitizers"] = prepared.get("core_sanitizers", False)
            sdk = Path(prepared["sdk_prefix"])
            if any(sha(sdk / "lib" / name) != value for name, value in prepared["final_libraries"].items()):
                raise ValueError("derived SDK library identity mismatch")
            report["derived_sdk_preparation_sha256"] = sha(args.derived_sdk_report)
        for name in ("rexglue-sdk", "mw2-recompiled"):
            verify_source(root / "sources" / name, next(s for s in lock["sources"] if s["name"] == name))
        report["mw2_generator"] = derive(root / "sources/mw2-xenon", root / "sources/mw2-recompiled" / lock["mw2_generator"]["patch_path"], lock["mw2_generator"])
        inventory = json.loads((args.metadata / "report.json").read_text())
        title_manifest = json.loads(DEFAULT.read_text())
        if inventory["identity"] != title_manifest["id"]:
            raise ValueError("inventory identity mismatch")
        layouts = {"synthetic": dict(PPC_IMAGE_BASE=0x82000000, PPC_IMAGE_SIZE=0x100000, PPC_CODE_BASE=0x82090000, PPC_CODE_SIZE=0x10000)}
        for role, name in (("sp", "default.xex"), ("mp", "default_mp.xex")):
            path = args.metadata / (role+"-image.json")
            title = next(t for t in inventory["titles"] if t["role"] == role)
            expected = next(t for t in title_manifest["executables"] if t["name"] == name)
            if title["executable_sha256"] != expected["sha256"] or sha(path) != title["metadata_sha256"]:
                raise ValueError("layout input hash mismatch")
            layouts[role] = geometry(json.loads(path.read_text()), title)
        output = root / "runs" / uuid.uuid4().hex
        output.mkdir(parents=True)
        snapshots = output / "tool-sources"
        snapshots.mkdir()
        for name in ("run_conformance.py","prepare.py","mw2_tools.py","pins.json"):
            shutil.copy2(HERE/name,snapshots/name)
        print(json.dumps(dict(output=str(output), owned_title_executed=False)), flush=True)
        report.update(layouts=layouts, inventory_sha256=sha(args.metadata / "report.json"),
                      sources={str(p.relative_to(HERE)): sha(p) for p in sorted((HERE / "conformance").iterdir()) if p.is_file()},
                      source_commits={s["name"]: s["commit"] for s in lock["sources"] if s["name"] in ("rexglue-sdk", "mw2-recompiled")})
        for layout, values in layouts.items():
            lane = output / layout
            lane.mkdir()
            build = lane / "build"
            command = ["cmake", "-S", HERE / "conformance", "-B", build, "-G", "Ninja",
                       "-DCMAKE_CXX_COMPILER=clang++-20", "-DCMAKE_BUILD_TYPE=Release",
                       "-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13",
                       "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                       "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2",
                       "-DCMAKE_PREFIX_PATH=" + str(sdk),
                       "-DMW2_SOURCE=" + str(root / "sources/mw2-recompiled"),
                       "-DMW2_GENERATOR=" + str(root / "sources/mw2-xenon"),
                       "-DMW3_CONFORMANCE_SANITIZERS=" + ("ON" if args.sanitizers else "OFF")]
            command += [f"-D{k}={hex(v)}" for k, v in values.items()]
            run(command, log=lane / "configure.log")
            run(["cmake", "--build", build, "--parallel", "2"], log=lane / "build.log")
            scenarios = ("memory", "thread-return", "thread-suspended", "thread-terminate", "host-range-collision") if layout == "synthetic" else ("memory",)
            for backend in ("mw2", "rex"):
                binary = build / (backend + "-conformance")
                backend_scenarios = scenarios + (("reload-lifecycle",) if layout == "synthetic" and backend == "rex" else ())
                for scenario in backend_scenarios:
                    for trial in range(3):
                        if scenario == "host-range-collision" and args.sanitizers:
                            report["results"].append(dict(layout=layout,backend=backend,scenario=scenario,trial=trial,
                                                           status="SKIP",reason="fixture host address is occupied by ASan; native profile tests this collision"))
                            continue
                        case = lane / f"{backend}-{scenario}-{trial}"
                        case.mkdir()
                        (case / "config").mkdir()
                        (case / "tmp").mkdir()
                        command = [str(binary), scenario]
                        if backend == "rex":
                            command += ["--app.root=" + str(case / "app"), "--app.user_root=" + str(case / "user"),
                                        "--title.game_root=" + str(case), "--ui.driver=none", "--hid.drivers=none", "--apu.driver=none", "--gpu.driver=none"]
                        env = dict(os.environ, TMPDIR=str(case / "tmp"), XDG_CONFIG_HOME=str(case / "config"),
                                   SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", ASAN_OPTIONS="detect_leaks=1")
                        symbolizer = shutil.which("llvm-symbolizer-20") or shutil.which("llvm-symbolizer-18")
                        if symbolizer: env["ASAN_SYMBOLIZER_PATH"] = symbolizer
                        start = time.monotonic()
                        with (case / "run.log").open("wb") as log:
                            result = subprocess.run(command, cwd=build, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=10)
                        text = (case / "run.log").read_text(errors="replace")
                        row = dict(layout=layout, backend=backend, scenario=scenario, trial=trial,
                                   status=classify(result.returncode, text), returncode=result.returncode,
                                   seconds=time.monotonic()-start, command=command, binary_sha256=sha(binary),
                                   log_sha256=sha(case / "run.log"))
                        report["results"].append(row)
                        (output / "manifest.json").write_text(json.dumps(report, indent=2)+"\n")
                        print(json.dumps({k: row[k] for k in ("layout", "backend", "scenario", "trial", "status")}), flush=True)
            if layout == "synthetic" and not args.sanitizers:
                binary = build / "rex-conformance"
                helper = build / "libview-fault.so"
                report["fault_helper_sha256"] = sha(helper)
                for position in range(1,10):
                    for trial in range(3):
                        case = lane / f"rex-mapping-failure-{position}-{trial}"
                        case.mkdir()
                        (case / "config").mkdir()
                        (case / "tmp").mkdir()
                        command = [str(binary),"mapping-failure-cleanup","--app.root="+str(case/"app"),
                                   "--app.user_root="+str(case/"user"),"--title.game_root="+str(case),
                                   "--ui.driver=none","--hid.drivers=none","--apu.driver=none","--gpu.driver=none"]
                        env = dict(os.environ, LD_PRELOAD=str(helper), MW3_FAIL_MAP_VIEW=str(position),
                                   TMPDIR=str(case/"tmp"), XDG_CONFIG_HOME=str(case/"config"),
                                   SDL_VIDEODRIVER="dummy",SDL_AUDIODRIVER="dummy")
                        with (case/"run.log").open("wb") as log:
                            result = subprocess.run(command,cwd=build,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=10)
                        diagnostic = (case/"run.log").read_text(errors="replace")
                        status = classify(result.returncode,diagnostic)
                        if diagnostic.count(f"FAULT_INJECTION_TRIGGERED:{position}\n") != 1:
                            status = "ERROR"
                        row = dict(layout=layout,backend="rex",scenario="mapping-failure-cleanup",position=position,
                                   trial=trial,status=status,returncode=result.returncode,command=command,
                                   binary_sha256=sha(binary),log_sha256=sha(case/"run.log"))
                        report["results"].append(row)
                        (output/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
                        print(json.dumps({k:row[k] for k in ("backend","scenario","position","trial","status")}),flush=True)
        report["shared_libraries"] = {p.name: sha(p) for p in sorted((output / "synthetic/build").glob("*.so*")) if p.is_file()}
        report["status"] = "FAIL" if any(r["status"] not in ("PASS", "SKIP") for r in report["results"]) else "PASS"
        (output / "manifest.json").write_text(json.dumps(report, indent=2)+"\n")
        return int(report["status"] != "PASS")
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output: (output / "manifest.json").write_text(json.dumps(report, indent=2)+"\n")
        parser.exit(2, f"conformance experiment failed: {type(error).__name__}; inspect private logs\n")


if __name__ == "__main__":
    raise SystemExit(main())
