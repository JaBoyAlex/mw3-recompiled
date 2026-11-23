#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build and verify a bounded owned-title lifecycle checkpoint."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

import recompile as common
import prepare_runtime_stop as stop
import prepare_runtime_xma as xma
import prepare_runtime_memory_imports as memory_imports
import runtime_probe as audit

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "runtime/lifecycle"
CASES = ("positive-0", "positive-1", "positive-2", "bad-binding", "bad-pointer", "bad-oracle", "interrupt")
ALLOCATION_CONTRACT = ROOT / "config/runtime/title-allocation.json"
ALLOCATION_CASES = (*CASES, "allocation-bad-binding", "allocation-bad-pointer", "allocation-bad-oracle",
                    "allocation-incomplete", "allocation-late")
DIAGNOSTICS = ("addresssanitizer", "leaksanitizer", "undefinedbehaviorsanitizer", "runtime error:", "crash report", "exception:")


def inspect_contract(path, expected_sha256, role, identity, metadata, generation_sha256):
    if role not in ("sp", "mp"):
        raise ValueError("unknown allocation role")
    if not expected_sha256 or common.sha(path) != expected_sha256:
        raise ValueError("allocation contract differs from explicit binding")
    contract = json.loads(path.read_text())
    fields = {"schema_version", "phase", "allow_allocation", "call_budget", "max_requested_bytes", "generation_sha256", "roles"}
    if (not isinstance(contract, dict) or set(contract) != fields or type(contract["schema_version"]) is not int
            or contract["schema_version"] != 1 or contract["phase"] != "first-allocation"
            or contract["allow_allocation"] is not True or type(contract["call_budget"]) is not int
            or contract["call_budget"] != 1 or type(contract["max_requested_bytes"]) is not int
            or not 1 <= contract["max_requested_bytes"] <= 16 * 1024 * 1024
            or not isinstance(contract["roles"], dict) or set(contract["roles"]) != {"sp", "mp"}):
        raise ValueError("unreviewed allocation checkpoint policy")
    selected = contract["roles"][role]
    required = {"executable_sha256", "metadata_sha256", "lr", "import_address", "ordinal", "base_pointer_r31_offset",
                "size_pointer_r31_offset", "allocation_type", "protection", "region_source_gpr", "original_callsite_words_sha256",
                "independent_llvm_disassembly_sha256", "initial_base", "initial_size", "region", "precall_capture_manifest_sha256"}
    if not isinstance(selected, dict) or set(selected) != required:
        raise ValueError("incomplete allocation caller contract")
    for key in ("lr", "import_address", "ordinal", "base_pointer_r31_offset", "size_pointer_r31_offset", "allocation_type",
                "protection", "region_source_gpr", "initial_base", "initial_size", "region"):
        if type(selected[key]) is not int or not 0 <= selected[key] < 2**32:
            raise ValueError("invalid allocation contract integer")
    for key in required - {"lr", "import_address", "ordinal", "base_pointer_r31_offset", "size_pointer_r31_offset", "allocation_type",
                           "protection", "region_source_gpr", "initial_base", "initial_size", "region"}:
        if not isinstance(selected[key], str) or not re.fullmatch(r"[a-f0-9]{64}", selected[key]):
            raise ValueError("invalid allocation evidence digest")
    executable = next(row for row in identity["executables"] if row["name"] == ("default.xex" if role == "sp" else "default_mp.xex"))
    calls = metadata["flow_scan"]["immediate_calls"]
    if (contract["generation_sha256"] != generation_sha256 or selected["executable_sha256"] != executable["sha256"]
            or selected["lr"] % 4 or selected["import_address"] % 4 or selected["ordinal"] != 0xcc
            or selected["base_pointer_r31_offset"] != 80 or selected["size_pointer_r31_offset"] != 324
            or selected["allocation_type"] != 0x60002000 or selected["protection"] != 4 or selected["region_source_gpr"] != 27
            or selected["initial_base"] != 0 or selected["initial_size"] != 0x100000 or selected["region"] != 0
            or selected["initial_size"] > contract["max_requested_bytes"]):
        raise ValueError("unreviewed allocation inspection contract")
    matches = [row for lib in metadata["import_audit"]["libraries"] for row in lib["records"]
               if row["type"] == 1 and row["export_name"] == "NtAllocateVirtualMemory"]
    if (len(matches) != 1 or matches[0]["ordinal"] != 0xcc or matches[0]["export_kind"] != "kFunction"
            or matches[0]["address"] != selected["import_address"]
            or not any(row["site"] == selected["lr"] - 4 and row["target"] == selected["import_address"] for row in calls)):
        raise ValueError("allocation caller/import differs from original metadata")
    return selected


