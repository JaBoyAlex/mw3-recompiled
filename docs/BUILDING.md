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

No production recompile command/config is supplied before function/import/control-flow analysis and runtime selection. Never manufacture MW3 configs by replacing MW2 filenames and retaining guest addresses. Generated game code and flat/decrypted images stay outside Git and public CI. Reproducibility will include every input hash, compiler, transitive dependency, config and patch; bit-for-bit release binaries have not been demonstrated.
