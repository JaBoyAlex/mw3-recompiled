# Decommit repair validation — 2026-11-18

The isolated `decommit-v1` profile fixes the four baseline decommit failures.
**All 300 memory-contract processes pass.** Both owned SP/MP executables retain
the reviewed header-query/next-import checkpoint on native Windows and Linux.
This completes MW3-042's bounded repair, not playable boot, full memory/kernel
compatibility, original gameplay or orderly title teardown.

## Implementation and identity

SDK base remains `ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d`. The original BSD
repair is SHA-256
`27792fb66bc8b6bac0ad11557c6325980e7dcdb337d2c5f837bc1d714db84141`;
its terms are in [NOTICE](NOTICE.md). Preparation composes the prior reviewed
reservation/output patch and, on Windows, API typing patch. Exact composition,
source/submodule trees, compiler, flags and package files are in each receipt.
Original SDK sources/packages and baseline failures remain available unchanged.

`QueryProtect` and `QueryRangeAccess` now reject uncommitted pages. Caller audit
covers checked GuestMemory/MemoryView access, address validity/protection queries,
physical-fault diagnostics and file-buffer checks. Decommit validates the entire
range before mutation, covers both ends of partial-page requests and revokes
host access while preserving shared backing storage. Physical parent/alias
operations cover identical complete guest pages. Fault recovery distinguishes
reserved, decommitted physical pages from released pages, preserving the existing
configurable release policy. The kernel shim already short-circuits zero-length
decommit; the low-level API's zero-range refusal does not change that shim path.

Profiles retain LLVM 20.1.2; Windows uses MSVC 14.44.35207 and Windows SDK
10.0.26100.0. Core/adapter integration is C++23; public metadata tooling remains
C++20. As before, SDK target settings may append O3 after configured O2. No
equivalent-optimization or performance comparison is inferred from build times.

## Actual verification

| Check | Result | Limit |
| --- | --- | --- |
| Windows native memory | 60 PASS | Original game-free programs, three layouts |
| Windows host UBSan trap memory | 60 PASS | Calibrated host checks; core uninstrumented |
| Linux native memory | 60 PASS | Original game-free programs, three layouts |
| Linux host ASan/UBSan memory | 60 PASS | Core uninstrumented |
| Linux core + host ASan/UBSan memory | 60 PASS | Base/PPC/kernel instrumented; prepared graphics/dependency components uninstrumented |
| Focused upstream SDK tests, Windows | 30 PASS, 1 SKIP | Actual kernel DLL imports verified |
| Focused upstream SDK tests, Linux | 28 PASS, 1 SKIP | Actual packaged kernel shared-library resolution verified |
| Owned SP/MP startup, Windows | 12 PASS | Three positive + three rejection processes per title |
| Owned SP/MP startup, Linux | 12 PASS | Same bounded checkpoint and rejection coverage |

The original contract cases retain aliases/endian access, seeded allocation,
pointer boundaries, live stack guards, reserve/commit/protect/recommit and
deliberately wrong oracle rejection. Added cases verify partial-page neighbors,
whole-range queries, invalid/wrapping/unreserved ranges, repeated decommit,
physical usage accounting/recommit and real physical-decommit faults. Expected
hardware faults require the correct signal/status; they cannot establish normal
teardown or leak freedom. Native callbacks are not translated-instruction ISA
coverage, which remains task 038.

The one upstream skip on each host explicitly requires host pages larger than
the 4 KiB pages available here. It is SKIP, not a passing assertion. No larger
host-page, GPU, allocation-failure rollback or concurrent lifetime guarantee is
established by this matrix. Windows ASan's allocator/CRT conflict remains;
Windows host checks use calibrated UBSan trap mode. Aggregate SDK lifecycle
failures remain with task 039; process isolation does not fix them.

Linkage review found that the original upstream `unit_tests` executable embeds
kernel objects. Staging new DLLs beside it is insufficient to validate those
objects. Its 255 passing Windows cases are therefore **excluded** from repair
acceptance. The focused target instead compiles the pinned original heap/access
test sources and imports the actual packaged kernel, with ELF/COFF linkage
evidence. It needs no game files or private title metadata:

```powershell
python tools/test_runtime_memory.py --root <private-runtime-cache> `
  --sdk-report <verified-memory-sdk-receipt> --output-root <private-results> --upstream
