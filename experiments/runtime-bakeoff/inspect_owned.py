#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Reproduce guarded, private MW3 analysis/code generation for either candidate.

All output is game-derived/private. Exit zero from an upstream generator is
insufficient: ERROR diagnostics fail this preparation step as well.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tomllib
import uuid

from prepare import HERE, sha, verify_source, outside_owned
from mw2_tools import derive

ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify_inputs import DEFAULT, verify
sys.path.insert(0, str(ROOT / "config/analysis"))
from analyze import validate_switches


def generator_errors(text):
    return sum(line.lstrip().startswith(("ERROR:", "Failed:")) for line in text.splitlines())


def invoke(command, log):
    start = time.monotonic()
    with log.open("wb") as stream:
        result = subprocess.run(list(map(str, command)), stdout=stream, stderr=subprocess.STDOUT, timeout=180)
    return dict(returncode=result.returncode, seconds=time.monotonic()-start,
                diagnostic_errors=generator_errors(log.read_text(errors="replace")), command=list(map(str, command)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("root", "owned", "metadata"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--candidate", choices=("rexglue", "mw2"), required=True)
    args = parser.parse_args()
    output = None
    report = dict(schema_version=1, candidate=args.candidate, guest_executed=False,
                  runtime_selected=False, script_sha256=sha(__file__), pins_sha256=sha(HERE / "pins.json"), titles=[])
    try:
        identity = verify(args.owned, json.loads(DEFAULT.read_text()))
        lock = json.loads((HERE / "pins.json").read_text())
        root = args.root.resolve()
        inventory = json.loads((args.metadata / "report.json").read_text())
        if inventory["identity"] != identity["manifest_id"]:
            raise ValueError("inventory title identity mismatch")
        if args.candidate == "rexglue":
            source = root / "sources/rexglue-sdk"
            report["source"] = verify_source(source, next(e for e in lock["sources"] if e["name"] == "rexglue-sdk"))
            tool = source / "out/linux-amd64/rexglue"
        else:
            parent = root / "sources/mw2-recompiled"
            verify_source(parent, next(e for e in lock["sources"] if e["name"] == "mw2-recompiled"))
            source = root / "sources/mw2-xenon"
            report["source"] = derive(source, parent / lock["mw2_generator"]["patch_path"], lock["mw2_generator"])
            tool = root / "build/mw2-tools/XenonRecomp/XenonRecomp"
            analyzer = root / "build/mw2-tools/XenonAnalyse/XenonAnalyse"
            report["analyzer_sha256"] = sha(analyzer)
        report.update(identity=identity, tool_sha256=sha(tool))
        output = root / "runs" / uuid.uuid4().hex
        outside_owned(output, args.owned)
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output), guest_executed=False)), flush=True)
        for role, filename in (("sp", "default.xex"), ("mp", "default_mp.xex")):
            meta_path = args.metadata / (role + "-image.json")
            title = next(t for t in inventory["titles"] if t["role"] == role)
            expected = next(t for t in identity["executables"] if t["name"] == filename)
            if sha(meta_path) != title["metadata_sha256"] or title["executable_sha256"] != expected["sha256"]:
                raise ValueError("metadata/input binding mismatch")
            meta = json.loads(meta_path.read_text())
            lane = output / role
            lane.mkdir()
            generated = lane / "generated"
            generated.mkdir()  # XenonRecomp otherwise dereferences a failed fopen.
            config = lane / "manifest.toml"
            row = dict(role=role, executable_sha256=expected["sha256"], metadata_sha256=sha(meta_path))
            if args.candidate == "rexglue":
                config.write_text('[project]\nname = ' + json.dumps("mw3_" + role + "_experiment") +
                                  '\ngame_root = ' + json.dumps(str(args.owned.resolve())) +
                                  '\n[entrypoint]\nfile_path = ' + json.dumps(str((args.owned / filename).resolve())) +
                                  '\nout_directory_path = ' + json.dumps(str(generated)) + '\n')
                command = [tool, "codegen", config, "--max_file_size_bytes", "1048576",
                           "--max_discovery_iterations", "1000", "--max_vtable_iterations", "1000", "--max_resolve_iterations", "1000"]
            else:
                switch_file = lane / "switches.toml"
                row["analysis"] = invoke([analyzer, (args.owned / filename).resolve(), switch_file], lane / "analysis.log")
                if row["analysis"]["returncode"] or row["analysis"]["diagnostic_errors"]:
                    raise ValueError("analyzer failed; inspect private log")
                row.update(validate_switches(meta, tomllib.loads(switch_file.read_text())))
                row["switch_sha256"] = sha(switch_file)
                content = '[main]\nfile_path = ' + json.dumps(os.path.relpath((args.owned / filename).resolve(), lane)) + '\nout_directory_path = "generated"\nswitch_table_file_path = "switches.toml"\n'
                for helper in meta["helpers"]:
                    if len(helper["candidates"]) != 1 or not helper["decoder_checked"]:
                        raise ValueError("unverified/ambiguous helper")
                    content += helper["family"] + "_address = " + hex(helper["candidates"][0]) + "\n"
                config.write_text(content)
                header = source / "XenonUtils/ppc_context.h"
                row["context_sha256"] = sha(header)
                command = [tool, config, header]
            row["initial_config_sha256"] = sha(config)
            row["codegen"] = invoke(command, lane / "codegen.log")
            row["final_config_sha256"] = sha(config)
            files = [p for p in sorted(generated.rglob("*")) if p.is_file()]
            row.update(output_files=len(files), output_bytes=sum(p.stat().st_size for p in files),
                       generated_snapshot={str(p.relative_to(generated)): sha(p) for p in files})
            row["status"] = "PASS" if files and not row["codegen"]["returncode"] and not row["codegen"]["diagnostic_errors"] else "FAIL"
            report["titles"].append(row)
            (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps({k: row[k] for k in ("role", "status", "output_files")}), flush=True)
        verify(args.owned, json.loads(DEFAULT.read_text()))
        report["status"] = "PASS" if all(t["status"] == "PASS" for t in report["titles"]) else "FAIL"
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return 0 if report["status"] == "PASS" else 1
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output and output.is_dir(): (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"private preparation failed: {type(error).__name__}; inspect private evidence\n")


if __name__ == "__main__":
    raise SystemExit(main())
