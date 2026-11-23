# Dependency-driven roadmap

The task DAG in `tasks/` is authoritative. `python tools/project.py list --ready` shows locally unblocked work. GitHub ownership still applies. Phase numbers describe feature maturity, not a ban on independent research, tooling, licensing or test design in parallel. Epics must be split into small tasks before implementation claims.

| Phase | Exit evidence | Main tasks |
| --- | --- | --- |
| 1. Foundations | Verified file identity, contributor flow, reproducible toolchain and reference/measurement contracts | 001–006, 019, 030–032, 035 |
| 2. Native execution | Chosen runtime, reproducible title generation, memory/thread/device services, real menu/scene, stable repeated shutdown | 007–014, 036–041 |
| 3. Original gameplay | All required missions/modes/maps, native split-screen, saves/controllers and local system link | 015–018 |
| 4. Secure Steam networking | Audited legacy parsing, authenticated private invites, verified relay through two-household CGNAT | 020–022 |
| 5. Graphics and latency | Profiled renderer improvements, correct temporal inputs, optional DLSS/DLAA and Reflex with fallback | 023–026 |
| 6. Finish and release | All-mode regressions, performance budgets, installer recovery, provenance and permitted distribution | 027–029 |

The owner requested four-player Survival as an additional feature. MW3-033 audits feasibility after the original two-player mode is stable; MW3-034 implements and verifies local and online four-player behavior after session transport is stable. Release acceptance includes this extension unless the owner explicitly accepts a documented limitation. It cannot replace the original parity gate.

Start three independent lanes after the foundation: toolchain (006), reference cases (004) and research/performance contracts (005/030/032). Lead handles baseline identity, legal blockers and interfaces. After analysis, CPU/kernel work precedes GPU and platform branches; the latter can proceed in separate scopes. Campaign, Spec Ops and MP verification can run independently after the harness/native gate, with controlled hardware access.

Every phase gate records case IDs, exact builds/content, machines, actual results and unresolved defects. It is not passed by a high recompilation percentage, compilation success, an attractive screenshot or a mocked service. Full-product delivery is a substantial research project for 2–3 developers; no defensible finish date exists before first playable-scene and mode-completion measurements. Re-estimate remaining work and blocked dependencies at each integration checkpoint.

After 009, kernel milestone 010 is split into scoped tasks 036–041. Header-service bring-up, memory tests, a selected-translator CPU oracle and thread tests can proceed independently; native Windows execution and controlled title teardown then converge. See [the lane plan](engine/BRINGUP-PLAN.md). The parent requires real-title/platform evidence and keeps first-frame work blocked until those dependencies pass. Additional discovered service repairs get their own tasks; the split is not completion of the kernel gate.

If the bakeoff shows MW2 adaptation costs more than a shared runtime, choose the shared runtime. If a native rendering seam yields no net quality/performance/maintenance benefit, keep the compatibility backend. If vendor/Steam rights cannot be obtained, state the gap and seek an owner decision on product scope instead of mislabeling a substitute as the requested feature.

## Immediate boot-first integration

Owner direction, 2026-11-23: prioritize a visible Windows Campaign boot and one controllable scene. The first allocation checkpoint092 is complete; child093 advances the existing SDK through the initial reserve/commit segment. Extend bounded startup toward content and the existing compatibility renderer, fixing actual incompatibilities. Preserve SP/MP and original split-screen requirements while using focused Campaign probes for development. Full supported checks remain acceptance requirements.

A short exploratory work budget is not a promised playable date. Report the last actual title boundary/frame and concrete remaining blockers. The earlier conversational month range was unsupported and is not a project schedule. Review [candidate acceleration tools](research/boot-acceleration.md) at a concrete integration need; no framework pivot or performance claim follows from documentation alone.

## Deferred community interoperability consideration

The owner identified possible long-term interoperability with existing MW3 multiplayer communities, particularly **Plutonium IW5** and **XLink Kai**, with **Open-IW5** as a potential technical reference. This is future product context, not a change to current priorities or an added release requirement.

Compatibility, feasibility and permitted reuse have not been investigated or promised. Revisit the idea only after the underlying original multiplayer functionality and secure networking are sufficiently stable. Do not spend current development or research resources on these projects, and do not alter present architecture or task dependencies to accommodate speculative interoperability.

## Planned RecompLauncher distribution

**RecompLauncher is a planned distribution channel. Easy installation compatible with RecompLauncher is an explicit release-packaging goal.** This records the owner's intended delivery experience; launcher support has not been implemented or verified.

The owner reports an earlier RecompLauncher release of **Mojo! Recomp**. Use that project's established release workflow as the first reference when packaging work begins, checking which parts remain applicable before creating new tooling. Its workflow has not been investigated during the current MW3 analysis work.

Keep this compatibility goal in mind for future packaging decisions. Defer launcher-specific research, manifests, integration and testing to installer/release preparation; current priorities, task dependencies and engine milestones remain unchanged. Installation must retain verification of legally obtained game inputs and respect upstream licenses and SDK redistribution limits. Do not package game content merely because a launcher can distribute a project.
