# Status — 2026-11-17

**Not playable. No MW3 gameplay, rendering, audio, Steam networking, DLSS or Reflex has been implemented or validated.** Four-player Survival is a requested planned extension, not an existing capability.

Implemented foundation:

- C++20 native bounded XEX metadata inspector and synthetic parser tests.
- Python owned-file SHA-256 inventory and bounded XDVDFS inspection; private executable extraction without overwriting originals.
- Dependency-DAG task catalog, filtered ready-task search, copyable prompts, issue export/idempotent sync and serialized-claim workflow definition.
- Game-free build/check driver, Windows/Linux CI definitions, three repository agent skills, contribution/architecture/research/testing/legal documentation.
- Frame-time export validation/comparison with provenance and noise handling; no real engine instrumentation or MW3 benchmark yet.
- Nine pinned upstream research checkouts; official REA included. Research pins do not imply integrated/runtime-ready dependencies.

Verified locally: Windows x64 MSVC 19.44 public native Debug build and CTest passed. Python 3.12: 22 unit tests passed. Supplied ISO hash and both title executable identities recorded; native and Python metadata readers used. Upstream XenonRecomp native MSVC build attempted and failed because the pinned project selects C++17 while using newer library/builtin behavior; toolchain compatibility remains open. No generated MW3 CPU module or complete function/import map exists yet.

Repository: [JaBoyAlex/mw3-recompiled](https://github.com/JaBoyAlex/mw3-recompiled), private initial research repository. CI and task administration must be checked after publication; workflow definitions alone are not successful runs. No branch-protection rule or trusted private game runner is configured. No game-linked binaries or SDKs are published.

Immediate dependencies: complete reproducible CPU/shader toolchain (MW3-006), verified SP/MP analysis (007), license/distribution assessment (003/031), reference matrix (004), then the runtime comparison (008). Steam AppID/SDK authorization (019) remains unresolved. The native-execution, original-gameplay, secure-network, enhancement and release gates are all open.

Select independent work using `python tools/project.py list --ready`, checking GitHub ownership before claiming. Every future status update must separate actual title execution from source inspection and synthetic tests.
