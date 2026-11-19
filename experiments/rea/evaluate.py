#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Bounded, local-only REA/Ghidra evaluation using an original PPC fixture.

No downloads, setup, MCP registration, title conversion, or guest execution.
Raw replies, binaries and diagnostics are private outputs, never Git inputs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import signal
import struct
import subprocess
import sys
import threading
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LANGUAGE = "PowerPC:BE:32:default"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path, algorithm="sha256"):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def operation(reply, name, expected_sha=None):
    require("error" not in reply and "result" in reply, "JSON-RPC failure")
    result = reply["result"]
    texts = [item["text"] for item in result.get("content", []) if item.get("type") == "text"]
    require(len(texts) == 1, "missing or ambiguous tool payload")
    value = json.loads(texts[0])
    require(result.get("structuredContent", value) == value, "contradictory tool payload")
    if result.get("isError"):
        require("error" in value, "failure omitted diagnostic")
        return None, value["error"]
    require("error" not in value, "unmarked tool error")
    if "normalized_result" in value:
        require(value["operation"] == name, "wrong evidence operation")
        require(value["provider"]["id"] == "ghidra" and value["provider"]["version"] == "12.1.4",
                "wrong evidence provider")
        require(value["subject"]["digest"]["sha256"] == expected_sha, "wrong evidence subject")
        return value["normalized_result"], None
    require("result" in value, "missing operation result")
    return value["result"], None


def check_instruction(value, address, word, mnemonic, destination=None):
    require(value["status"] == "decoded", "instruction not decoded")
    require(int(value["address"], 16) == address, "wrong instruction address")
    require(value["architecture"] == LANGUAGE, "wrong instruction language")
    require(value["length"] == 4 and value["bytes"] == f"{word:08x}", "wrong instruction bytes")
    require(value["mnemonic"].lower() == mnemonic, "wrong mnemonic")
    if destination is not None:
        flow = value["flow"]
        require(flow["conditional"] and not flow["computed"], "wrong branch kind")
        require([int(item, 16) for item in flow["direct_destinations"]] == [destination],
                "wrong branch destination")


class Session:
    """One owned stdio process group; finite requests and retained raw replies."""
    def __init__(self, prep, out):
        self.out, self.counter = out, 0
        self.messages = queue.Queue()
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("REA_", "GHIDRA_", "JAVA_", "JDK_", "_JAVA_"))}
        for name in ("home", "tmp", "cache", "config"):
            (out / name).mkdir()
        env.update(HOME=str(out / "home"), TMPDIR=str(out / "tmp"),
                   XDG_CACHE_HOME=str(out / "cache"), XDG_CONFIG_HOME=str(out / "config"),
                   GHIDRA_INSTALL_DIR=prep["ghidra"], JAVA_HOME=prep["java_home"],
                   JAVA_TOOL_OPTIONS="-XX:ActiveProcessorCount=2",
                   GHIDRA_HEADLESS_MAXMEM="1024M", GHIDRA_MAXMEM="1024M",
                   REA_GHIDRA_STARTUP_TIMEOUT_MS="120000", REA_GHIDRA_DECOMPILE_TIMEOUT_SECONDS="20",
                   REA_ANALYSIS_PROVIDER="ghidra", REA_LOG_LEVEL="silent")
        self.stderr = (out / "stderr.log").open("w")
        self.process = subprocess.Popen(
            [prep["node"], str(Path(prep["rea_package"]) / "scripts/rea.mjs"), "mcp"],
            env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            text=True, start_new_session=True)
        def reader():
            try:
                while line := self.process.stdout.readline(16 * 1024 * 1024 + 1):
                    require(len(line) <= 16 * 1024 * 1024, "oversized MCP line")
                    self.messages.put(json.loads(line))
                self.messages.put(RuntimeError("MCP stream closed"))
            except Exception as error:
                self.messages.put(error)
        self.reader = threading.Thread(target=reader, daemon=True)
        self.reader.start()

    def request(self, method, params):
        self.counter += 1
        request = dict(jsonrpc="2.0", id=self.counter, method=method, params=params)
        save(self.out / f"{self.counter:03}-request.json", request)
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            response = self.messages.get(timeout=max(0.1, deadline - time.monotonic()))
            if isinstance(response, Exception):
                raise response
            if response.get("id") == self.counter:
                save(self.out / f"{self.counter:03}-reply.json", response)
                return response
        raise TimeoutError(method)

    def initialize(self):
        response = self.request("initialize", dict(protocolVersion="2025-03-26", capabilities={},
                                clientInfo=dict(name="mw3-035-evaluation", version="1")))
        require(response["result"]["serverInfo"]["version"] == "6.9.0", "wrong REA version")
        self.process.stdin.write(json.dumps(dict(jsonrpc="2.0", method="notifications/initialized")) + "\n")
        self.process.stdin.flush()

    def call(self, name, arguments=None, sha=None):
        return operation(self.request("tools/call", dict(name=name, arguments=arguments or {})), name, sha)

    def close(self):
        self.process.stdin.close()
        try:
            status = self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=10)
            raise RuntimeError("MCP required emergency termination; cleanup fails")
        finally:
            self.stderr.close()
            self.process.stdout.close()
            self.reader.join(timeout=2)
        require(status == 0, f"MCP exited {status}")


