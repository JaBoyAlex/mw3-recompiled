# ABI helper and function-metadata validation — 2026-11-17

Task MW3-007 remains **in progress**. No guest code executed. This checkpoint verifies helper locations and bounded metadata scans; import completeness, nonlocal exits, exception handling and indirect-target resolution remain unfinished.

## Maintained code and owned-title evidence

Implementation checkpoint: `ebfde788741fb078ee689db718fb1b1bf1b53be0`. Later documentation changes do not alter the analysis inputs. The private manifests record normalized hashes of the Python driver, CMake configuration, C++ adapter, scanner and synthetic harness. The exact owned executable identities and observed addresses are in [the executable map](../../docs/engine/executables.md).

Two fresh Release probe builds with Clang **18.1.3**, ASan/UBSan and the canonical pinned CPU toolchain produced identical complete Campaign and Multiplayer metadata. Every instruction of all eight unique helper matches in each image passed the table-driven decoder comparison. Both runs completed with empty probe sanitizer/error logs. The prepared upstream archives were not instrumented by this option.

Private manifests:

| Report | SHA-256 |
| --- | --- |
| First (`title-analysis-helpers-e/report.json`) | `d2eaa6640e8dc897eb9182b069b141a9c49cf4b271ea7f07669508e41df1988a` |
| Repeat (`title-analysis-helpers-f/report.json`) | `3806dc6896b5cd5a9fa1fcbf94db76f5bcc93985b99164528cf609531e37b2fc` |

The repeat manifest includes the first manifest's digest, so the manifest files themselves differ. Its enforced metadata/library/compiler/source comparison passed. This is deterministic repetition with the same pinned loader/decoder/analyzer, not an independent implementation of every analysis stage.

Reproduction, after the documented canonical toolchain preparation:

```sh
python3 config/analysis/analyze.py --owned '<private verified pair>' --sources "$HOME/.cache/mw3-recompiled/sources" --toolchain "$HOME/.cache/mw3-recompiled/toolchain-clean-a" --sanitizers --output "$HOME/.cache/mw3-recompiled/title-analysis-helpers-e"
python3 config/analysis/analyze.py --owned '<private verified pair>' --sources "$HOME/.cache/mw3-recompiled/sources" --toolchain "$HOME/.cache/mw3-recompiled/toolchain-clean-a" --sanitizers --output "$HOME/.cache/mw3-recompiled/title-analysis-helpers-f" --compare "$HOME/.cache/mw3-recompiled/title-analysis-helpers-e/report.json"
```

Outputs must not already exist. Keep complete inventories/logs local; none are uploaded with the source PR.

## Game-free checks

- Linux separate clean checkout: `CXX=clang++-18 python3 tools/check.py --sanitizers` — **PASS**, all 39 Python tests and native CTest, no skips. Includes an LLVM 18 assembly oracle for the six standard PowerPC helper families.
- Windows MSVC 19.44: `python tools/check.py --config Release` with Visual Studio CMake on PATH — **PASS**, native build/CTest and 39-test suite with one explicit skip (LLVM assembler/objcopy unavailable).
- Windows Debug native metadata build/CTest — **PASS**. Standalone scanner tests separately compiled and passed with MSVC.
- Original synthetic scanner harness — **PASS**, 2,115 checks on both hosts. Exercises complete patterns, every truncation and one-word corruption, ambiguity, non-code/unaligned/split-section rejection, invalid `.pdata`, and immediate-branch sign/absolute/wrap semantics.
- Repeat comparison negative tests mutate every compared identity field — **PASS**, each mismatch refused.
- Repository artifact heuristic, task DAG and manual provenance review — **PASS**. Tests contain original synthetic ABI examples; no title bytes, keys, generated title code or SDKs are committed.

Environment corrections: the first sanitizer link attempt identified a missing Ubuntu `libclang-rt-18-dev` package; installing it from the signed Ubuntu repository resolved the build. A full repository check launched in a Windows-created worktree under Linux Git failed before tests because of its drive-letter `.git` path; a separate Linux clone passed. Neither correction changes game files or Windows security settings.

Actual gameplay, native title generation, runtime performance, Steam/SDR, rendering and launcher integration — **NOT RUN / NOT IMPLEMENTED**. This checkpoint provides no runtime performance result and does not select a runtime.