def probe_output(requested, owned, root, sdk, receipt, metadata, generation):
    output = common.private_cache(requested, owned)
    protected = [HOST, ROOT / "tools", ROOT / "config", ROOT / "include", ROOT / "src", sdk, receipt.parent, metadata]
    if generation:
        protected.append(generation.parent)
    protected.extend(root / name for name in ("sources", "build", "install", "memory-preparations", "stop-preparations",
                                               "xma-preparations", "memory-imports-preparations"))
    if any(output.is_relative_to(p.resolve()) or p.resolve().is_relative_to(output) for p in protected):
        raise ValueError("lifecycle output overlaps immutable inputs")
    return output / uuid.uuid4().hex


def allocation_input(text, selected, nonce):
    fields = ("lr", "r1", "r31", "base_word", "size_word", "base", "size", "type", "protect", "region")
    pattern = r"^MW3_ALLOCATION_INPUT:" + " ".join(key + r"=(?P<" + key + r">[a-f0-9]{8})" for key in fields)
    matches = list(re.finditer(pattern + r" nonce=(?P<nonce>[a-f0-9]{32})$", text, re.MULTILINE))
    if len(matches) != 1 or text.count("MW3_ALLOCATION_INPUT:") != 1 or matches[0]["nonce"] != nonce:
        return None
    values = {key: int(matches[0][key], 16) for key in fields}
    if (values["lr"] != selected["lr"] or values["r31"] + 328 > 2**32
            or values["base_word"] != values["r31"] + 80 or values["size_word"] != values["r31"] + 324
            or values["base_word"] % 4 or values["size_word"] % 4
            or values["base"] != selected["initial_base"] or values["size"] != selected["initial_size"]
            or values["type"] != selected["allocation_type"] or values["protect"] != selected["protection"]
            or values["region"] != selected["region"]):
        return None
    return matches[0][0]


def recovered(code, text, expected, complete=True):
    if code != expected:
        return False
    matches = re.findall(r"^MW3_LIFECYCLE_SHUTDOWN:result=0 threads_before=(\d+) threads_after=(\d+)$", text, re.MULTILINE)
    if len(matches) != 1 or matches[0][0] != matches[0][1]:
        return False
    events = [line for line in text.splitlines() if line.startswith("MW3_LIFECYCLE_") and not line.startswith("MW3_LIFECYCLE_REJECT:")]
    wanted = [f"MW3_LIFECYCLE_THREAD_STOPPED:exit={expected} queries=1",
              "MW3_LIFECYCLE_UNLOADED:reservation_released=1", "MW3_LIFECYCLE_MAPPING_RELEASED:bytes=4831838208",
              f"MW3_LIFECYCLE_SHUTDOWN:result=0 threads_before={matches[0][0]} threads_after={matches[0][1]}"]
    if complete:
        wanted.append(f"MW3_LIFECYCLE_COMPLETE:exit={expected}")
    return events == wanted