def command(args, out, name):
    started = time.monotonic()
    result = subprocess.run(list(map(str, args)), capture_output=True, text=True, timeout=60)
    save(out / f"{name}.json", dict(command=list(map(str, args)), returncode=result.returncode,
                                   stdout=result.stdout, stderr=result.stderr,
                                   seconds=time.monotonic() - started))
    require(result.returncode == 0, f"{name} exited {result.returncode}")
    return result.stdout


def build(out, tools):
    obj, image = out / "fixture.o", out / "fixture.elf"
    command([tools["mc"], "-triple=powerpc-unknown-linux-gnu", "-filetype=obj", HERE / "fixture.s",
             "-o", obj], out, "assemble")
    command([tools["lld"], "-m", "elf32ppc", "-Ttext=0x10000", "--entry=mw3_probe", obj,
             "-o", image], out, "link")
    text = command([tools["readelf"], "-h", "-s", "-W", image], out, "readelf")
    disassembly = command([tools["objdump"], "-d", image], out, "objdump")
    symbols = {}
    for name in ("mw3_probe", "mw3_leaf", "mw3_data_ref", "mw3_marker", "mw3_vmx128"):
        matches = re.findall(rf"^\s*\d+:\s+([a-fA-F0-9]+)\s+\d+\s+(?:FUNC|OBJECT)\s+GLOBAL\s+\S+\s+\d+\s+{name}$", text, re.M)
        require(len(matches) == 1, f"ambiguous/missing independent symbol {name}")
        symbols[name] = int(matches[0], 16)
    data = image.read_bytes()
    require(data[:6] == b"\x7fELF\x01\x02" and struct.unpack_from(">HH", data, 16) == (2, 20),
            "not ELF32 BE PPC ET_EXEC")
    require(struct.unpack_from(">I", data, 24)[0] == symbols["mw3_probe"], "entry reader disagreement")
    require("38 64 12 34" in disassembly and "41 82 00 08" in disassembly,
            "LLVM did not retain expected instruction bytes")
    return image, symbols


def positive(session, image, symbols):
    sha = digest(image)
    started = time.monotonic()
    target, error = session.call("open_binary", dict(path=str(image), provider_id="ghidra"))
    require(error is None and target["sha256"] == sha and target["architecture"] == "powerpc", "wrong target")
    observed, error = session.call("inspect_native_load_image", sha=sha)
    require(error is None, "load observation failed")
    observations = observed["observations"]
    require(observations["language_id"] == LANGUAGE, "wrong loaded language")
    require(observations["compiler_spec_id"] == "default", "wrong loaded ABI")
    require(any(item["original_sha256"] == sha and item["modified_sha256"] == sha
                for item in observations["source_files"]), "wrong loaded bytes")
    import_seconds = time.monotonic() - started
    procedures, error = session.call("list_procedures", sha=sha)
    require(error is None, "procedure listing failed")
    for name in ("mw3_probe", "mw3_leaf", "mw3_data_ref"):
        require(any(item["value"] == name and int(item["address"], 16) == symbols[name]
                    for item in procedures), f"missing procedure {name}")
    def query(name, **arguments):
        result, error = session.call(name, arguments, sha)
        require(error is None, f"{name} failed")
        return result
    move = query("inspect_native_instruction", address=hex(symbols["mw3_leaf"]))
    branch = query("inspect_native_instruction", address=hex(symbols["mw3_leaf"] + 8))
    check_instruction(move, symbols["mw3_leaf"], 0x38641234, "addi")
    check_instruction(branch, symbols["mw3_leaf"] + 8, 0x41820008, "beq", symbols["mw3_leaf"] + 16)
    require(hex(symbols["mw3_leaf"]) in query("procedure_callees", procedure=hex(symbols["mw3_probe"])),
            "missing direct-call xref")
    marker = query("read_bytes", address=hex(symbols["mw3_marker"]), length=4)
    require(marker["returned_bytes"] == 4 and marker["bytes_hex"] == "1234abcd", "wrong BE global")
    xrefs = query("xrefs", address=hex(symbols["mw3_marker"]))
    require(hex(symbols["mw3_data_ref"] + 8) in xrefs, "missing load-instruction data xref")
    dossier = query("analyze_function", procedure=hex(symbols["mw3_leaf"]), detail="complete")
    require(dossier["pseudocode"].strip(), "no decompiler liveness evidence")
    vmx = query("inspect_native_instruction", address=hex(symbols["mw3_vmx128"]))
    vmx_bytes = query("read_bytes", address=hex(symbols["mw3_vmx128"]), length=4)
    require(vmx_bytes["returned_bytes"] == 4 and vmx_bytes["bytes_hex"] == "100b60cb",
            "VMX128 probe bytes were not retained")
    closed, error = session.call("close_binary")
    require(error is None and closed is None, "close failed")
    require(digest(image) == sha, "provider modified original fixture")
    # A deliberate wrong expected word must be detected for the exact reason.
    try:
        check_instruction(move, symbols["mw3_leaf"], 0x38641235, "addi")
    except ValueError as failure:
        require(str(failure) == "wrong instruction bytes", "unrelated mutation failure")
    else:
        raise ValueError("wrong-word mutation passed")
    return dict(sha256=sha, import_seconds=import_seconds, mutation_detected=True,
                vmx128_observation=vmx, data_xrefs=xrefs,
                load_image_verifier_status=observed["status"])


