# Build and preparation

The public build is game-free. It builds `mw3-xex-inspect` and parser tests; it is not an MW3 executable. Python tools require only the standard library. Use Python 3.11+ and CMake 3.25+.

## Windows

Install Visual Studio 2022 Build Tools with Desktop C++, MSVC and a Windows SDK. The check driver selects the Visual Studio x64 generator without requiring a Developer shell:

```powershell
python tools/check.py
python tools/check.py --config Release
```

If CMake is only installed under Visual Studio, pass its actual paths using `--cmake` and `--ctest`; locate the installed tool directory rather than committing machine-specific absolute paths. An existing Codex bundled Python can run these tools; its path is machine-specific and not a project dependency. The Windows Store Python alias alone is not a Python installation.

For Ninja presets, start a compiler-ready Developer PowerShell, ensure CMake/Ninja are on PATH, then run `cmake --preset dev`, `cmake --build --preset dev` and `ctest --preset dev`.

## Linux and diagnostics

Install Git, Python, CMake, Ninja and GCC or Clang. Run `python3 tools/check.py`; optimized checks use `--config Release`. `--sanitizers` adds address/undefined-behavior sanitizers on supported GCC/Clang hosts. Windows MSVC sanitizer mode is deliberately refused by this initial driver. CI declares Windows/Linux Debug/Release plus Linux sanitizer jobs. Passing local Windows checks is not proof those remote jobs passed.

## Upstream research checkouts

`config/upstreams.lock.json` pins inspected revisions and license file digests. `python tools/upstreams.py fetch` obtains missing checkouts under ignored `.local/upstreams`, checks out detached commits and verifies identity. Existing dirty/mismatched checkouts are refused, not overwritten. `verify` is read-only. These checkouts are **not** vendored runtime dependencies; fetching them does not execute or build their code. Submodules/toolchain dependencies need their own pin/build manifest when adopted by MW3-006.

## Private title preparation

The initial tools fingerprint explicit files and inspect XDVDFS/XEX metadata without decryption. Example commands are in README. Reports do not certify legal ownership, complete disc integrity or supported runtime execution. `disc.py --extract-executables .local/game/rev1` copies the two known root executables exclusively; it refuses existing destinations. If interrupted, inspect/remove only your own partial output or choose a new private directory. It is a developer inspection tool, not the final transactional installer.

Never manufacture MW3 configs by replacing MW2 filenames and retaining guest addresses. Generated game code and flat/decrypted images stay outside Git and public CI. Bit-for-bit release binaries have not been demonstrated.

## Reproducible private generation (Linux/WSL)

The selected SDK profile currently prepares on Linux x86-64; this is not Windows
title validation or an installer. First prepare the exact sources, baseline SDK
and normal memory derivative using the [runtime guide](../experiments/runtime-bakeoff/README.md).
The preparation prints a manifest; use that exact **normal**, unsanitized
report. Do not use its validation-only core-sanitizer package for generation.

```sh
python3 tools/recompile.py --owned "$OWNED_PAIR" --bakeoff-root "$BAKEOFF_CACHE" --sdk-report "$NATIVE_PREPARATION_REPORT" --cache "$PRIVATE_GENERATION_CACHE"
python3 tools/recompile.py --owned "$OWNED_PAIR" --bakeoff-root "$BAKEOFF_CACHE" --sdk-report "$NATIVE_PREPARATION_REPORT" --cache "$PRIVATE_GENERATION_CACHE" --reproduce
```

Use a private cache outside Git, or in a Git-ignored directory such as `.local/`.
It must not overlap the owned inputs or traverse symlinks. The driver checks
both executable hashes before any cache write, verifies pinned source/submodule
and derivative identities, hashes the complete SDK inputs and system libraries,
and binds the exact recipe/driver/helper hashes. SDK-adjacent `bin/logs/` is
excluded as observation data; new logs/profiles use each attempt's own roots.
Each key has an exclusive writer lock. A crashed writer's lock is retained:
inspect its PID/attempt, verify that writer has ended, then remove only that
lane's stale lock. The tool never deletes another writer's lock automatically.

The versioned [recipe](../config/recomp/recipe.json) requests exact vector and
scalar-estimate math with conservative register/context handling. This selects
upstream emission behavior; it does not independently prove console accuracy.
Manual addresses, includes, hooks, shims and unreviewed optimization settings
are refused. Automatic function discovery still has unresolved control flow;
generation success is not a full target/exception/VMX validation. No `--force`
or successful import stubs are used. SDK load/normalize behavior is private
preparation, not a title boot or DRM/SDK bypass.

A cache hit rehashes every payload file, including generated ancillary files;
modified/missing/extra files fail rather than being overwritten. `--reproduce`
generates both modules in a fresh attempt and compares the byte hashes and
sizes of **all generated C++/headers** with the existing code manifest.
Absolute-path dependency files, logs and SDK stamps remain hashed per attempt
but are not claimed byte-identical between attempts. Both attempts and failures
remain private. No generated code is edited as maintained source. The current
SDK receipt is local provenance, not a signed build attestation or redistribution
approval; compiler/build timestamps can change SDK binaries and cache keys.
