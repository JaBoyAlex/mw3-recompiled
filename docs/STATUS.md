# Status — 2026-11-23

**Not playable. No rendered MW3 frame, menu or playable mode is verified.**
The immediate priority is a visible Windows Campaign boot and then one
controllable scene, using existing runtime implementations and compatible
MW2 components. This is static recompilation, not full source reconstruction.
See [boot-first integration and tools](research/boot-acceleration.md).

## Current verified boundary

MW3-046 allocation-import contracts are accepted with the MW3-091 selected-SDK
repair. MW3-092 is merged in [PR140](https://github.com/JaBoyAlex/mw3-recompiled/pull/140)
at `2d1ac5764b4bea20ea8e1d0d00b2265c38a9151a`. Both exact owned SP/MP modules
execute the audited header query and one original kernel allocation, checking
a 1 MiB reserve-only region, then stop before translated title code resumes.
There is no observed next service, menu, frame or gameplay from that checkpoint.

The [allocation report](engine/title-allocation.md) records 246 isolated process
cases across 28 independently audited runs: 120 allocation, 70 read-only
inspection and 56 original-header regressions, with 246 unique nonces and
60 actual calls including intentional post-call controls. Native Windows/Linux,
supported host sanitizers and Linux participating-kernel sanitizers pass.
Windows kernel sanitizers are unsupported; Linux/WSL shares the Windows machine.
Generated guest code and retained native dependencies are outside parts of
instrumentation. Self-review only; no independent reviewer is claimed.

Public local Windows Release and Linux Release ASan/UBSan checks each pass
327 Python tests plus parser CTest 1/1, with 8/2 explicit platform skips. The
final [exact-head CI run](https://github.com/JaBoyAlex/mw3-recompiled/actions/runs/45127118417)
passes all five Windows/Linux Debug/Release and sanitizer jobs at reviewed head
`0cdbdbaf2571cf25f28e31596167e8f8299c4ea5`. Retained failures and limitations
remain in the subsystem report; a passing probe is not gameplay evidence.

The source baseline remains MW3 **2011**, Xbox 360 USA/Korea Rev 1, bound to the
[owned executable manifest](../config/titles/mw3-xbox360-rev1.json). Informal
"1.1", disc revision, XEX version and title update remain distinct identities.
PC files are optional. Owner console content is privately prepared by 045:
218 files, 8,112,921,882 bytes, unchanged ISO and verified executable identities;
see [content preparation](engine/content-preparation.md). The old minimal owned
directory still contains only the two XEX files. Full preparation does not
prove the title has loaded those assets through its runtime.

MW3-011 remains an unfinished first-frame epic. New child 093 scopes the first
post-allocation reserve/commit startup segment and next diagnostic stop, using
existing SDK services. It must be separately published and claimed before
implementation. Subsequent content/device/rendering integration remains
unverified and must be split into bounded tasks. No unsupported calendar
estimate is adopted as a delivery schedule.

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
