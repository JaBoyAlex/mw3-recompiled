# Boot-first integration and reusable tools

Owner direction recorded 2026-11-23: prioritize an actual Windows Campaign
first frame/menu and then one controllable scene. This is static recompilation
with an existing host runtime, not a requirement to reconstruct all game source.
Retain original modes and native console split-screen as product requirements.
The earlier conversational 3–9 month estimate for a first playtest had no
measured work breakdown and is not a project schedule. A short exploratory
budget measures actual progress and blockers; it does not promise playability.

## Immediate approach

Continue the verified selected ReXGlue base and use its implemented services
and compatibility renderer. We already have native translated SP/MP modules,
kernel/platform code and full privately prepared owner content. The current
probe deliberately stops after the first allocation; it does not demonstrate
that all later SDK implementations are missing or that they work with MW3.
The next step is integrating and checking those implementations against actual
MW3 behavior, repairing demonstrated mismatches and retaining diagnostic stops.

Use focused bounded Windows Campaign probes while developing. Complete the
required supported SP/MP, negative, sanitizer and platform regressions at each
finished integration milestone. Reuse generated objects and isolated build
caches where identities match. Keep at most two build workers and one GPU-heavy
real-title suite per machine. Prioritize title execution/content/frames over
unrelated enhancements or a new generic runtime. Do not remove correctness,
provenance, resource ownership or unknown-import checks to produce a green boot.

Completed child092 proves the first actual reserve call, not its guest return.
Child093 separately owns the audited initial reserve/commit continuation and
next unadmitted service stop. Later content, device and rendering boundaries
need independently testable scopes before claiming the first-frame epic011.
Report the last executed title boundary, any actual rendered frame and concrete
remaining blockers. Test counts and source inspection are not gameplay progress
percentages. Keep the previous checkpoint available as a regression.

## Candidate accelerators

These are current primary-source observations from 2026-11-23, not new local
integrations or measured MW3 improvements. No upstream pin, SDK, renderer or
license decision changes in this planning update. Keep a single coherent
memory/PPC/thread model. Inspect exact revisions, interfaces and file-level
terms when a scoped consumer needs a candidate; do not copy upstream agent
instructions into this repository.

| Tool/component | Potential use | Current boundary |
| --- | --- | --- |
| [ReXGlue](https://docs.rexglue.com/#runtime) | Existing kernel, memory, XAM, filesystem, input, audio, window and GPU services; use the compatibility backend for a first frame | Already selected at reviewed v0.11-derived identities. Current online documentation may describe newer APIs; it does not validate MW3 or authorize an automatic upgrade. |
| [MW2 reusable host components](mw2-reuse.md) | Related-title input/audio/storage/graphics techniques and analysis tools | Existing reviewed map covers16areas/55files. Prefer a concrete compatible consumer. Tested whole-runtime layout/termination and translation preflight failures remain; no MW2 guest address is an MW3 address. |
| [ReGPU](https://github.com/zer0ducksgiven/ReGPU) and [Glue2GPU](https://github.com/zer0ducksgiven/Glue2GPU) | Reusable Direct3D12 Xenos renderer and an adapter for ReXGlue ports | Upstream documentation describes shader/command/resolve handling and an FH1-based plugin example. It needs matching SDK/compiler interfaces and replacement/removal of title-specific hooks. Our v0.11-derived ABI, MW3 formats/shaders, split-screen and actual frames are untested. Other-title FPS claims are not MW3 results or integration-time estimates. |
| [Re360](https://github.com/furqanagwan/Re360) | Combined ReXGlue-derived CPU/runtime and ReGPU-derived graphics stack | Upstream labels it alpha and lists Windows11, VS2026/Clang and Microsoft GDK requirements. No local build, regression, provenance-combination or MW3 comparison has been run. Migration costs are unknown; it is not selected. |
| [Ghidra](https://github.com/NationalSecurityAgency/ghidra) with [XEXLoaderWV](https://github.com/zeroKilo/XEXLoaderWV), scripts or a verified agent bridge | Automate function/xref/structure matching to help adapt MW2 hooks to exact MW3 builds | A loader's format support is distinct from Xenon/VMX128 correctness and provider admission. Our [tested REA/Ghidra path](rea-evaluation.md) refused both MW3 XEX files; installing a generic MCP bridge does not resolve that by itself. Existing independent loader/decoder analysis remains available. |
| [sccache](https://github.com/mozilla/sccache) | Local compiler caching to reduce repeated generated-C++ builds | Candidate only. Ninja, precompiled headers and persistent isolated object caches already exist. Measure additional cache hits/build time with exact compiler/config/source identity; keep game-derived objects private. |

Project skills already cover scoped task execution, evidence and performance.
A future boot-debug skill can automate trace collection, exact call-site lookup,
minimal changes and bounded repro/regression commands. Such a skill organizes
work; it supplies no kernel or renderer implementation. Independent analysis
lanes need separate claimed paths and agreed interfaces before parallel work.

## Decision boundary

First try to reach actual output with the existing SDK stack. A new renderer or
runtime needs an observed MW3 blocker or a comparable correctness/performance
benefit that justifies integration and maintenance costs. Use the existing
[scorecard](scorecard.md); unknown measurements stay unknown. No framework is
called the fastest, no DLL is assumed compatible because it loads, and no mock,
other-title screenshot or successful stub completes a boot/mode gate.