def classify_allocation(case, code, text, nonce, selected, inspect=False):
    if case not in ALLOCATION_CASES or not re.fullmatch(r"[a-f0-9]{32}", nonce):
        return False
    if any(word in text.lower() for word in DIAGNOSTICS):
        return False
    mode = "positive" if case.startswith("positive") else case
    markers = [line for line in text.splitlines() if line.startswith("MW3_CHECKPOINT_RUN:")]
    if markers != [f"MW3_CHECKPOINT_RUN:case={mode} nonce={nonce}"]:
        return False
    protocol = [line for line in text.splitlines() if line.startswith("MW3_")]
    if not protocol or protocol[0] != markers[0]:
        return False
    unreviewed = [i for i, line in enumerate(protocol) if line.startswith("MW3_PROBE_UNREVIEWED_IMPORT:")]
    if unreviewed and not (inspect and case.startswith("positive")):
        return False
    allocations = [i for i, line in enumerate(protocol) if line.startswith("MW3_ALLOCATION_")]
    lifecycle = [i for i, line in enumerate(protocol) if line.startswith("MW3_LIFECYCLE_")]
    if allocations:
        if (any(i > allocations[0] for i, line in enumerate(protocol)
                if line.startswith(("MW3_HEADER_", "MW3_MODULE_HEADER_AUDIT_")))
                or lifecycle and min(lifecycle) <= max(allocations)
                or unreviewed and (min(unreviewed) <= max(allocations)
                                   or lifecycle and max(unreviewed) >= min(lifecycle))):
            return False
    rejection = [i for i, line in enumerate(protocol) if line.startswith("MW3_LIFECYCLE_REJECT:")]
    recovery = [i for i in lifecycle if not protocol[i].startswith("MW3_LIFECYCLE_REJECT:")]
    if rejection and recovery and max(rejection) >= min(recovery):
        return False
    events = [line for line in text.splitlines() if line.startswith("MW3_ALLOCATION_")]
    if case in ("bad-binding", "bad-pointer", "bad-oracle", "interrupt"):
        return not events and classify(case, code, text)
    if case == "allocation-bad-binding":
        return not inspect and not events and classify("bad-binding", code, text)
    if text.count("MW3_HEADER_ORACLE_CASE_PASS:") != 4 or text.count("MW3_HEADER_QUERY_PASS:") != 1:
        return False
    rejects = re.findall(r"^MW3_LIFECYCLE_REJECT:(.*)$", text, re.MULTILINE)
    armed = f"MW3_ALLOCATION_ARMED:nonce={nonce}"
    if case == "allocation-bad-pointer":
        return (not inspect and events == [armed, f"MW3_ALLOCATION_MUTATION:allocation-bad-pointer nonce={nonce}"]
                and rejects == ["allocation pointer setup differs from audited PPC"] and recovered(code, text, 87))
    captured = allocation_input(text, selected, nonce)
    if not captured:
        return False
    if inspect:
        return (case.startswith("positive") and events == [armed, captured] and classify(case, code, text))
    if "MW3_PROBE_UNREVIEWED_IMPORT:" in text:
        return False
    returns = re.findall(r"^MW3_ALLOCATION_RETURN:status=00000000 base=([a-f0-9]{8}) size=([a-f0-9]{8}) nonce=" + nonce + "$", text, re.MULTILINE)
    if len(returns) != 1 or text.count("MW3_ALLOCATION_RETURN:") != 1:
        return False
    address, size = (int(value, 16) for value in returns[0])
    rounded = (selected["initial_size"] + 65535) & ~65535
    if not address or address % 65536 or address + size > 2**32 or size != rounded:
        return False
    wanted = [armed, captured, f"MW3_ALLOCATION_CALL:nonce={nonce}",
              f"MW3_ALLOCATION_RETURN:status=00000000 base={address:08x} size={size:08x} nonce={nonce}",
              f"MW3_ALLOCATION_CHECK_PASS:bytes={rounded:08x} reserved=1 committed=0 neighbours=1 nonce={nonce}"]
    if case in ("allocation-bad-oracle", "allocation-incomplete", "allocation-late"):
        wanted.append(f"MW3_ALLOCATION_MUTATION:{case} nonce={nonce}")
    if case == "allocation-late":
        return events == wanted and code == -999 and not rejects and "MW3_LIFECYCLE_" not in text
    if case == "allocation-bad-oracle":
        return events == wanted and rejects == ["intentional allocation oracle mismatch"] and recovered(code, text, 87)
    wanted.append(f"MW3_ALLOCATION_STOP:before_guest_return=1 nonce={nonce}")
    return (events == wanted and not rejects and recovered(code, text, 86, complete=case != "allocation-incomplete")
            and (case.startswith("positive") or case == "allocation-incomplete"))


