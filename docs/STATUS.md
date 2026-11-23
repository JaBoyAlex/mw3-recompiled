# Status — 2026-11-23

**Not playable. No rendered MW3 frame, menu or playable mode is verified.**
The immediate priority is a visible Windows Campaign boot and then one
controllable scene, using existing runtime implementations and compatible
MW2 components. This is static recompilation, not full source reconstruction.
See [boot-first integration and tools](research/boot-acceleration.md).

## Current verified boundary

[MW3-093 / PR143](https://github.com/JaBoyAlex/mw3-recompiled/pull/143) advances
both exact owned SP/MP modules through the audited header service, initial
1 MiB reservation, following 64 KiB commit and title heap initialization.
Execution stops **before calling `KeGetCurrentProcessType`**, at independently
audited SP/MP callers. There is no rendered frame, menu or playable boot.
The existing MW3-091 selected SDK supplies the real allocation export; no new
SDK repair, imported data variable, renderer or successful stub is added.

The [continuation report](engine/title-startup.md) records 206 isolated process
cases across 22 separately audited runs: 150 continuation, 48 historical
first-allocation, four header-only and four continuation-inspection cases,
with 206 unique nonces and 198 actual allocation calls including deliberate
post-call controls. Native Windows/Linux, supported host sanitizers and Linux
participating-kernel sanitizers pass. Intentional deadline controls establish
their valid baseline and make no recovery claim; all other cases check mapping
release and host-thread counts. Pre-launch binding controls do not launch a
guest thread. Historical regressions here use the selected memory-imports SDK
on native hosts; prior 092 sanitizer/original-XMA evidence is retained separately.

Public local Windows Release and Linux Release ASan/UBSan checks each pass
338 Python tests plus parser CTest 1/1, with 8/2 explicit platform skips.
Three direct stale-hash CLI controls refuse execution before output. Exact-head
public CI and review are recorded on the linked PR and are required for merge.
Windows kernel sanitizers are unsupported; Linux/WSL shares the Windows machine.
Generated guest code and retained dependencies are outside parts of
instrumentation. Self-review only; no independent reviewer is claimed.

The previous [MW3-092 allocation checkpoint](engine/title-allocation.md), merged
in [PR140](https://github.com/JaBoyAlex/mw3-recompiled/pull/140), remains an
explicit regression and stops before returning from the first reserve. Its
separate report retains earlier evidence and failures. Passing either bounded
probe does not establish gameplay or general retail ABI parity.

The source baseline remains MW3 **2011**, Xbox 360 USA/Korea Rev 1, bound to the
[owned executable manifest](../config/titles/mw3-xbox360-rev1.json). Informal
"1.1", disc revision, XEX version and title update remain distinct identities.
PC files are optional. Owner console content is privately prepared by 045:
218 files, 8,112,921,882 bytes, unchanged ISO and verified executable identities;
see [content preparation](engine/content-preparation.md). This startup probe
still uses the minimal two-XEX directory; full preparation does not prove
the title has loaded those assets through its runtime.

MW3-011 remains an unfinished first-frame epic. The next serial integration
task must audit and scope the following bounded service segment before claiming
the shared runtime paths. Reuse existing SDK services toward content/device/
rendering integration, preserving modes and split-screen requirements. No
unsupported calendar estimate is adopted as a delivery schedule.

## Completed foundation and bounded evidence

- C++20 game-free XEX inspector, bounded synthetic parser tests, owned-file
  SHA-256 identity checks, XDVDFS inventory and exclusive executable extraction.
- Dependency-DAG task catalog, searchable ready tasks, copyable prompts,
  idempotent issue publication and serialized path-based claims. GitHub issue
  assignees define ownership; local readiness alone is insufficient.
- Pinned/reproducible CPU and shader host-tool preparation, private title
  generation, ABI helper-ladder and switch analysis, original import/data
  classification and independent header/layout checks. All 326 generated
  C++/header files reproduce; ancillary paths/stamps are not claimed identical.
- [Runtime selection](adr/0002-runtime-selection.md): continue private ReXGlue
  development. The related MW2 runtime is rejected for these title outputs;
  retain its useful analysis tools. No comparative gameplay performance result
  exists. [The scorecard](research/scorecard.md) defines measured reconsideration
  and migration gates.
- [Memory contracts/repair](engine/memory.md): five native/sanitizer profiles
  pass 300 cases; original decommit failures remain retained. Strict mapping,
  alias and release checks do not establish every kernel memory-import ABI.
- [Selected-translator CPU oracle](engine/ppc-validation.md): 2,410 original
  synthetic cases per run across six native/sanitizer/held-out runs, with
  rejected result mutations and matching generation. This is a selected ISA
  subset; VMX128, reservation-instruction and nonlocal/exception gaps remain.
- [Thread acceptance](engine/threads.md): isolated/repeated contracts, actual
  kernel/XAM stop boundaries, TLS/r13, waits, stacks, interlocked interfaces and
  cancellation checks pass with the stop repair. Fibers/APCs, translated
  reservation semantics and general race freedom are not established.
- [Native Windows bring-up](engine/windows-bringup.md) and the
  [audited header service](engine/startup-imports.md) bind both executable
  identities. Twelve other kernel data variables and subsequent function
  services remain unaudited. Unknown imports fail diagnostically.
- [REA evaluation](research/rea-evaluation.md) records tested provider limits;
  its PPC analysis results do not establish XEX/VMX128 or native runtime support.
- [Measurement contracts](../qa/benchmarks/schema-v2.md) validate provenance,
  noise and memory-budget reporting. No MW3 gameplay benchmark exists.

## Product and delivery work still ahead

Original Campaign, Special Ops, Survival, Multiplayer and console split-screen
parity remain unverified. Four-player Survival is an explicitly requested
extension with its own feasibility/regression work. Steam invites, private
lobbies, authorized SDR/CGNAT tests, renderer modernization, DLSS/DLAA, Reflex,
optimization, installer recovery and release acceptance remain future work.
See the [architecture](ARCHITECTURE.md) and [roadmap](ROADMAP.md).

MW3-031 completes the scoped [source/local-build delivery decision](legal/distribution.md).
It does not approve game-linked executable/SDK distribution or a release.
Reference cases 004 and authorized Steam AppID/SDK access 019 remain open.
RecompLauncher-compatible easy installation is planned; integration and the
Mojo! Recomp reference remain deferred. Plutonium/XLink Kai interoperability
and Open-IW5 remain deferred considerations, not current implementation work.

[Contributor setup](FRIENDS-START-HERE.md) uses the live backlog rather than a
fixed list of completed tasks. Select with `python tools/project.py list --ready`,
check GitHub ownership/dependencies, claim through task-admin and use a separate
branch/worktree. Every future report must distinguish source inspection,
synthetic tests, actual title checkpoints and verified gameplay.
