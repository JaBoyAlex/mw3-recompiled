#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Generate immutable private MW3 modules; never compile, run or publish them."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import uuid

from verify_inputs import DEFAULT, verify

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments/runtime-bakeoff"
sys.path.insert(0, str(EXPERIMENT))
from prepare import sha, verify_source
from mw2_tools import derive
from inspect_owned import generator_errors

RECIPE = ROOT / "config/recomp/recipe.json"
VECTOR_KEYS = {"vmaddfp", "vnmsubfp", "vmsum3fp128", "vmsum4fp128", "vrefp",
               "vrsqrtefp", "vexptefp", "fres", "frsqrte"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def validate_recipe(value):
    expected = {"schema_version", "runtime", "title", "max_file_size_bytes",
                "max_discovery_iterations", "max_vtable_iterations", "max_resolve_iterations",
                "register_locals", "forward_stack_stores", "manual_code_targets", "vector_math"}
    if set(value) != expected or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("unknown recipe fields/version")
    if value["runtime"] != "rexglue-sdk" or value["title"] != "mw3-xbox360-usa-korea-rev1":
        raise ValueError("unreviewed runtime/title recipe")
    if value["register_locals"] is not False or value["forward_stack_stores"] is not False or value["manual_code_targets"] != []:
        raise ValueError("unreviewed register optimization or code targets")
    if value["vector_math"] != dict.fromkeys(VECTOR_KEYS, "exact"):
        raise ValueError("all supported vector/estimate modes must be explicitly exact")
    for key, expected in (("max_file_size_bytes", 1048576), ("max_discovery_iterations", 1000),
                          ("max_vtable_iterations", 1000), ("max_resolve_iterations", 1000)):
        if type(value[key]) is not int or value[key] != expected:
            raise ValueError("unreviewed generation limit")
    return value


def no_symlink_path(path):
    """Refuse redirected writable roots, including a symlink in an ancestor."""
    path = Path(os.path.abspath(path))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("symlink in private output path")
    # Resolve Windows short-name aliases too, so both sides of every overlap
    # comparison identify the same directory (RUNNER~1 versus runneradmin).
    return path.resolve()


def private_cache(path, owned):
    path = no_symlink_path(path)
    owned = Path(owned).resolve()
    if path.is_relative_to(owned) or owned.is_relative_to(path):
        raise ValueError("cache overlaps owned input tree")
    # Outputs inside any Git worktree must be ignored, including future children.
    parent = path
    while not parent.exists():
        parent = parent.parent
    found = subprocess.run(["git", "-C", str(parent), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
    if found.returncode == 0:
        repository = Path(found.stdout.strip()).resolve()
        for probe in (path, path / "candidate.cpp"):
            result = subprocess.run(["git", "-C", str(repository), "check-ignore", "--no-index", "--quiet", str(probe)],
                                    capture_output=True)
            if result.returncode != 0:
                raise ValueError("private cache is not ignored by its Git repository")
    return path


def snapshot(directory, *, internal_links=False):
    """Hash every file; no devices, external links, or redirected directories."""
    if Path(directory).is_symlink():
        raise ValueError("redirected artifact root")
    directory = Path(directory).resolve()
    result = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        if path.is_symlink():
            if not internal_links or not path.resolve().is_relative_to(directory) or not path.is_file():
                raise ValueError("symlink in artifact tree")
            result[relative] = dict(sha256=sha(path), link=os.readlink(path))
        elif path.is_file():
            result[relative] = dict(sha256=sha(path), bytes=path.stat().st_size)
        elif not path.is_dir():
            raise ValueError("nonregular artifact")
    if not result:
        raise ValueError("empty artifact tree")
    return result


@contextmanager
def writer_lock(cache, key):
    lock = no_symlink_path(cache / (key + ".lock"))
    # Exclusive creation is cross-process. Never auto-delete another writer's lock.
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(dict(pid=os.getpid(), key=key), stream)
        yield
    finally:
        lock.unlink()


def read_cache(directory, key, inputs):
    no_symlink_path(directory)
    manifest_path = directory / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("redirected cache manifest")
    value = json.loads(manifest_path.read_text())
    fields = {"schema_version", "key", "inputs", "files", "code_manifest", "guest_executed", "runtime_supported", "release_package"}
    if (set(value) != fields or type(value.get("schema_version")) is not int or value["schema_version"] != 1
            or value.get("key") != key or value.get("inputs") != inputs
            or any(value.get(name) is not False for name in ("guest_executed", "runtime_supported", "release_package"))):
        raise ValueError("cache identity mismatch")
    actual = snapshot(directory / "payload")
    if value.get("files") != actual:
        raise ValueError("cache changed; preserve it for diagnosis and use a new cache")
    if {p.name for p in directory.iterdir()} != {"manifest.json", "payload"}:
        raise ValueError("unexpected cache entries")
    expected_code = {name: row for name, row in actual.items() if name.endswith((".cpp", ".h"))}
    if not expected_code or value.get("code_manifest") != expected_code:
        raise ValueError("invalid generated-code manifest")
    return value


def toolchain(root, report_path):
    lock = json.loads((EXPERIMENT / "pins.json").read_text())
    source = verify_source(root / "sources/rexglue-sdk", next(s for s in lock["sources"] if s["name"] == "rexglue-sdk"))
    for name in ("headers", "vma"):
        verify_source(root / "sources" / name, next(s for s in lock["sources"] if s["name"] == name))
    pin = lock["rexglue_memory_derivative"]
    derivative = derive(root / "sources/rexglue-memory", EXPERIMENT / pin["patch_path"], pin)
    report = json.loads(report_path.read_text())
    if (report.get("status") != "PASS" or report.get("source") != derivative
            or report.get("codegen_compatible") is not True or report.get("core_sanitizers") is not False
            or report.get("script_sha256") != sha(EXPERIMENT / "prepare_rexglue_memory.py")
            or report.get("pins_sha256") != sha(EXPERIMENT / "pins.json")):
        raise ValueError("unreviewed, stale or validation-only SDK preparation")
    sdk = Path(report["sdk_prefix"]).resolve()
    for name, expected in report["final_libraries"].items():
        if Path(name).name != name or sha(sdk / "lib" / name) != expected:
            raise ValueError("SDK library identity mismatch")
    if set(report["replaced_libraries"]) != {"librexbase.so", "librexppc.so", "librexkernel.so"}:
        raise ValueError("unexpected derivative components")
    # Earlier experiments may have created SDK-adjacent logs. They are runtime
    # observations, never toolchain inputs. New runs redirect them privately.
    files = {name: row for name, row in snapshot(sdk, internal_links=True).items()
             if not name.startswith("bin/logs/")}
    if "bin/rexglue" not in files:
        raise ValueError("SDK code generator missing")
    env = {k: v for k, v in os.environ.items() if not k.startswith("LD_")}
    env["LD_LIBRARY_PATH"] = str(sdk / "lib")
    linked = subprocess.run(["ldd", str(sdk / "bin/rexglue")], env=env,
                            capture_output=True, text=True, check=True, timeout=10).stdout
    if "not found" in linked:
        raise ValueError("missing generator runtime dependency")
    system_libraries = {}
    for name in re.findall(r"(?:=>\s+)?(/\S+)\s+\(", linked):
        path = Path(name).resolve()
        if not path.is_relative_to(sdk):
            system_libraries[str(path)] = sha(path)
    if not system_libraries:
        raise ValueError("generator system-library inventory empty")
    return sdk, dict(source=source, derivative=derivative, preparation_sha256=sha(report_path),
                     sdk_files=files, sdk_tree_sha256=digest(files), system_libraries=system_libraries,
                     host=dict(system=platform.system(), machine=platform.machine(), python=sys.version),
                     pins_sha256=sha(EXPERIMENT / "pins.json"))


def manifest_text(role, owned, recipe):
    # Stable relative output, separate owned source. No includes, addresses or shims.
    lines = ["[project]", "name = " + json.dumps("mw3_" + role),
             "game_root = " + json.dumps(str(owned)), "", "[vector_math]"]
    lines += [name + ' = "exact"' for name in sorted(recipe["vector_math"])]
    lines += ["", "[entrypoint]", "file_path = " + json.dumps(str(owned / ("default.xex" if role == "sp" else "default_mp.xex"))),
              'out_directory_path = "generated"', "ctr_as_local = false", "xer_as_local = false",
              "reserved_as_local = false", "cr_as_local = false", "non_argument_as_local = false",
              "non_volatile_as_local = false", "forward_stack_stores = false", ""]
    return "\n".join(lines)


def generate(output, sdk, owned, recipe):
    payload = output / "payload"
    payload.mkdir()
    for role in ("sp", "mp"):
        lane = payload / role
        lane.mkdir()
        (lane / "generated").mkdir()
        config = lane / "manifest.toml"
        text = manifest_text(role, owned, recipe)
        config.write_text(text)
        command = [str(sdk / "bin/rexglue"), "codegen", str(config)]
        for name in ("max_file_size_bytes", "max_discovery_iterations", "max_vtable_iterations", "max_resolve_iterations"):
            command += ["--" + name, str(recipe[name])]
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LD_", "ASAN_", "UBSAN_", "LSAN_", "REX_"))}
        env.update(LD_LIBRARY_PATH=str(sdk / "lib"), XDG_CONFIG_HOME=str(lane / "config"), TMPDIR=str(lane),
                   REX_APP_ROOT=str(lane / "app"), REX_APP_USER_ROOT=str(lane / "user"),
                   REX_APP_LOG_ROOT=str(lane / "logs"))
        with (lane / "codegen.log").open("wb") as log:
            result = subprocess.run(command, cwd=lane, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        diagnostic = (lane / "codegen.log").read_text(errors="replace")
        if result.returncode or generator_errors(diagnostic):
            raise ValueError(f"{role}: generator failed; inspect private log")
        # The SDK may add project SDK metadata; retain its final config in payload.
        if not any((lane / "generated").glob("*.cpp")) or not any((lane / "generated").glob("*.h")):
            raise ValueError(f"{role}: generator emitted no native module")
    return snapshot(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("owned", "cache", "bakeoff-root", "sdk-report"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--reproduce", action="store_true", help="clean-generate again, retaining a private comparison attempt")
    args = parser.parse_args()
    attempt = None
    try:
        if platform.system() != "Linux" or platform.machine() != "x86_64":
            raise ValueError("selected SDK profile currently supports Linux x86-64 preparation only")
        identity = verify(args.owned, json.loads(DEFAULT.read_text()))  # before any cache writes
        recipe = validate_recipe(json.loads(RECIPE.read_text()))
        sdk, compiler = toolchain(args.bakeoff_root.resolve(), args.sdk_report.resolve())
        inputs = dict(title=identity, recipe=recipe, toolchain=compiler, recipe_sha256=sha(RECIPE),
                      driver_sha256=sha(__file__), title_manifest_sha256=sha(DEFAULT),
                      helper_sha256={name: sha(EXPERIMENT / name) for name in ("prepare.py", "mw2_tools.py", "inspect_owned.py")})
        key = digest(inputs)
        cache = private_cache(args.cache, args.owned)
        cache.mkdir(parents=True, exist_ok=True)
        destination = cache / key
        no_symlink_path(destination)
        with writer_lock(cache, key):
            previous = read_cache(destination, key, inputs) if destination.exists() else None
            if previous is not None and not args.reproduce:
                print(json.dumps(dict(status="CACHE_HIT", key=key, directory=str(destination), guest_executed=False)))
                return 0
            attempt = cache / ("attempt-" + uuid.uuid4().hex)
            attempt.mkdir()
            print(json.dumps(dict(status="GENERATING", key=key, attempt=str(attempt), guest_executed=False)), flush=True)
            files = generate(attempt, sdk, args.owned.resolve(), recipe)
            verify(args.owned, json.loads(DEFAULT.read_text()))
            # Rehash dependencies after generation; don't publish output from a changed SDK.
            _, after = toolchain(args.bakeoff_root.resolve(), args.sdk_report.resolve())
            if after != compiler:
                raise ValueError("toolchain changed during generation")
            value = dict(schema_version=1, key=key, inputs=inputs, files=files,
                         code_manifest={name: row for name, row in files.items() if name.endswith((".cpp", ".h"))},
                         guest_executed=False, runtime_supported=False, release_package=False)
            (attempt / "manifest.json").write_text(json.dumps(value, indent=2, sort_keys=True)+"\n")
            if previous is not None:
                if previous["code_manifest"] != value["code_manifest"]:
                    raise ValueError("clean generation differs; both private attempts retained")
                status = "REPRODUCED"
            else:
                if destination.exists():
                    raise ValueError("cache destination appeared; no output overwritten")
                attempt.rename(destination)
                status = "GENERATED"
            print(json.dumps(dict(status=status, key=key, directory=str(destination),
                                  code_files=len(value["code_manifest"]), guest_executed=False)))
            return 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration, subprocess.SubprocessError) as error:
        parser.exit(1, f"private generation refused: {error}; attempt={attempt}\n")


if __name__ == "__main__":
    raise SystemExit(main())