def classify(case, code, text):
    if case not in CASES:
        raise ValueError("unknown lifecycle case")
    if any(marker in text for marker in ("AddressSanitizer", "LeakSanitizer", "runtime error:", "UndefinedBehaviorSanitizer")):
        return False
    expected = 86 if case.startswith("positive") else 88 if case == "interrupt" else 87
    if code != expected or text.count(f"MW3_LIFECYCLE_COMPLETE:exit={expected}") != 1:
        return False
    if text.count("MW3_LIFECYCLE_UNLOADED:reservation_released=1") != 1:
        return False
    if text.count("MW3_LIFECYCLE_MAPPING_RELEASED:bytes=4831838208") != 1:
        return False
    counts = re.findall(r"MW3_LIFECYCLE_SHUTDOWN:result=0 threads_before=(\d+) threads_after=(\d+)", text)
    if len(counts) != 1 or counts[0][0] != counts[0][1]:
        return False
    if case.startswith("positive"):
        return (text.count("MW3_HEADER_ORACLE_CASE_PASS:") == 4
                and text.count("MW3_HEADER_QUERY_PASS:") == 1
                and text.count("MW3_PROBE_UNREVIEWED_IMPORT:NtAllocateVirtualMemory ") == 1
                and "MW3_LIFECYCLE_REJECT:" not in text
                and text.count("MW3_LIFECYCLE_THREAD_STOPPED:exit=86 queries=1") == 1)
    if case == "interrupt":
        return (text.count("MW3_HEADER_QUERY_PASS:") == 1
                and text.count("MW3_LIFECYCLE_INTERRUPT_REQUESTED:exit=88") == 1
                and text.count("MW3_LIFECYCLE_THREAD_STOPPED:exit=88 queries=1") == 1
                and "MW3_PROBE_UNREVIEWED_IMPORT:" not in text and "MW3_LIFECYCLE_REJECT:" not in text)
    reason = {"bad-binding": "function binding verification", "bad-pointer": "unexpected header pointer",
              "bad-oracle": "SDK header result differs from independent oracle"}[case]
    rejects = re.findall(r"^MW3_LIFECYCLE_REJECT:(.*)$", text, re.MULTILINE)
    metadata_checked = case == "bad-binding" or text.count("MW3_LIFECYCLE_THREAD_STOPPED:exit=87 queries=1") == 1
    return rejects == [reason] and metadata_checked and "MW3_HEADER_QUERY_PASS:" not in text


