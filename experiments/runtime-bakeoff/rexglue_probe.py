#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Compile private ReXGlue output and optionally stop at its first guest import.

Not a game launcher. Every function import must bind to a diagnostic stop before
the title thread may start. No imported function is approved by this experiment.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from prepare import HERE, sha, outside_owned

ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify_inputs import verify, DEFAULT


def make_traps(metadata, prefix):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", prefix):
        raise ValueError("invalid generated prefix")
    records = [row for lib in metadata["import_audit"]["libraries"] for row in lib["records"]]
    if any(r["type"] not in (0, 1) or r["export_kind"] not in ("kFunction", "kVariable")
           or r["type"] == 1 and r["export_kind"] != "kFunction" for r in records):
        raise ValueError("unknown/malformed import cannot be skipped")
    rows = [row for row in records if row["type"] == 1]
    if not rows or len({r["address"] for r in rows}) != len(rows):
        raise ValueError("empty/duplicate import thunk map")
    names = {r["export_name"] for r in rows}
    if any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", n) for n in names):
        raise ValueError("invalid import identifier")
    result = [f'#include "{prefix}_pch.h"', '#include <rex/kernel/title_runtime.h>',
              '#include <cstdio>', '#include <cstdlib>']
    for name in sorted(names):
        result.append('extern "C" void __imp__' + name + '(PPCContext& ctx, u8*) { '
                      'std::fputs("MW3_PROBE_UNREVIEWED_IMPORT:' + name + '", stderr); '
                      'std::fprintf(stderr, " lr=%llx", static_cast<unsigned long long>(ctx.lr)); '
                      'std::fputc(10, stderr); std::fflush(stderr); std::_Exit(86); }')
    result.append('bool VerifyProbeImportStops(rex::kernel::TitleRuntime& runtime) {')
    for row in sorted(rows, key=lambda x: x["address"]):
        if type(row["address"]) is not int or not 0 <= row["address"] <= 0xffffffff or row["address"] % 4:
            raise ValueError("invalid import thunk address")
        name = row["export_name"]
        result.append('{ auto fn = runtime.FindFunction(' + hex(row["address"]) + '); '
                      'if (!fn || *fn != &__imp__' + name + ') { std::fputs("MW3_PROBE_UNBOUND_IMPORT:' +
                      name + '", stderr); std::fputc(10, stderr); return false; } }')
    result.append('return true; }')
    return '\n'.join(result) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("owned", "generated", "metadata", "sdk", "output-root"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--role", required=True, choices=("sp", "mp"))
    parser.add_argument("--execute", action="store_true", help="bounded entry/import stop only")
    args = parser.parse_args()
    out = args.output_root.resolve() / uuid.uuid4().hex
    report = dict(schema_version=1, guest_executed=False, playable=False, runtime_selected=False,
                  script_sha256=sha(__file__), role=args.role)
    try:
        outside_owned(out, args.owned)
        identity = verify(args.owned, json.loads(DEFAULT.read_text()))
        inventory = json.loads((args.metadata / "report.json").read_text())
        title = next(t for t in inventory["titles"] if t["role"] == args.role)
        meta_path = args.metadata / (args.role + "-image.json")
        filename = "default.xex" if args.role == "sp" else "default_mp.xex"
        expected = next(x for x in identity["executables"] if x["name"] == filename)
        if inventory["identity"] != identity["manifest_id"] or title["executable_sha256"] != expected["sha256"] or sha(meta_path) != title["metadata_sha256"]:
            raise ValueError("owned executable/inventory binding mismatch")
        metadata = json.loads(meta_path.read_text())
        prefix = "mw3_" + args.role + "_experiment"
        generated = args.generated.resolve()
        if not (generated / (prefix + "_init.h")).is_file():
            raise ValueError("unexpected generated prefix/output")
        # Snapshot records exact artifacts compiled; source build/codegen manifests
        # remain separate provenance. A snapshot alone does not certify generation.
        report.update(identity=identity, metadata_sha256=sha(meta_path),
                      generated_snapshot={str(p.relative_to(generated)): sha(p) for p in sorted(generated.rglob("*")) if p.is_file()},
                      host_sources={p.name: sha(p) for p in (HERE / "rexglue-host").iterdir() if p.is_file()},
                      sdk_libraries={p.name: sha(p) for p in sorted((args.sdk / "lib").glob("*.so*")) if p.is_file()})
        out.mkdir(parents=True)
        traps = out / "traps.cpp"
        traps.write_text(make_traps(metadata, prefix))
        report["traps_sha256"] = sha(traps)
        print(json.dumps(dict(output=str(out), guest_executed=False)), flush=True)
        commands = [["cmake", "-S", str(HERE / "rexglue-host"), "-B", str(out / "build"), "-G", "Ninja",
                     "-DCMAKE_CXX_COMPILER=clang++-20", "-DCMAKE_BUILD_TYPE=Release",
                     "-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13",
                     "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG",
                     "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2",
                     "-DCMAKE_PREFIX_PATH=" + str(args.sdk.resolve()),
                     "-DMW3_GENERATED_DIR=" + str(generated), "-DMW3_GENERATED_PREFIX=" + prefix,
                     "-DMW3_PRIVATE_TRAPS=" + str(traps)],
                    ["cmake", "--build", str(out / "build"), "--parallel", "2"]]
        report["commands"] = commands
        for i, command in enumerate(commands):
            with (out / f"build-{i}.log").open("wb") as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=1800, check=True)
        binary = out / "build/mw3-entry-probe"
        report.update(binary_sha256=sha(binary), build_status="PASS")
        if args.execute:
            profile = out / "profile"
            profile.mkdir()
            (out / "tmp").mkdir()
            (out / "config").mkdir()
            env = dict(os.environ, XDG_CONFIG_HOME=str(out / "config"), TMPDIR=str(out / "tmp"),
                       SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
            # Never point writable title roots at the read-only owner's files.
            command = [str(binary), "--kernel.headless=true", "--title.game_root=" + str(args.owned.resolve()),
                       "--title.entry=" + filename, "--app.root=" + str(profile), "--app.user_root=" + str(profile / "user"),
                       "--ui.driver=none", "--hid.drivers=none", "--apu.driver=none", "--gpu.driver=none"]
            report["execution_command"] = command
            with (out / "execution.log").open("wb") as log:
                start = time.monotonic()
                result = subprocess.run(command, cwd=out / "build", env=env, stdout=log, stderr=subprocess.STDOUT, timeout=20)
            diagnostic = (out / "execution.log").read_text(errors="replace")
            reached = result.returncode == 86 and "MW3_PROBE_IMAGE_LOADED" in diagnostic and "MW3_PROBE_UNREVIEWED_IMPORT:" in diagnostic
            report.update(execution_returncode=result.returncode, execution_seconds=time.monotonic()-start,
                          guest_executed=reached, stop="unreviewed-import" if reached else "before-confirmed-import-stop",
                          execution_log_sha256=sha(out / "execution.log"))
        verify(args.owned, json.loads(DEFAULT.read_text()))
        report["status"] = "PASS" if not args.execute or report["guest_executed"] else "INCOMPLETE"
        (out / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: report[k] for k in ("status", "guest_executed", "playable")}))
        return 0 if report["status"] == "PASS" else 1
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError) as error:
        report.update(status="FAIL", error=str(error))
        if out.exists(): (out / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"entry probe failed; inspect private evidence: {type(error).__name__}\n")


if __name__ == "__main__":
    raise SystemExit(main())
