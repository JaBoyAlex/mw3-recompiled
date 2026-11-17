# Bootstrap validation evidence

Date: 2026-11-17. These observations concern public tools and metadata only; **no MW3 execution or performance result is claimed**.

| Check | Result |
| --- | --- |
| Public native build, MSVC 19.44 x64 Debug | PASS |
| Public native build, MSVC 19.44 x64 Release | PASS |
| Native CTest parser suite in both configurations | PASS: big-endian metadata, truncation, invalid offsets, hostile count and 10,000 deterministic malformed cases |
| Python 3.12 unit suite | PASS: 22 tests, including disc bounds/path/cycle cases, immutable inventory, DAG/claims and benchmark provenance |
| Three repository skills, bundled skill validator | PASS; PyYAML 6.0.3 used only in ignored local validation directory |
| Nine research checkouts and license digests | PASS: `tools/upstreams.py verify` |
| Synthetic benchmark self-comparison | PASS: 0% p95 change; not a game measurement |
| Owner ISO/executable inspection | PASS for read-only metadata/hash capture, not ownership or gameplay verification |
| Initial upstream XenonRecomp MSVC tool build | FAILED: pinned source uses Clang builtins; native MSVC is not the chosen upstream host-tool compiler |
| Remote GitHub Windows/Linux/sanitizer workflows | Pending publication/run; update status from actual workflow evidence |
| Real title boot/gameplay/Steam/renderer enhancements | NOT RUN; no runtime exists yet |

Reproduce public checks with `python tools/check.py` and `python tools/check.py --config Release`, passing installed CMake/CTest paths if not on PATH. Synthetic comparator command: `python tools/benchmark.py qa/benchmarks/synthetic.json qa/benchmarks/synthetic.json`. Skill validation uses the host-provided validator; no nonstandard Python package is required by the project's own test tools.

Private ISO reports and extracted title inputs are under ignored workspace storage. Executable hashes and cross-reader metadata are recorded in docs/research/title-identity.md. Logs containing machine paths remain local. CMake presets and CI definitions are repeatable inputs, not evidence of bitwise reproducible release binaries.
