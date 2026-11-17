# Measurement evidence tooling validation — 2026-11-17

Implementation checkpoint: `5f38eafff63eaaa8971eb922e84cfb9248b45679`. MW3-005 validates an export/comparison contract; no game collector or real MW3 measurement is represented. All source-controlled examples and test traces are original synthetic data.

- Windows MSVC 19.44: `python tools/check.py --config Release` with Visual Studio CMake on PATH — **PASS**, 56 Python tests and native Release CTest. Two explicit skips: LLVM assembler/objcopy unavailable and file-symlink creation unavailable to this host user.
- Linux separate clean checkout: `CXX=clang++-18 python3 tools/check.py --sanitizers` — **PASS**, all 56 tests, native CTest and scanner sanitizer checks, no skips. Includes the trace symlink-escape case and LLVM fixture oracle.
- `python tools/benchmark.py qa/benchmarks/synthetic-v2.json qa/benchmarks/synthetic-v2.json` — **PASS**, exit 0, explicitly `synthetic: true`, three runs/nine samples, p50/p95/p99 10 ms, zero change and `raw_trace_integrity_verified: false`. These are example numbers, not MW3 performance.
- CLI negatives — **PASS**, exit 1 for regression/noise and 2 for invalid/incomparable input; legacy schema 1 real-data claims refused. Existing schema-1 synthetic/API tests remain compatible.
- Schema/integrity negatives — **PASS**: missing identities, bad hashes/units, NaN/infinity, booleans/negative/fractional samples, repeated run/trace identities, traversal/drive paths, wrong raw-file hashes, changed loaded metadata and unverified real-data dictionaries refused. Valid original temporary trace files exercise the real-validation code path without claiming actual game capture.
- Comparison cases — **PASS**: runs receive equal weight despite different trace lengths; timing and memory remain distinct; memory budgets use worst peaks; zero baselines/large finite values produce no nonfinite JSON; view/configuration/cache/compiler/method/input mismatches rejected; build/artifact/source/flags may differ as the intended tested change.
- Task DAG, artifact heuristic, diff checks and manual example/trace provenance review — **PASS**. Real traces remain private and are neither copied nor uploaded by the tool.

Reports bind exact export bytes, so whitespace/checkout line endings can change the export SHA without changing parsed example statistics. This is deliberate; no cross-host byte identity is asserted for differently serialized JSON. Trace hashes always refer to the actual raw file bytes.

`raw_trace_integrity_verified` establishes existence/hash integrity at load time, not sample derivation, truthful metadata, representative gameplay or statistical significance. Reports retain `sample_derivation_verified=false` and `statistical_confidence=not-estimated`. Real instrumentation, reference cases and same-work runtime timing remain downstream work.
