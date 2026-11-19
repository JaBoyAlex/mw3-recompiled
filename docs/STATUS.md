# Status — 2026-11-19

**Not playable. No menu, rendered MW3 frame or playable mode has been verified.**
Private native Windows and Linux/WSL modules execute a bounded portion of owned
Campaign/Multiplayer startup through one audited header service, then stop at
guarded NtAllocateVirtualMemory. This is actual translated title execution,
with deliberately limited service coverage. It is not a game launcher.

The baseline is MW3 **2011**, Xbox 360 USA/Korea Rev 1, bound to the exact
[owned-input manifest](../config/titles/mw3-xbox360-rev1.json). The owner's
informal “1.1” preference is not a verified title update. PC files are optional.

## Current integration checkpoint

MW3-044 is merged in [PR 70](https://github.com/JaBoyAlex/mw3-recompiled/pull/70).
It fixes the demonstrated XMA packet-ownership leak without changing decoding
algorithms or admitting another guest service. Its matrix passes **56 bounded
owned-title processes and 20 focused game-free processes**. The original
42 MB-per-pool leak and six original title-sanitizer failures remain retained.
All 76 processes' reported kernel-library hashes were checked. The repaired
Campaign comparison retains identical game inputs, generation, host source and
compiler, with the exact original SDK as parent. See
[lifecycle evidence and limitations](engine/xma-lifecycle.md).

Public checks for that implementation pass 116 Python tests on Windows with
five explicit LLVM/symlink skips, and 118 on Linux with no skips. Native parser
CTest and Linux ASan/UBSan checks pass. Windows uses native runtime libraries
and supported host UBSan traps; core ASan is unavailable. Generated guest code
is not sanitizer-instrumented. Linux core coverage retains native XAM and
disabled vptr instrumentation. Self-review is recorded; no independent review
is claimed. No game-linked binaries, SDKs or private traces are published.

The discovered lifecycle blocker is resolved. **041 still needs formal child
evidence reconciliation; parent kernel gate 010 remains open.** First-frame
011 remains an epic that must be split before implementation claims. Its next
foundations are complete private content preparation (045) and allocation
import ABI contracts (046). The current owned directory contains only the two
XEX files. No full game-content preparation or later startup is verified.

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
