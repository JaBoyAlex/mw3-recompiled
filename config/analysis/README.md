# Owned-title metadata analysis

This is an initial inventory tool, not a game runtime or complete control-flow analyzer. Use only the exact owned executable pair from the versioned identity manifest and the [verified host toolchain](../toolchains/README.md).

On Ubuntu/WSL, after successful toolchain preparation:

```sh
python3 config/analysis/analyze.py --owned '<private SP/MP directory>' --sources "$HOME/.cache/mw3-recompiled/sources" --toolchain "$HOME/.cache/mw3-recompiled/toolchain-a" --output "$HOME/.cache/mw3-recompiled/title-analysis-a"
```

Add `--sanitizers` to instrument the maintained adapter and synthetic scan tests with ASan/UBSan. Ubuntu's Clang 18 instrumentation needs `libclang-rt-18-dev`. The prepared upstream archives are not rebuilt/instrumented by this option. Repeat into a fresh directory with the same options and `--compare '<first directory>/report.json'`. Comparison requires identical input, analyzer, loader/decoder library, compiler, maintained analysis-source and complete metadata digests. It does not assert cross-directory binary bit identity or independent algorithm coverage.

The directory containing the two root executables can remain on the Windows drive under WSL; files are read-only. The script checks their exact hashes, the tool source/submodule revisions, preparation lock and analyzer binary hash. It then compiles a small metadata adapter against the prepared XenonUtils static library, records that library/probe identity, and captures image/import/switch observations. No guest code executes, decrypted image is dumped, key is logged, game data is uploaded, or original input is changed.

Use a new output directory each time. Logs, generated build files and full address inventories remain private; only sanitized observations and hashes belong in docs. The pinned upstream loader is not a hardened generic untrusted-file parser. Directly invoking `mw3-image-probe` bypasses the Python fingerprint guard and is unsupported for unknown files.

All detected entry/dispatch/target addresses must fall within executable sections. Invalid registers, empty targets or duplicate dispatches fail validation. These checks do not find omitted switch tables or prove import/function/ABI completeness. See [current findings and remaining work](../../docs/engine/executables.md).

The adapter now scans every executable section for all eight complete ABI save/restore ladders. Every register, offset and return/LR tail must match; candidates must fit inside one section. All candidates remain in the report, including missing/ambiguous families. A second, table-driven instruction decoder must agree with every instruction in each actual match. No candidate is automatically promoted to a production code-generation configuration.

Bounded `.pdata` parsing validates alignment, nonzero length, prologue extent, ordering and code-section containment. It reports overlaps and union coverage separately. The two high bits classify save millicode / normal / restore millicode / handler metadata as described by the pinned ReXGlue image reader. Handler metadata is counted, not interpreted or executed. Immediate-call and indirect-branch scans inspect aligned words in code sections; embedded data can resemble instructions. Canonical `blr` words are counted separately; they are not proof of valid returns. Indirect targets, nonlocal exits and exception paths remain unresolved.

Game-free scanner checks run through `tests/test_analysis.py` when CMake is on PATH. They compile on Windows/Linux without upstream sources or game files; Linux checks instrument the scanner. Tests reject every truncation and each one-word mutation of all helper patterns, non-code/unaligned/split-section matches, malformed `.pdata`, and branch-sign/wrap errors. When LLVM assembler/objcopy are available, a separate oracle assembles the six standard PowerPC helper families from original ABI mnemonics. VMX128 matches receive the separate decoder verification during owned-title analysis.

Standalone equivalent:

```sh
cmake -S config/analysis/probe -B out/scan-tests -DMW3_SCAN_TESTS_ONLY=ON -DMW3_SCAN_SANITIZERS=ON
cmake --build out/scan-tests
ctest --test-dir out/scan-tests --output-on-failure
```

Use `-C Debug` for CTest with a Windows multi-configuration build. The sanitizer option is supported on Linux; Windows scan tests use MSVC without it.