def check_refusal(error, name):
    """A missing tool, timeout, or unrelated I/O error cannot pass a negative."""
    details = error.get("details", {})
    if name in ("truncated", "ppc64", "default.xex", "default_mp.xex"):
        require(error["code"] == "target_unavailable" and error["category"] == "unsupported_target",
                "wrong format-refusal class")
        require(details.get("constraint") == "file_format_rejected", "not a format refusal")
        reason = details.get("reason", "").lower()
        expected = {"truncated": "truncated elf header", "ppc64": "unsupported",
                    "default.xex": "unsupported binary format", "default_mp.xex": "unsupported binary format"}
        require(expected[name] in reason, "wrong format-refusal reason")
    else:
        require(error["code"] == "capability_unavailable" and error["category"] == "unsupported_provider",
                "wrong provider-refusal class")
        expected = {"relocatable": "ET_EXEC only", "shared": "ET_EXEC only",
                    "embedded": "EF_PPC_EMB", "little-endian": "big-endian ELF32 only"}
        require(any(item.get("provider_id") == "ghidra" and item.get("origin") == "target"
                    and item.get("code") == "architecture_unsupported"
                    and expected[name] in item.get("reason", "")
                    for item in details.get("rejections", [])), "missing expected Ghidra rejection")
    require(details.get("selection_at_failure") == {"kind": "none"}, "failure retained active target")