def controlled_traps(metadata, prefix, expected_count, allocation_guard=False):
    source, address = audit.guarded_traps(metadata, prefix, expected_count)
    expression = re.compile(
        r'extern "C" void __imp__(\w+)\(PPCContext& ctx, u8\*\) \{ [^\n]+std::_Exit\(86\); \}')
    changed = []

    def replace(match):
        name = match.group(1)
        changed.append(name)
        return f'extern "C" void __imp__{name}(PPCContext& ctx, u8*) {{ StopUnreviewedImport("{name}",ctx); }}'

    source = expression.sub(replace, source)
    if len(changed) != expected_count - 1 or "std::_Exit" in source:
        raise ValueError("unrecognized audited import-stop template")
    declaration = 'extern "C" [[noreturn]] void StopUnreviewedImport(const char*,PPCContext&);\n'
    first, remainder = source.split("\n", 1)
    source = first + "\n" + declaration + remainder
    if allocation_guard:
        rows = [r for lib in metadata["import_audit"]["libraries"] for r in lib["records"] if r["type"] == 1]
        selected = [r for r in rows if r["export_name"] == "NtAllocateVirtualMemory"]
        others = [r for r in rows if r["export_name"] != "NtAllocateVirtualMemory"]
        if len(selected) != 1 or not others:
            raise ValueError("allocation binding mutation fixture missing")
        original = "runtime.FindFunction(" + hex(selected[0]["address"]) + ")"
        changed = 'runtime.FindFunction(std::getenv("MW3_ALLOCATION_TEST_BAD_BINDING") ? ' + hex(others[0]["address"]) + " : " + hex(selected[0]["address"]) + ")"
        if source.count(original) != 1:
            raise ValueError("allocation binding mutation anchor differs")
        source = source.replace(original, changed)
    return source, address


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "sdk-report", "owned", "metadata", "output-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--role", choices=("sp", "mp"), required=True)
    parser.add_argument("--sdk-profile", choices=("stop", "xma", "memory-imports"), default="stop")
    parser.add_argument("--checkpoint", choices=("header", "allocation-inspect", "allocation"), default="header")
    parser.add_argument("--expected-allocation-contract-sha256")
    parser.add_argument("--cases", nargs="+", choices=ALLOCATION_CASES)
    parser.add_argument("--generation", type=Path, help="immutable generation receipt, required on Windows")
    parser.add_argument("--expected-generation-sha256")
    parser.add_argument("--sanitizers", action="store_true")
    args = parser.parse_args()
    if args.cases is None:
        args.cases = ALLOCATION_CASES if args.checkpoint == "allocation" else CASES
    verifier = {"xma": xma, "stop": stop, "memory-imports": memory_imports}[args.sdk_profile]
    output = None
    report = dict(schema_version=1, status="IN_PROGRESS", playable=False, guest_executed=False,
                  script_sha256=common.sha(__file__), role=args.role, results=[],
                  host_sources=common.snapshot(HOST), host_sanitizers=args.sanitizers,
                  sdk_profile=args.sdk_profile, checkpoint=args.checkpoint, selected_cases=list(args.cases))
    report["supporting_sources"] = {str(path.relative_to(ROOT)): common.sha(path) for path in (
        ROOT / "src/xex.cpp", ROOT / "include/mw3/xex.hpp", Path(common.__file__), Path(stop.__file__),
        Path(xma.__file__), xma.LOCK, xma.LOCK.parent / "packet.patch",
        Path(audit.__file__), ROOT / "experiments/runtime-bakeoff/rexglue_probe.py",
        ROOT / "runtime/bringup/analysis-lock.json", common.DEFAULT, common.RECIPE)}
    report["supporting_sources"].update({str(path.relative_to(ROOT)): common.sha(path) for path in (
        Path(memory_imports.__file__), memory_imports.LOCK, memory_imports.LOCK.parent / "in-out-words.patch")})
    try:
        for task in ("036", "037", "038", "039", "040", "042", "043"):
            if json.loads((ROOT / f"tasks/MW3-{task}.json").read_text())["status"] != "done":
                raise ValueError(f"unfinished child MW3-{task}")
        owned = args.owned.resolve()
        identity = common.verify(owned, json.loads(common.DEFAULT.read_text()))
        if len(set(args.cases)) != len(args.cases):
            raise ValueError("duplicate lifecycle case")
        if args.checkpoint != "allocation" and any(case not in CASES for case in args.cases):
            raise ValueError("allocation mutation requires the allocation checkpoint")
        if args.checkpoint != "header" and (args.sdk_profile != "memory-imports" or not args.generation):
            raise ValueError("allocation inspection requires explicit repaired SDK and generation")
        if args.checkpoint != "header":
            for task in ("046", "091"):
                if json.loads((ROOT / f"tasks/MW3-{task}.json").read_text())["status"] != "done":
                    raise ValueError("unfinished allocation contract/repair dependency")
        if verifier is memory_imports:
            sdk, evidence = verifier.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        else:
            sdk, evidence = verifier.verify_prepared(args.root.resolve(), args.sdk_report)
        report.update(identity=identity, sdk=evidence, sdk_report_sha256=common.sha(args.sdk_report))
        recipe = common.validate_recipe(json.loads(common.RECIPE.read_text()))
        windows = sys.platform == "win32"
        if args.generation:
            if not args.expected_generation_sha256 or common.sha(args.generation) != args.expected_generation_sha256:
                raise ValueError("generation receipt differs from explicit binding")
            generation = json.loads(args.generation.read_text())
            report["generation_receipt_sha256"] = common.sha(args.generation)
            payload = args.generation.parent / "payload"
            if (generation.get("status") != "GENERATED" or generation["identity"] != identity
                    or generation["recipe"] != recipe or generation["files"] != common.snapshot(payload)
                    or generation["recipe_sha256"] != common.sha(common.RECIPE)
                    or generation["driver_sha256"] != common.sha(common.__file__)
                    or generation["sdk"]["stop_lock_sha256"] != common.sha(stop.LOCK)):
                raise ValueError("generation payload or identity changed")
        else:
            if windows:
                raise ValueError("Windows requires a verified independent generation receipt")
            generation = None
        metadata = args.metadata / (args.role + "-image.json")
        analysis = json.loads((ROOT / "runtime/bringup/analysis-lock.json").read_text())
        if common.sha(metadata) != analysis[args.role]["metadata_sha256"]:
            raise ValueError("unreviewed analysis metadata")
        prefix = "mw3_" + args.role
        traps, address = controlled_traps(json.loads(metadata.read_text()), prefix, analysis[args.role]["function_imports"],
                                          allocation_guard=args.checkpoint == "allocation")
        definitions = f"#pragma once\n#define MW3_MODULE_HANDLE_IMPORT {hex(address)}u\n"
        selected = None
        if args.checkpoint != "header":
            selected = inspect_contract(ALLOCATION_CONTRACT, args.expected_allocation_contract_sha256,
                                        args.role, identity, json.loads(metadata.read_text()), common.sha(args.generation))
            if selected["metadata_sha256"] != common.sha(metadata):
                raise ValueError("allocation metadata binding changed")
            definitions += f"#define MW3_ALLOCATION_INSPECT 1\n#define MW3_ALLOCATION_LR {hex(selected['lr'])}u\n"
            definitions += (f"#define MW3_ALLOCATION_VALUES 1\n#define MW3_ALLOCATION_INITIAL_BASE {hex(selected['initial_base'])}u\n"
                            f"#define MW3_ALLOCATION_INITIAL_SIZE {hex(selected['initial_size'])}u\n"
                            f"#define MW3_ALLOCATION_REGION {hex(selected['region'])}u\n")
            if args.checkpoint == "allocation":
                limit = json.loads(ALLOCATION_CONTRACT.read_text())["max_requested_bytes"]
                definitions += f"#define MW3_ALLOCATION_EXECUTE 1\n#define MW3_ALLOCATION_LIMIT {limit}u\n"
                private_header = args.root.resolve() / "sources/rexglue-memory-imports/src/kernel/test_access.h"
                report["sdk_private_header"] = dict(path=str(private_header), sha256=common.sha(private_header))
                definitions += '#define MW3_SDK_TEST_ACCESS_HEADER "' + private_header.as_posix() + '"\n'
            report["supporting_sources"][str(ALLOCATION_CONTRACT.relative_to(ROOT))] = common.sha(ALLOCATION_CONTRACT)
            report["allocation_contract_sha256"] = common.sha(ALLOCATION_CONTRACT)
        output = probe_output(args.output_root, owned, args.root.resolve(), sdk, args.sdk_report, args.metadata, args.generation)
        output.mkdir(parents=True)
        print(json.dumps(dict(output=str(output))), flush=True)
        shutil.copytree(HOST, output / "maintained-host")
        shutil.copy2(__file__, output / "maintained-driver.py")
        if selected:
            shutil.copy2(ALLOCATION_CONTRACT, output / "allocation-contract.json")
        if generation is None:
            common.generate(output, sdk, owned, recipe)
            payload = output / "payload"
            generation = dict(schema_version=1, status="GENERATED", identity=identity, recipe=recipe,
                              recipe_sha256=common.sha(common.RECIPE), driver_sha256=common.sha(common.__file__), sdk=evidence,
                              generator_sha256=common.sha(sdk / "bin/rexglue"), files=common.snapshot(payload))
            (output / "generation.json").write_text(json.dumps(generation, indent=2) + "\n")
        report["generation"] = generation
        (output / "traps.cpp").write_text(traps)
        (output / "data-import.h").write_text(definitions)
        report.update(metadata_sha256=common.sha(metadata), traps_sha256=common.sha(output / "traps.cpp"),
                      data_import_sha256=common.sha(output / "data-import.h"))
        if windows:
            import prepare_windows_runtime as win
            lock = json.loads(win.LOCK.read_text())
            clang, report["compiler"] = win.compiler(args.root.resolve(), lock["compiler"], False)
            env, cmake, ninja, report["host"] = win.msvc_environment(lock, clang)
            compiler = clang / "bin/clang++.exe"
            extra = ["-DCMAKE_MAKE_PROGRAM=" + ninja.as_posix(), "-DCMAKE_CXX_FLAGS=-march=x86-64-v2",
                     "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld"]
            if args.sanitizers:
                report["calibration"] = win.calibrate_sanitizer(output, clang, env)
        else:
            env = dict(os.environ)
            cmake = "cmake"
            compiler = Path(shutil.which("clang++-20") or "missing")
            report["compiler"] = dict(sha256=common.sha(compiler), version=subprocess.check_output([compiler, "--version"], text=True).splitlines()[0])
            extra = ["-DCMAKE_CXX_FLAGS=-march=x86-64-v2 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13",
                     "-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=/usr/bin/ld.lld-20 -Wl,--threads=2"]
        cache = common.private_cache(output.parent / "build-cache", owned)
        cache.mkdir(exist_ok=True)
        build_key = common.digest(dict(sdk=evidence, generation=generation["files"], role=args.role,
                                       compiler=report["compiler"], cmake_sha256=common.sha(HOST / "CMakeLists.txt")))
        build = cache / build_key
        configure = [cmake, "-S", HOST, "-B", build, "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
                     "-DCMAKE_CXX_COMPILER=" + compiler.as_posix(), "-DCMAKE_CXX_FLAGS_RELEASE=-O2 -DNDEBUG",
                     "-DCMAKE_PREFIX_PATH=" + sdk.as_posix(), "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                     "-DMW3_GENERATED_DIR=" + (payload / args.role / "generated").as_posix(),
                     "-DMW3_GENERATED_PREFIX=" + prefix, "-DMW3_PRIVATE_TRAPS=" + (output / "traps.cpp").as_posix(),
                     "-DMW3_DATA_IMPORT_HEADER=" + (output / "data-import.h").as_posix(),
                     "-DMW3_LIFECYCLE_SANITIZERS=" + ("ON" if args.sanitizers else "OFF"), *extra]
        execution = output / "execution"
        execution.mkdir()
        with common.writer_lock(cache, build_key):
            for label, command in (("configure", configure), ("build", [cmake, "--build", build, "--parallel", "2"])):
                report.setdefault("commands", []).append(list(map(str, command)))
                print(json.dumps(dict(stage=label)), flush=True)
                with (output / (label + ".log")).open("wb") as log:
                    subprocess.run(list(map(str, command)), env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1800)
            name = "mw3-lifecycle.exe" if windows else "mw3-lifecycle"
            shutil.copy2(build / name, execution / name)
            if windows:
                for library in build.glob("*.dll"):
                    shutil.copy2(library, execution / library.name)
            shutil.copy2(build / "compile_commands.json", output / "compile_commands.json")
        binary = execution / name
        report.update(execution_files=common.snapshot(execution), build_key=build_key,
                      compile_commands_sha256=common.sha(output / "compile_commands.json"))
        report["binary_sha256"] = common.sha(binary)
        for case in args.cases:
            nonce = uuid.uuid4().hex
            lane = output / case
            (lane / "tmp").mkdir(parents=True)
            (lane / "config").mkdir()
            name = "default.xex" if args.role == "sp" else "default_mp.xex"
            command = [str(binary), "--kernel.headless=true", "--title.game_root=" + str(owned), "--title.entry=" + name,
                       "--app.root=" + str(lane / "app"), "--app.user_root=" + str(lane / "user"),
                       "--ui.driver=none", "--hid.drivers=none", "--apu.driver=none", "--gpu.driver=none"]
            child = {k: v for k, v in env.items() if not k.startswith(("REX_", "MW3_", "LD_", "ASAN_", "UBSAN_", "LSAN_"))}
            child.update(MW3_HEADER_OWNED_FILE=str(owned / name), MW3_LIFECYCLE_CASE="positive" if case.startswith("positive") else case,
                         MW3_ALLOCATION_NONCE=nonce,
                         TMPDIR=str(lane / "tmp"), TMP=str(lane / "tmp"), TEMP=str(lane / "tmp"),
                         XDG_CONFIG_HOME=str(lane / "config"), SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                         ASAN_OPTIONS="detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
            if case == "bad-binding":
                child["MW3_HEADER_TEST_BAD_BINDING"] = "1"
            if case == "allocation-bad-binding":
                child["MW3_ALLOCATION_TEST_BAD_BINDING"] = "1"
            if windows:
                child["PATH"] = str(sdk / "bin") + os.pathsep + child.get("PATH", "")
            else:
                child["LD_LIBRARY_PATH"] = str(sdk / "lib")
            with (lane / "run.log").open("wb") as log:
                try:
                    code = subprocess.run(command, cwd=execution, env=child, stdout=log, stderr=subprocess.STDOUT,
                                          timeout=5 if case == "allocation-late" else 30).returncode
                except subprocess.TimeoutExpired:
                    code = -999
            text = (lane / "run.log").read_text(errors="replace")
            if args.checkpoint == "header":
                accepted = classify(case, code, text)
            elif args.checkpoint == "allocation-inspect":
                accepted = classify_allocation(case, code, text, nonce, selected, inspect=True)
            else:
                accepted = classify_allocation(case, code, text, nonce, selected)
            loaded = re.findall(r"module 'rexkernel' loaded from '([^']+)'", text)
            kernel_hash = common.sha(Path(loaded[0])) if len(loaded) == 1 else None
            kernel_name = "bin/rexkernel.dll" if windows else "lib/librexkernel.so"
            accepted = (accepted and not any(word in text.lower() for word in DIAGNOSTICS)
                        and kernel_hash == evidence["sdk_files"][kernel_name]["sha256"])
            row = dict(case=case, nonce=nonce, status="PASS" if accepted else "FAIL", returncode=code,
                       command=command, log_sha256=common.sha(lane / "run.log"),
                       loaded_kernel_paths=loaded, loaded_kernel_sha256=kernel_hash,
                       events=[line for line in text.splitlines() if line.startswith("MW3_")])
            report["results"].append(row)
            print(json.dumps({key: row[key] for key in ("case", "status", "returncode")}), flush=True)
            (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        if verifier is memory_imports:
            _, after = verifier.verify_prepared(args.root.resolve(), args.sdk_report, allow_sanitized=args.sanitizers)
        else:
            _, after = verifier.verify_prepared(args.root.resolve(), args.sdk_report)
        if after != evidence or common.sha(binary) != report["binary_sha256"]:
            raise ValueError("SDK or executed binary changed")
        if common.snapshot(execution) != report["execution_files"]:
            raise ValueError("executed package changed")
        if common.snapshot(HOST) != report["host_sources"] or common.sha(__file__) != report["script_sha256"]:
            raise ValueError("maintained lifecycle source changed during verification")
        if any(common.sha(ROOT / path) != digest for path, digest in report["supporting_sources"].items()):
            raise ValueError("supporting source changed during verification")
        if (common.sha(output / "traps.cpp") != report["traps_sha256"]
                or common.sha(output / "data-import.h") != report["data_import_sha256"]
                or args.generation and common.sha(args.generation) != report["generation_receipt_sha256"]
                or selected and common.sha(output / "allocation-contract.json") != report["allocation_contract_sha256"]):
            raise ValueError("private trap/data/generation identity changed")
        if "sdk_private_header" in report and common.sha(Path(report["sdk_private_header"]["path"])) != report["sdk_private_header"]["sha256"]:
            raise ValueError("private SDK diagnostic header changed")
        common.verify(owned, json.loads(common.DEFAULT.read_text()))
        if common.snapshot(payload) != generation["files"]:
            raise ValueError("generated payload changed")
        report["status"] = "PASS" if all(row["status"] == "PASS" for row in report["results"]) else "FAIL"
        report["guest_executed"] = any(row["case"].startswith("positive") and row["status"] == "PASS" for row in report["results"])
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        return int(report["status"] != "PASS")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        if output:
            (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"lifecycle verification failed: {type(error).__name__}; inspect {output}\n")


if __name__ == "__main__":
    raise SystemExit(main())