```

Normal matrix/preparation commands are in [the profile guide](README.md).
Private preparation failures include the stale helper fingerprint during
development and upstream's cached relative install prefix; the latter is fixed
with an absolute unused prefix. Initial staged tests lacked an allocator test
module, and the first focused runner treated Catch2's explicit all-skipped exit
as failure. Those records remain private. Corrected classification requires
matching skip XML and cannot hide a failing assertion or arbitrary nonzero exit.

## Regeneration and title limits

The native repaired package generated both modules twice cleanly. All **326
C++/header files match**, and also match the earlier verified outputs byte for
byte. No generated source was edited. The new identity is
`b20d2d83448ef9b8286c68e039f38ab41c9317153ac7875f9d8e8d99b1a2f3ba`;
its manifest SHA-256 is
`2defa8d49183f6c925afc2d12dc2c9435e7a28c9526bd23525e347315e9db07a`.
Patch/package/preparer identity participates in the cache key. Instrumented
core SDKs are refused for generation. Modified/reset sources, patch receipts,
SDK packages and reference caches fail without silent repair. SDK resolution
outside the verified package is rejected.

Both platforms still admit only RtlImageXexHeaderField, audit the used module
handle/header bytes and stop at **NtAllocateVirtualMemory**. That service remains
unreviewed and guarded. Four additional present-field probes are host-initiated,
not original guest calls. Intentional `_Exit` stops remain distinct from orderly
title shutdown. Original files are reverified and private SDK/generation inputs
remain unchanged. No renderer, audio, split-screen or online result is implied.

Public checks: Windows `python tools/check.py --config Release` passes 92 Python
tests with five explicit LLVM/symlink skips and native CTest. Linux
`python3 tools/check.py --config Release --sanitizers` passes 94 Python tests,
without skips, and ASan/UBSan CTest. Catalog and artifact heuristic checks pass;
the heuristic is not legal clearance. Exact-head CI must pass before merge.

Performance impact is unmeasured: the repair adds commitment checks and host
protection on decommit. There is no FPS, loading, latency or architecture-speed
claim. Game/SDK-linked distribution remains unapproved. Self-review is recorded;
no independent reviewer is claimed.

## Private receipt index

Each row names its attempt's `manifest.json`. Linux SDK attempts are under
`runtime-bakeoff/memory-preparations`, memory cases under `memory-fixed`, focused
tests under `upstream-memory-fixed` and titles under `fixed-title-probes` in the
owner's Linux cache. Corresponding Windows roots are `memory-preparations`,
`memory-fixed`, `upstream-memory-fixed` and `runs` in the private Windows cache.
Receipts retain commands, sources/compiler/binary identities and raw-log hashes;
focused tests also bind each XML result and actual library imports.

| Evidence | Attempt | Manifest SHA-256 |
| --- | --- | --- |
| Linux SDK | `72b8002f19454b8895429ea40357a291` | `a7888b4cf6fab9606e2ae13dd00f48f716c91eb12dcf950b20e32d8689a50a08` |
| Linux core ASan SDK | `94cf1f3e2d8b4c35a7c7caabb26c7241` | `f021fde423e685d95742250505c648aacd18c8d5e658c5ab61ca6315e7029340` |
| Linux native memory | `b57b166d352d46ff99204c0cf027ce88` | `6c06215f367ec4d222e61e0018e7adae9239724003af5c31ce37a28a5f97ee72` |
| Linux host sanitizer memory | `66e019e44c834a21997571f1c5874e79` | `2deee77918bf8458bbba7c19d72caa09e75bb023671cd44e71a07689047d5cc3` |
| Linux core sanitizer memory | `1100fcff87384508914b23162ba77e51` | `86647a18408e36341f601082fa4710b4fe12f3e79feae7f3b33e8268209de0ff` |
| Linux focused SDK | `f8ba3e65cdc24416a6326c4aa14f6259` | `55cb012a8247106804c4543e294ac42ac3e25e12512d97da63655d1eb52889e2` |
| Linux SP title | `b3dceaac051a4021b9bef70714fb08ec` | `919d38e33c2f036451924e91218001e21346375dd03758d64af7f895fc8434e4` |
| Linux MP title | `9620c86c5b184de8895824f2be296969` | `475a08fc1796dd981bc73156822956536c4265126e4760a782e84fd605d5e17e` |
| Windows SDK | `1b889453ae91462d8e0ca6c8adc64faf` | `31b7ed50829b8e95ad4df23b08bd7f31128d1fd643328f60e63beec6dca4d659` |
| Windows native memory | `5974c1ca75194bffb4707b11e97eeb10` | `4061ca9b4613c0fbaa89954f7a7eb9e92c1ecb4cb6d510326e4775b8dc307fb6` |
| Windows host sanitizer memory | `e0db6d5b7d8c421192289cf97def419e` | `2f09912d6f78c03d25f8c53335fa50b1f33232d9b4db306b6b624b77b6ff357a` |
| Windows focused SDK | `fc51f0e9fa68461ab7616bf2100742e4` | `dddc85c57bfc3449df43806bc905d48b23309d0c82659661a169b496b361070d` |
| Windows SP title | `1009eb0a39fc4991bcc12bd0e2f7bea4` | `3d0e405d9a16e6ec8de7a70eb0b526ec96d51cf1e3522ba3ecf4e73ef5918954` |
| Windows MP title | `a92e03c3f82846f8857748ccb32bc173` | `caf92598b5ae6d6f1fb8e93cb9a63ffc21d649301f16e4bb237124ec2948f968` |