def refused(session, path, name):
    sha = digest(path)
    result, error = session.call("open_binary", dict(path=str(path), provider_id="ghidra"))
    if error is None:
        require(result["sha256"] == sha, "negative target identity mismatch")
        result, error = session.call("list_procedures", sha=sha)
    require(error is not None, "unsupported target unexpectedly admitted")
    check_refusal(error, name)
    _, close_error = session.call("close_binary")
    require(close_error is None, "negative session failed cleanup")
    require(digest(path) == sha, "provider modified negative input")
    return dict(sha256=sha, diagnostic=error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--owned", type=Path, help="Optional read-only directory containing the exact manifest pair")
    parser.add_argument("--runs", type=int, default=3)
    for name, default in (("mc", "/usr/bin/llvm-mc-19"), ("lld", "/usr/bin/ld.lld-20"),
                          ("objdump", "/usr/bin/llvm-objdump-19"), ("readelf", "/usr/bin/readelf")):
        parser.add_argument("--" + name, default=default)
    args = parser.parse_args()
    require(sys.platform == "linux" and args.runs in range(1, 4), "Linux; one to three sequential runs")
    out_root = args.output_root.resolve()
    require(not out_root.is_relative_to(ROOT) or ".local" in out_root.relative_to(ROOT).parts,
            "outputs must be outside repository or under ignored .local")
    if args.owned:
        owned_root = args.owned.resolve()
        require(not out_root.is_relative_to(owned_root) and not owned_root.is_relative_to(out_root),
                "output overlaps owned inputs")
    prep = json.loads(args.preparation.read_text())
    pins = json.loads((HERE / "pins.json").read_text())
    archive_root = Path(prep["rea_package"]).parents[1]
    for name, (algorithm, expected) in pins["archives"].items():
        require(digest(archive_root / name, algorithm) == expected, "archive identity mismatch: " + name)
    require(json.loads((Path(prep["rea_package"]) / "package.json").read_text())["version"] == "6.9.0",
            "wrong installed REA package")
    out = out_root / uuid.uuid4().hex
    out.mkdir(parents=True, mode=0o700)
    print("private output:", out, flush=True)
    report = dict(schema_version=1, task="MW3-035", status="FAIL", synthetic_positive=True,
                  game_executed=False, preparation=prep, preparation_sha256=digest(args.preparation),
                  sources={p.name: digest(p) for p in (Path(__file__), HERE / "fixture.s", HERE / "pins.json")},
                  positive=[], negative={})
    tools = {name: getattr(args, name) for name in ("mc", "lld", "objdump", "readelf")}
    try:
        report["tools"] = {name: dict(path=path, sha256=digest(Path(path).resolve()),
                                    version=command([path, "--version"], out, name + "-version").splitlines()[0])
                           for name, path in tools.items()}
        report["executed_files"] = {str(p): digest(p) for p in (
            Path(sys.executable),
            Path(prep["node"]), Path(prep["java_home"]) / "bin/java",
            Path(prep["rea_package"]) / "scripts/rea.mjs",
            Path(prep["rea_package"]) / "bridge/ghidra/ReaGhidraBridge.java",
            Path(prep["ghidra"]) / "Ghidra/application.properties",
            Path(prep["ghidra"]) / "Ghidra/Features/Decompiler/os/linux_x86_64/decompile")}
        # Bind the bundled JS chunks/native addons, bridge, processor specs and
        # Ghidra JARs as used, beyond the small launcher-file identity above.
        report["provider_files"] = {
            label: {str(p.relative_to(directory)): digest(p) for p in sorted(directory.rglob("*"))
                    if p.is_file()}
            for label, directory in (("rea", Path(prep["rea_package"])),
                                     ("ghidra", Path(prep["ghidra"])))
        }
        image, symbols = build(out, tools)
        report["symbols"] = symbols
        for index in range(args.runs):
            run = out / f"positive-{index}"
            run.mkdir()
            session = Session(prep, run)
            try:
                session.initialize()
                report["positive"].append(positive(session, image, symbols))
                print(f"positive {index}: PASS", flush=True)
            finally:
                session.close()
        data = image.read_bytes()
        negatives = {"relocatable": out / "fixture.o"}
        for name, triple, emulation in (("little-endian", "powerpcle-unknown-linux-gnu", "elf32lppc"),
                                        ("ppc64", "powerpc64-unknown-linux-gnu", "elf64ppc")):
            obj, target = out / (name + ".o"), out / (name + ".elf")
            command([tools["mc"], "-triple=" + triple, "-filetype=obj", HERE / "fixture.s", "-o", obj],
                    out, name + "-assemble")
            command([tools["lld"], "-m", emulation, "-Ttext=0x10000", "--entry=mw3_probe", obj,
                     "-o", target], out, name + "-link")
            command([tools["readelf"], "-h", "-W", target], out, name + "-header")
            negatives[name] = target
        for name, offset, value in (("shared", 16, struct.pack(">H", 3)),
                                    ("embedded", 36, struct.pack(">I", 0x80000000))):
            mutated = bytearray(data)
            mutated[offset:offset + len(value)] = value
            negatives[name] = out / (name + ".elf")
            negatives[name].write_bytes(mutated)
        negatives["truncated"] = out / "truncated.elf"
        negatives["truncated"].write_bytes(data[:20])
        if args.owned:
            manifest = json.loads((ROOT / "config/titles/mw3-xbox360-rev1.json").read_text())
            for item in manifest["executables"]:
                path = args.owned / item["name"]
                require(path.stat().st_size == item["size"] and digest(path) == item["sha256"],
                        "owned executable manifest mismatch")
                negatives[item["name"]] = path.resolve()
        for name, path in negatives.items():
            run = out / ("negative-" + name)
            run.mkdir()
            session = Session(prep, run)
            try:
                session.initialize()
                report["negative"][name] = refused(session, path, name)
                print(name + ": refused", flush=True)
            finally:
                session.close()
        report["status"] = "PASS"
    except Exception as error:
        report["failure"] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        report["artifacts"] = {str(p.relative_to(out)): digest(p) for p in out.rglob("*") if p.is_file()}
        save(out / "report.json", report)
        print("report:", out / "report.json", report["status"], flush=True)


if __name__ == "__main__":
    main()
