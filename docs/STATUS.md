# Status — 2026-11-17

**Not playable. No MW3 gameplay, rendering, audio, Steam networking, DLSS or Reflex has been implemented or validated.** Four-player Survival is a requested planned extension, not an existing capability.

Implemented foundation:

- C++20 native bounded XEX metadata inspector and synthetic parser tests.
- Python owned-file SHA-256 inventory and bounded XDVDFS inspection; private executable extraction without overwriting originals.
- Dependency-DAG task catalog, filtered ready-task search, copyable prompts, issue export/idempotent sync and serialized-claim workflow definition.
- Game-free build/check driver, Windows/Linux CI definitions, three repository agent skills, contribution/architecture/research/testing/legal documentation.
- Frame-time export validation/comparison with provenance and noise handling; no real engine instrumentation or MW3 benchmark yet.
- Nine pinned upstream research checkouts; official REA included. Research pins do not imply integrated/runtime-ready dependencies.
- Verified CPU/shader host preparation on Ubuntu/WSL, with pinned transitive sources/compiler/DXC and identical generated outputs from two clean builds.
- Exact owned SP/MP pair verification that rejects missing, mixed, modified and wrong-format inputs.
- Complete ABI helper-ladder scanning with independent instruction decoding, bounded `.pdata` inventory and explicit unresolved LR/CTR branch reports.
- Pre-normalization import audit, complete value/thunk grouping, variable-import identification and unwind/context-service cross-references.

Verified locally: the Linux game-free suite passes all 42 Python tests, native CTest and ASan/UBSan checks. The scanner's 2,303 synthetic checks pass on Linux and Windows MSVC; LLVM independently assembled the six standard helper families on Linux. Windows Release metadata builds/CTest pass; its LLVM assembly oracle is explicitly skipped when unavailable. The canonical host toolchain passed 547 executable synthetic PPC checks, a failing oracle mutation, and DXIL/SPIR-V compilation in two clean builds. The owner-restored Windows analyzer passed a synthetic input; a newer native copy remains blocked by Defender. No security setting was changed. See [toolchain evidence](../config/toolchains/validation-2026-11-17.md).

Actual owned-title analysis finds all eight ABI helper families uniquely in each executable; the table-driven decoder agrees with every instruction. Bounded `.pdata` parsing identifies 15,024 Campaign / 15,951 Multiplayer entries, including 310 / 322 with handler metadata. The import audit reads 529 / 537 original records, classifying 258 / 262 function pairs and **13 kernel data variables per image**, with no unknown header-declared ordinals/types. Function identities agree with the normalizing loader; an independent Python struct reader confirms raw header identities/versions and all record addresses. Runtime support/version compatibility remains unverified. Two fresh sanitized observed-loader builds produce identical metadata; prepared archives remain uninstrumented. Five detected switch tables and 29 targets per executable are **all in BINK video code**, providing no measured main-engine switch coverage. See [the executable map](engine/executables.md). Thousands of indirect branch sites and further direct-call targets remain unclassified. **No MW3 guest code has executed and no native game module exists.**

Repository: [JaBoyAlex/mw3-recompiled](https://github.com/JaBoyAlex/mw3-recompiled), private initial research repository. [Initial CI](https://github.com/JaBoyAlex/mw3-recompiled/actions/runs/44049711442) passed all five Windows/Linux Debug/Release and sanitizer jobs. [Task publication](https://github.com/JaBoyAlex/mw3-recompiled/actions/runs/44049774225) succeeded and created 35 labeled issues with dependencies/prompts. No branch-protection rule or trusted private game runner is configured. No game-linked binaries or SDKs are published. [Friends can begin independent work now](FRIENDS-START-HERE.md).

MW3-002 and MW3-006 have merged through green CI. MW3-007 remains in progress: helper locations and header-declared import identity are verified; remaining work is representative switch decoding, main-engine dispatch and nonlocal/exception evidence. The inventory identifies unwind/context service call words without claiming setjmp/longjmp identities. Runtime comparison (008) remains gated by 003/005/007; license/distribution assessment (031) and reference cases (004) can progress independently. Steam AppID/SDK authorization (019) remains unresolved. The native-execution, original-gameplay, secure-network, enhancement and release gates are all open.

Select independent work using `python tools/project.py list --ready`, checking GitHub ownership before claiming. Every future status update must separate actual title execution from source inspection and synthetic tests.
