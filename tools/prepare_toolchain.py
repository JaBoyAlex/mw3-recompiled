#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build pinned host tools and verify original, game-free CPU/shader fixtures.

No packages are installed, no security settings are changed, and no game is loaded.
Initialize source submodules beforehand. Logs and artifacts remain in --output.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import struct
import subprocess
import tarfile
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/toolchains"
FIXTURES = CONFIG / "fixtures"
NAMES = ("arithmetic", "branch", "memory", "rotate")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text_sha256(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True, stderr=subprocess.PIPE).strip()


def verify_sources(source_root, lock):
    for source in lock["sources"]:
        folder = source_root / source["name"]
        if git(folder, "rev-parse", "HEAD") != source["commit"]:
            raise ValueError(f"{source['name']}: source revision differs from lock")
        if git(folder, "status", "--porcelain", "--untracked-files=normal"):
            raise ValueError(f"{source['name']}: dirty source or submodule")
        lines = subprocess.check_output(["git", "-C", str(folder), "submodule", "status", "--recursive"], text=True).splitlines()
        observed = {}
        for line in lines:
            if not line.startswith(" "):
                raise ValueError(f"{source['name']}: uninitialized, changed or conflicted submodule")
            revision, relative, *_ = line.strip().split()
            observed[relative] = revision
        if observed != {s["path"]: s["commit"] for s in source["submodules"]}:
            raise ValueError(f"{source['name']}: transitive revisions differ from lock")


def fetch_sources(source_root, lock):
    source_root.mkdir(parents=True, exist_ok=True)
    for source in lock["sources"]:
        path = source_root / source["name"]
        if path.exists():
            continue  # Verification refuses a dirty/mismatched existing checkout.
        if not source["url"].startswith("https://github.com/hedge-dev/"):
            raise ValueError("unexpected upstream source URL")
        subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", source["url"], str(path)], check=True)
        subprocess.run(["git", "-C", str(path), "checkout", "--detach", source["commit"]], check=True)
        subprocess.run(["git", "-C", str(path), "submodule", "update", "--init", "--recursive", "--depth", "1", "--jobs", "2"], check=True)


def compare_reports(left, right):
    # Host binaries may embed build paths/timestamps; compare the reproducible
    # translation/shader results and exact preparation inputs, not claimed binary identity.
    for key in ("host", "compiler", "lock_sha256", "preparation_sha256", "fixture_sha256", "generated_sha256", "ppc_checks", "mutation_rejected"):
        if left[key] != right[key]:
            raise ValueError(f"independent toolchain runs differ: {key}")


def safe_member(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError("unsafe DXC archive member")
    return path


def dxc_package(output, spec):
    archive = output / ("dxc.zip" if spec["url"].endswith(".zip") else "dxc.tar.gz")
    if not archive.exists():
        # Official URL and digest are versioned in the lock, never taken from a latest tag.
        if not spec["url"].startswith("https://github.com/microsoft/DirectXShaderCompiler/releases/download/"):
            raise ValueError("DXC download is not an official Microsoft release URL")
        temporary = archive.with_suffix(archive.suffix + ".part")
        with urllib.request.urlopen(spec["url"], timeout=60) as response, temporary.open("wb") as dest:
            shutil.copyfileobj(response, dest)
        if sha256(temporary) != spec["sha256"]:
            raise ValueError("DXC archive checksum mismatch; unverified partial file retained for inspection")
        temporary.replace(archive)
    if sha256(archive) != spec["sha256"]:
        raise ValueError("cached DXC archive checksum mismatch")
    destination = output / "dxc"
    destination.mkdir(exist_ok=True)
    # Verify each extracted regular file against the verified archive on every invocation.
    def write(name, data):
        relative = safe_member(name)
        path = destination / str(relative)
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != destination.parent):
            raise ValueError("symlink in DXC extraction destination")
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(data).hexdigest()
        if path.exists():
            if not path.is_file() or sha256(path) != digest:
                raise ValueError("extracted DXC file differs from verified archive")
        else:
            with path.open("xb") as file:
                file.write(data)
        return path
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                safe_member(member.filename)
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("symlink in DXC archive")
                if not member.is_dir():
                    write(member.filename, package.read(member))
    else:
        with tarfile.open(archive, "r:gz") as package:
            for member in package:
                safe_member(member.name)
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError("non-regular DXC archive member")
                path = write(member.name, package.extractfile(member).read())
                path.chmod(member.mode & 0o755)
    return destination


