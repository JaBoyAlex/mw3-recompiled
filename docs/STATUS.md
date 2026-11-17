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

Verified locally: Windows x64 MSVC 19.44 public native builds/CTest and 35 Python unit tests passed across the integrated foundation and initial analysis changes. The canonical host toolchain passed 547 executable synthetic PPC checks, a failing oracle mutation, and DXIL/SPIR-V compilation in two clean builds. The owner-restored Windows analyzer passed a synthetic input; a newer native copy remains blocked by Defender. No security setting was changed. See [toolchain evidence](../config/toolchains/validation-2026-11-17.md).

Actual owned-title metadata analysis has begun: both images contain 13 sections, and the pinned loader resolves 258 SP / 262 MP import symbols. Windows/Linux analyzer data matches: five detected switch tables and 29 targets per executable, with targets in code. See [the executable map](engine/executables.md). This is not complete control-flow/import coverage. **No MW3 guest code has executed and no native game module exists.**

Repository: [JaBoyAlex/mw3-recompiled](https://github.com/JaBoyAlex/mw3-recompiled), private initial research repository. [Initial CI](https://github.com/JaBoyAlex/mw3-recompiled/actions/runs/44049711442) passed all five Windows/Linux Debug/Release and sanitizer jobs. [Task publication](https://github.com/JaBoyAlex/mw3-recompiled/actions/runs/44049774225) succeeded and created 35 labeled issues with dependencies/prompts. No branch-protection rule or trusted private game runner is configured. No game-linked binaries or SDKs are published. [Friends can begin independent work now](FRIENDS-START-HERE.md).

MW3-002 and MW3-006 have merged through green CI. Active next work is MW3-007: verify helper families, function/indirect-flow coverage and complete import identity. License/distribution assessment (003/031) and the reference matrix (004) remain independent open work before the runtime comparison (008). Steam AppID/SDK authorization (019) remains unresolved. The native-execution, original-gameplay, secure-network, enhancement and release gates are all open.

Select independent work using `python tools/project.py list --ready`, checking GitHub ownership before claiming. Every future status update must separate actual title execution from source inspection and synthetic tests.
