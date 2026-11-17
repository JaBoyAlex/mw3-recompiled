# Dependency-driven roadmap

The task DAG in `tasks/` is authoritative. `python tools/project.py list --ready` shows locally unblocked work. GitHub ownership still applies. Phase numbers describe feature maturity, not a ban on independent research, tooling, licensing or test design in parallel. Epics must be split into small tasks before implementation claims.

| Phase | Exit evidence | Main tasks |
| --- | --- | --- |
| 1. Foundations | Verified file identity, contributor flow, reproducible toolchain and reference/measurement contracts | 001–006, 019, 030–032, 035 |
| 2. Native execution | Chosen runtime, reproducible title generation, memory/thread/device services, real menu/scene, stable repeated shutdown | 007–014 |
| 3. Original gameplay | All required missions/modes/maps, native split-screen, saves/controllers and local system link | 015–018 |
| 4. Secure Steam networking | Audited legacy parsing, authenticated private invites, verified relay through two-household CGNAT | 020–022 |
| 5. Graphics and latency | Profiled renderer improvements, correct temporal inputs, optional DLSS/DLAA and Reflex with fallback | 023–026 |
| 6. Finish and release | All-mode regressions, performance budgets, installer recovery, provenance and permitted distribution | 027–029 |

The owner requested four-player Survival as an additional feature. MW3-033 audits feasibility after the original two-player mode is stable; MW3-034 implements and verifies local and online four-player behavior after session transport is stable. Release acceptance includes this extension unless the owner explicitly accepts a documented limitation. It cannot replace the original parity gate.

Start three independent lanes after the foundation: toolchain (006), reference cases (004) and research/performance contracts (005/030/032). Lead handles baseline identity, legal blockers and interfaces. After analysis, CPU/kernel work precedes GPU and platform branches; the latter can proceed in separate scopes. Campaign, Spec Ops and MP verification can run independently after the harness/native gate, with controlled hardware access.

Every phase gate records case IDs, exact builds/content, machines, actual results and unresolved defects. It is not passed by a high recompilation percentage, compilation success, an attractive screenshot or a mocked service. Full-product delivery is a substantial research project for 2–3 developers; no defensible finish date exists before first playable-scene and mode-completion measurements. Re-estimate remaining work and blocked dependencies at each integration checkpoint.

If the bakeoff shows MW2 adaptation costs more than a shared runtime, choose the shared runtime. If a native rendering seam yields no net quality/performance/maintenance benefit, keep the compatibility backend. If vendor/Steam rights cannot be obtained, state the gap and seek an owner decision on product scope instead of mislabeling a substitute as the requested feature.

## Deferred community interoperability consideration

The owner identified possible long-term interoperability with existing MW3 multiplayer communities, particularly **Plutonium IW5** and **XLink Kai**, with **Open-IW5** as a potential technical reference. This is future product context, not a change to current priorities or an added release requirement.

Compatibility, feasibility and permitted reuse have not been investigated or promised. Revisit the idea only after the underlying original multiplayer functionality and secure networking are sufficiently stable. Do not spend current development or research resources on these projects, and do not alter present architecture or task dependencies to accommodate speculative interoperability.
