# Initial executable-inventory completion — 2026-11-17

Implementation checkpoint: `8c2ee14de3d97ee59769036e307209e21a3f69ce`. MW3-007's initial-inventory acceptance is satisfied; native-execution and full flow coverage remain open in downstream work. This closes neither a gameplay gate nor the unresolved runtime semantics listed in [the handoff](HANDOFF.md).

Both exact owned executables were analyzed twice with fresh Clang 18.1.3 Release/ASan/UBSan probe builds and the pinned preparation tools. The manifest compares complete metadata/input/library/compiler/source identities. Reports differ only by the repeat manifest's reference to its predecessor:

| Private report | SHA-256 |
| --- | --- |
| `title-analysis-control-f/report.json` | `3014152aa55ac6fe90f909a07e34c5d7efb5e3cf2d3541b9b085c4e986f6b5b1` |
| `title-analysis-control-g/report.json` | `9f3d50da3ccdc34d53ee07e7911692fa5c7d5d37b7069df8e173bd220e934084` |

Reproduce with the prior documented owned/source/toolchain arguments, `--sanitizers`, fresh `title-analysis-control-f` and `title-analysis-control-g` outputs, and `--compare '<first>/report.json'` on the second command. Upstream prepared archive objects remain uninstrumented; the maintained adapter/scanner and observed XEX loader source are instrumented. No guest code executed or raw image/instruction dump was written.

All five detected tables / 29 labels per executable independently agree on table base, index register, default and targets. Direct PPC field checks verify pointer construction, index scaling, load/CTR flow, bounded table reads and comparison/guard evidence. The check uses no XenonAnalyse/disassembler API. It records rather than assumes the range guard, supports r0 in RB while rejecting RA=0 as a register index, and permits a separated compare/guard. This does not prove dominance/reachability or discover omitted tables. All five tables remain in BINK; `.text` coverage is zero.

Acceptance evidence:

- Exact input/tool/source-bound addresses: manifests and [the maintained map](../../docs/engine/executables.md); no MW2 addresses copied.
- Independently inspected helpers: full matches checked through a table-driven decoder; standard encodings additionally assembled with LLVM as recorded in prior checkpoints.
- Independently inspected switches: all detected tables verified by the separate direct-field reader, with exact agreement above.
- Unknown targets and exception paths: private LR/CTR site inventories, all handler-bearing `.pdata` entries enumerated as unresolved, unverified setjmp/longjmp and `control_flow_complete=false`. No successful guest stubs or native title module exists.
- Deterministic repetition: enforced complete metadata comparison passed for both executables, with empty probe/analyzer error logs.

Linux `CXX=clang++-18 python3 tools/check.py --sanitizers` passes all **43 Python tests**, native CTest and scanner sanitizers with no skips. Windows Release native metadata build/CTest passes; the exact analysis suite passes with one explicit unavailable-LLVM-tools skip. The synthetic scanner now passes **2,363 checks** on both hosts, including wrong counts/guards, register/data-flow mutations, truncated code/table windows, unaligned/out-of-code targets and all prior ABI/import negatives. Differences between the original narrow checker and retail compiler layout were rejected diagnostically, corrected with r0 and separated-guard tests, and revalidated before accepting results.

Runtime timings, gameplay, exception implementation, dynamic dispatch coverage and production title generation remain **NOT VERIFIED / NOT IMPLEMENTED**. Proceed to the licensed, measured runtime comparison rather than hand-building a general engine analyzer first.
