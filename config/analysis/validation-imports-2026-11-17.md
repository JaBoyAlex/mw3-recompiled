# Original import audit — 2026-11-17

Task MW3-007 remains **in progress**. Implementation checkpoint: `0d47c6e4d4baf8535451e1b0c91b3031e4500b26`. Documentation changes after that commit do not change analysis inputs. No guest code executed, runtime selected or production title code generated.

The driver uses the exact owned executable hashes documented in [the map](../../docs/engine/executables.md), the canonical Clang 18.1.3 preparation and pinned XenonRecomp source/submodules. It privately compiles a licensed copy of the pinned XEX loader with one read-only observer inserted before normalization. All other loader logic is unchanged; its source digest, export-table digests, maintained sources and linked archives are recorded in each private manifest. The upstream checkout remains clean.

Two fresh Release builds with ASan/UBSan passed on both owned files and produced identical full metadata. The instrumented code now includes the private observed XEX loader; remaining prepared archive objects are not instrumented. Probe/analyzer error logs are empty.

| Private report | SHA-256 |
| --- | --- |
| `title-analysis-imports-c/report.json` | `eb38c5d882c0f95c67eec723de1a2251f33665ba31c351aa4736e53065f522ea` |
| `title-analysis-imports-d/report.json` | `8a956d046ba7f6c9baf45dfd0d14aba405337fe777cce7c2dace5c386855c223` |

The repeat manifest records the first manifest's hash, so the report files themselves differ. Its complete metadata/source/tool/library/compiler comparison passed. This does not establish independent algorithm coverage or runtime performance.

Reproduce after canonical toolchain preparation, using fresh private output directories:

```sh
python3 config/analysis/analyze.py --owned '<private verified pair>' --sources "$HOME/.cache/mw3-recompiled/sources" --toolchain "$HOME/.cache/mw3-recompiled/toolchain-clean-a" --sanitizers --output "$HOME/.cache/mw3-recompiled/title-analysis-imports-c"
python3 config/analysis/analyze.py --owned '<private verified pair>' --sources "$HOME/.cache/mw3-recompiled/sources" --toolchain "$HOME/.cache/mw3-recompiled/toolchain-clean-a" --sanitizers --output "$HOME/.cache/mw3-recompiled/title-analysis-imports-d" --compare "$HOME/.cache/mw3-recompiled/title-analysis-imports-c/report.json"
```

Observed: 529 Campaign / 537 Multiplayer import records form 258 / 262 function pairs and 13 named kernel variable imports per module. No header-declared ordinal is absent from the pinned export tables; no unknown types or malformed known groups were observed. The separate normalizing-loader symbol list matches every original function identity/address. An independent read-only Python `struct` inspection of the original XEX optional/import headers (`>II`, `>III`, `>IIIHH`, record-address arrays) confirmed both library names/IDs/version fields/name indices, record order and all 529 / 537 addresses. This second reader did not decode the image or verify runtime implementations.

Both modules contain three direct-call words to imported `RtlUnwind` and one to `RtlCaptureContext`, each within a distinct declared `.pdata` range. These are private navigation hints, not setjmp/longjmp identifications. All five analyzer-detected switches per module lie in `BINK`, with none in main `.text`; gameplay switch coverage remains unestablished.

Validation:

- Linux separate clean checkout: `CXX=clang++-18 python3 tools/check.py --sanitizers` — **PASS**, all 42 Python tests, native CTest and scanner sanitizers, no skips.
- Windows MSVC 19.44: `python tools/check.py --config Release` with VS CMake on PATH — **PASS**, native CTest and 42-test suite with one explicit skip (LLVM assembler/objcopy unavailable).
- Synthetic scanner/header/record harness — **PASS**, 2,303 checks on both hosts, including every truncation, declared padding, reordered library name indices, duplicate/unaligned/unmapped records, truncated or non-code thunks, unknown record-kind preservation, malformed extents and existing ABI/branch cases.
- Python negatives — **PASS**: observer insertion refuses absent/duplicate anchors; type-0 function slots are not misclassified as variables; unknown/malformed groups remain diagnostic; loader identity disagreement and changed repeat-manifest identities are refused. Unwind cross-references never claim a verified nonlocal function.
- Artifact heuristic, task DAG, diff checks and manual source/data provenance review — **PASS**. No title bytes, keys, SDKs, generated title code or raw private reports are committed.

Header-declared name coverage is not dynamic-lookup coverage, ABI compatibility, working imports, exception support, native execution or a performance result. Those remain **NOT VERIFIED / NOT IMPLEMENTED**.