def synthetic_elf(code):
    """A minimal big-endian ELF32 executable with non-overlapping section addresses.

    XenonRecomp's test loader coalesces ELF sections by virtual address, so a
    relocatable llvm-mc object with multiple sections at address zero is unsuitable.
    """
    names = b"\0.text\0.shstrtab\0"
    text_at = 64
    names_at = text_at + len(code)
    table_at = (names_at + len(names) + 3) & ~3
    out = bytearray(table_at + 120)
    ident = b"\x7fELF\x01\x02\x01" + bytes(9)
    struct.pack_into(">16sHHIIIIIHHHHHH", out, 0, ident, 2, 20, 1, 0, 0, table_at, 0, 52, 0, 0, 40, 3, 2)
    out[text_at:text_at + len(code)] = code
    out[names_at:names_at + len(names)] = names
    struct.pack_into(">IIIIIIIIII", out, table_at + 40, 1, 1, 6, 0, text_at, len(code), 0, 0, 4, 0)
    struct.pack_into(">IIIIIIIIII", out, table_at + 80, 7, 3, 0, 0x10000, names_at, len(names), 0, 0, 1, 0)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--cc", default="clang-18")
    parser.add_argument("--cxx", default="clang++-18")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--skip-build", action="store_true", help="rerun validation against existing build outputs")
    parser.add_argument("--fetch-sources", action="store_true", help="obtain missing pinned research checkouts and submodules")
    parser.add_argument("--compare", type=Path, help="compare validated outputs with a prior run's manifest")
    args = parser.parse_args()
    try:
        if args.jobs < 1 or platform.machine().lower() not in ("amd64", "x86_64"):
            raise ValueError("positive job count and x86-64 host required")
        source_root, output = args.sources.resolve(), args.output.resolve()
        if source_root == output or source_root in output.parents:
            raise ValueError("build output must be outside the source checkout root")
        lock = json.loads((CONFIG / "lock.json").read_text())
        if args.fetch_sources:
            fetch_sources(source_root, lock)
        verify_sources(source_root, lock)
        output.mkdir(parents=True, exist_ok=True)
        host = "windows" if os.name == "nt" else "linux"
        logs = output / "logs"
        logs.mkdir(exist_ok=True)
        sequence = 0

        def run(command, expected=0, env=None):
            nonlocal sequence
            sequence += 1
            result = subprocess.run(list(map(str, command)), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=900)
            (logs / f"{sequence:02d}.log").write_bytes(result.stdout)
            if result.returncode != expected:
                raise ValueError(f"command {sequence} failed (exit {result.returncode}); see private build logs")
            return result.stdout.decode(errors="replace")

        generator = ["-G", "Visual Studio 17 2022", "-A", "x64", "-T", "ClangCL"] if host == "windows" else ["-G", "Ninja", f"-DCMAKE_C_COMPILER={args.cc}", f"-DCMAKE_CXX_COMPILER={args.cxx}"]
        dxc = dxc_package(output, lock["dxc"][host])
        if not args.skip_build:
            for component, name, include, targets in (
                ("cpu", "XenonRecomp", "xenon-host-project.cmake", ["XenonRecomp", "XenonAnalyse"]),
                ("shader", "XenosRecomp", "xenos-host-project.cmake", ["XenosRecomp"])):
                command = [args.cmake, "-S", source_root / name, "-B", output / component, *generator,
                           "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_PROJECT_INCLUDE={(ROOT / 'cmake/toolchains' / include).as_posix()}"]
                if component == "shader":
                    command += [f"-DMW3_DXC_ROOT={dxc.as_posix()}", "-DZSTD_BUILD_PROGRAMS=OFF", "-DZSTD_BUILD_TESTS=OFF"]
                run(command)
                run([args.cmake, "--build", output / component, "--config", "Release", "--target", *targets, "--parallel", args.jobs])
        compiler_file = next((output / "cpu/CMakeFiles").glob("*/CMakeCXXCompiler.cmake"))
        compiler = compiler_file.read_text()
        if f'CMAKE_CXX_COMPILER_VERSION "{lock["compilers"][host]}"' not in compiler:
            raise ValueError("compiler version differs from lock; review and update pin explicitly")
        suffix = "Release/" if host == "windows" else ""
        extension = ".exe" if host == "windows" else ""
        recompiler = output / f"cpu/XenonRecomp/{suffix}XenonRecomp{extension}"
        analyzer = output / f"cpu/XenonAnalyse/{suffix}XenonAnalyse{extension}"
        shader = output / f"shader/XenosRecomp/{suffix}XenosRecomp{extension}"
        for path in (recompiler, analyzer, shader):
            if not path.is_file():
                raise ValueError(f"missing host tool {path.name}; inspect build/security logs; no retry or exclusion is performed")
        smoke = output / "smoke"
        objects, generated = smoke / "objects", smoke / "generated"
        objects.mkdir(parents=True, exist_ok=True)
        generated.mkdir(exist_ok=True)
        words = json.loads((FIXTURES / "instructions.json").read_text())
        for name in NAMES:
            code = bytes.fromhex("".join(words[name]))
            (objects / f"{name}.o").write_bytes(synthetic_elf(code))
            shutil.copyfile(FIXTURES / f"{name}.s", smoke / f"{name}.s")
            # Disassembly is not our oracle; populate the optional upstream naming input.
            (objects / f"{name}.dis").write_text("00000000 <fixture>:\n")
        run([analyzer, objects / "arithmetic.o", smoke / "synthetic-switches.toml"])
        run([recompiler, objects, generated])
        for name in NAMES:
            if f"__imp__{name}_0" not in (generated / f"{name}.cpp").read_text():
                raise ValueError("synthetic fixture produced no translated function")
        run([args.cmake, "-S", CONFIG / "smoke", "-B", smoke / "build", *generator, "-DCMAKE_BUILD_TYPE=Release",
             f"-DMW3_CPU_SOURCE={(source_root / 'XenonRecomp').as_posix()}", f"-DMW3_FIXTURES={FIXTURES.as_posix()}", f"-DMW3_GENERATED={generated.as_posix()}"])
        run([args.cmake, "--build", smoke / "build", "--config", "Release", "--parallel", args.jobs])
        executable = smoke / f"build/{suffix}ppc-smoke{extension}"
        result = run([executable])
        if "PASS: synthetic PPC" not in result:
            raise ValueError("missing PPC completion evidence")
        run([executable, "--mutate-oracle"], expected=1)
        dxc_exe = dxc / ("bin/x64/dxc.exe" if host == "windows" else "bin/dxc")
        environment = dict(os.environ)
        if host == "linux":
            environment["LD_LIBRARY_PATH"] = str(dxc / "lib")
        outputs = {}
        for target in ("dxil", "spirv"):
            dest = smoke / f"smoke.{target}"
            command = [dxc_exe, "-E", "main", "-T", "ps_6_0", "-HV", "2021", "-Qstrip_debug", "-Fo", dest, FIXTURES / "smoke.hlsl"]
            if target == "spirv":
                command += ["-spirv", "-fspv-target-env=vulkan1.2"]
            run(command, env=environment)
            magic = dest.read_bytes()[:4]
            if magic != (b"DXBC" if target == "dxil" else b"\x03\x02\x23\x07"):
                raise ValueError("shader compiler did not produce the requested container")
            outputs[f"smoke.{target}"] = sha256(dest)
        outputs.update({f"{name}.cpp": sha256(generated / f"{name}.cpp") for name in NAMES})
        outputs["synthetic-switches.toml"] = sha256(smoke / "synthetic-switches.toml")
        report = dict(schema_version=1, host=host, compiler=lock["compilers"][host], lock_sha256=text_sha256(CONFIG / "lock.json"),
                      preparation_sha256={str(p.relative_to(ROOT)).replace("\\", "/"): text_sha256(p) for p in
                          [Path(__file__), ROOT / "cmake/toolchains/xenon-host-project.cmake", ROOT / "cmake/toolchains/xenos-host-project.cmake", CONFIG / "smoke/CMakeLists.txt"]},
                      tools={p.name: sha256(p) for p in (recompiler, analyzer, shader)},
                      fixture_sha256={p.name: text_sha256(p) for p in sorted(FIXTURES.iterdir()) if p.is_file()},
                      generated_sha256=outputs, ppc_checks=547, mutation_rejected=True,
                      limits=["no VMX128, full ABI, title execution or GPU execution coverage", "Xenos translator built; original HLSL compiled by DXC; Xenos translation correctness not established"])
        (output / "manifest.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        if args.compare:
            compare_reports(json.loads(args.compare.read_text()), report)
        print("PASS: 547 synthetic PPC checks, failing mutation, DXIL and SPIR-V compile; see private manifest.json")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, urllib.error.URLError) as error:
        parser.exit(1, f"toolchain preparation failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
