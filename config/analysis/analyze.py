#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Reproduce private, identity-guarded MW3 image/switch metadata on Ubuntu/WSL.

Does not execute guest code, dump decrypted images or claim control-flow completeness.
"""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from verify_inputs import verify, DEFAULT
from prepare_toolchain import verify_sources, sha256, text_sha256


def validate_switches(metadata, switches):
    code = [row for row in metadata["sections"] if row["code"]]

    def contains(address):
        return type(address) is int and any(row["address"] <= address < row["address"] + row["size"] for row in code)
    if not contains(metadata["entry_point"]):
        raise ValueError("entry point outside executable sections")
    tables = switches.get("switch", [])
    bases = set()
    for table in tables:
        if table["base"] in bases or not contains(table["base"]):
            raise ValueError("duplicate switch or dispatch outside code")
        bases.add(table["base"])
        if type(table["r"]) is not int or not 0 <= table["r"] <= 31 or not table["labels"]:
            raise ValueError("invalid switch register or empty targets")
        if not all(contains(label) for label in table["labels"]):
            raise ValueError("switch target outside code")
    return dict(switch_tables=len(tables), switch_targets=sum(len(t["labels"]) for t in tables))


def summarize_mapping(metadata):
    expected = {f"{operation}{family}" for operation in ("save", "rest")
                for family in ("gprlr_14", "fpr_14", "vmx_14", "vmx_64")}
    helpers = metadata["helpers"]
    if len(helpers) != 8 or {row["family"] for row in helpers} != expected:
        raise ValueError("missing or duplicate helper family report")
    if not all(row["decoder_checked"] for row in helpers):
        raise ValueError("helper instruction decoder verification missing")
    pdata, flow = metadata["pdata"], metadata["flow_scan"]
    if pdata["entries"] != len(pdata["functions"]) or sum(pdata["type_counts"]) != pdata["entries"]:
        raise ValueError("inconsistent pdata counts")
    helper_entries = {base + reg * row["stride"] for row in helpers if len(row["candidates"]) == 1
                      for base in row["candidates"] for reg in range(row["last_register"] - row["first_register"] + 1)}
    declared_entries = helper_entries | {row["address"] for row in pdata["functions"]} | {
        row["address"] for row in metadata["resolved_import_symbols"]}
    unclassified = {row["target"] for row in flow["immediate_calls"] if row["target"] not in declared_entries}
    return dict(unique_helper_families=sum(len(row["candidates"]) == 1 for row in helpers),
                missing_helper_families=sum(not row["candidates"] for row in helpers),
                ambiguous_helper_families=sum(len(row["candidates"]) > 1 for row in helpers),
                pdata_entries=pdata["entries"], pdata_handler_entries=pdata["type_counts"][3],
                pdata_covered_code_bytes=pdata["covered_code_bytes"], code_section_bytes=pdata["code_bytes"],
                immediate_call_words=len(flow["immediate_calls"]),
                immediate_calls_outside_code=sum(not row["target_in_code"] for row in flow["immediate_calls"]),
                helper_direct_call_words=sum(row["target"] in helper_entries for row in flow["immediate_calls"]),
                direct_call_targets_without_declared_entry=len(unclassified),
                unresolved_indirect_sites=len(flow["unresolved_indirect_sites"]))


def compare_reports(current, previous):
    # Compare complete private metadata via its digests, not just headline counts.
    # Binary bit identity across build-directory paths is not asserted here.
    for key in ("schema_version", "identity", "analyzer_sha256", "analysis_source_sha256",
                "loader_static_library_sha256", "decoder_static_library_sha256", "compiler", "probe_sanitizers", "titles"):
        if current[key] != previous[key]:
            raise ValueError(f"repeat analysis differs: {key}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owned", required=True, type=Path)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--toolchain", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--compare", type=Path, help="prior report.json; require identical input/tool/source/metadata identities")
    parser.add_argument("--sanitizers", action="store_true", help="instrument the maintained probe and scan tests (upstream archives remain as prepared)")
    args = parser.parse_args()
    try:
        if platform.system() != "Linux" or platform.machine() != "x86_64":
            raise ValueError("use the verified x86-64 Ubuntu/WSL preparation environment")
        identity = verify(args.owned, json.loads(DEFAULT.read_text()))
        lock_path = ROOT / "config/toolchains/lock.json"
        lock = json.loads(lock_path.read_text())
        verify_sources(args.sources.resolve(), lock)
        preparation = json.loads((args.toolchain / "manifest.json").read_text())
        analyzer = args.toolchain / "cpu/XenonAnalyse/XenonAnalyse"
        if preparation["lock_sha256"] != text_sha256(lock_path) or sha256(analyzer) != preparation["tools"]["XenonAnalyse"]:
            raise ValueError("analysis toolchain identity mismatch")
        if args.output.exists():
            raise ValueError("output already exists; use a fresh private directory")
        args.output.mkdir(parents=True)
        output = args.output.resolve()

        def run(command, name):
            result = subprocess.run(list(map(str, command)), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
            (output / f"{name}.stderr.log").write_bytes(result.stderr)
            if result.returncode:
                (output / f"{name}.stdout.log").write_bytes(result.stdout)
                raise ValueError(f"{name} failed (exit {result.returncode}); inspect private logs")
            return result.stdout
        run(["cmake", "-S", ROOT / "config/analysis/probe", "-B", output / "build", "-G", "Ninja",
             "-DCMAKE_CXX_COMPILER=clang++-18", "-DCMAKE_BUILD_TYPE=Release",
             f"-DMW3_SCAN_SANITIZERS={'ON' if args.sanitizers else 'OFF'}",
             f"-DMW3_CPU_SOURCE={(args.sources / 'XenonRecomp').resolve()}",
             f"-DMW3_CPU_BUILD={(args.toolchain / 'cpu').resolve()}"], "configure")
        run(["cmake", "--build", output / "build", "--parallel", "2"], "build")
        compiler_file = next((output / "build/CMakeFiles").glob("*/CMakeCXXCompiler.cmake"))
        if f'CMAKE_CXX_COMPILER_VERSION "{lock["compilers"]["linux"]}"' not in compiler_file.read_text():
            raise ValueError("probe compiler differs from the canonical preparation lock")
        run([output / "build/mw3-scan-tests"], "synthetic-scans")
        probe = output / "build/mw3-image-probe"
        summaries = []
        for role, filename in (("sp", "default.xex"), ("mp", "default_mp.xex")):
            metadata = json.loads(run([probe, (args.owned / filename).resolve()], role + "-image"))
            table_file = output / f"{role}-switches.toml"
            run([analyzer, (args.owned / filename).resolve(), table_file], role + "-switches")
            switches = tomllib.loads(table_file.read_text())
            checked = validate_switches(metadata, switches)
            (output / f"{role}-image.json").write_text(json.dumps(metadata, indent=2) + "\n")
            summaries.append(dict(role=role, executable_sha256=next(row["sha256"] for row in identity["executables"] if row["name"] == filename),
                                  base=metadata["base"], entry_point=metadata["entry_point"], image_size=metadata["size"],
                                  section_count=len(metadata["sections"]), resolved_import_symbols=len(metadata["resolved_import_symbols"]),
                                  switches_sha256=sha256(table_file), metadata_sha256=sha256(output / f"{role}-image.json"),
                                  **checked, **summarize_mapping(metadata)))
        report = dict(schema_version=2, identity=identity["manifest_id"], analyzer_sha256=sha256(analyzer), probe_sha256=sha256(probe),
                      compiler=lock["compilers"]["linux"], probe_sanitizers=args.sanitizers,
                      probe_source_sha256=text_sha256(ROOT / "config/analysis/probe/image_probe.cpp"),
                      analysis_source_sha256={name: text_sha256(ROOT / "config/analysis" / name) for name in
                                             ("analyze.py", "probe/image_probe.cpp", "probe/scan.h", "probe/CMakeLists.txt", "probe/scan_tests.cpp")},
                      loader_static_library_sha256=sha256(args.toolchain / "cpu/XenonUtils/libXenonUtils.a"),
                      decoder_static_library_sha256=sha256(args.toolchain / "cpu/thirdparty/disasm/libdisasm.a"),
                      titles=summaries, guest_executed=False, control_flow_complete=False, unknown_import_coverage="not-established")
        if args.compare:
            compare_reports(report, json.loads(args.compare.read_text()))
            report["compared_to_report_sha256"] = sha256(args.compare)
        (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"analysis failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
