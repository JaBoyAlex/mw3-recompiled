# Runtime selection: ReXGlue for private MW3 development

Status: **selected for continued private development**, 2026-11-17. This is
neither release clearance nor a gameplay/performance certification.

Use pinned ReXGlue v0.11.0 with the reviewed Linux reservation repair. Stop
adapting the MW2 runtime; retain its analysis tools, source references and
failed comparison evidence. Maintain one runtime model rather than combining
its memory layout, PPC context or scheduler with the MW2 implementation.
[Reproduction](../../experiments/runtime-bakeoff/README.md) and
[evidence](../../experiments/runtime-bakeoff/conformance-2026-11-17.md) record
the exact revisions, failures, tests and remaining limits.

ReXGlue generates both owned executables without forced validation. Private
Linux/WSL native programs execute translated startup to the first guarded
function import, reproduced in three processes per title. The same stop was
rechecked with the memory repair. All function imports remain diagnostic
stops; all 13 data imports per image still require semantic review. Windows
title execution, normal game shutdown and all original modes remain unverified.

The MW2 candidate fails preflight correctness: its translator emits 377 SP /
436 MP switch-boundary errors despite exit zero; its fixed heap overlaps both
MW3 function-table ranges. The common synthetic harness actually allocates
inside those ranges and demonstrates that its ExTerminateThread returns to
the callback. These failures are retained, not scored as successful work.
Repairing a second runtime before choosing a base would add unnecessary scope.
Its analyzer remains useful for switch discovery; range checks alone do not
establish recovered engine control flow.

ReXGlue also failed an important test: its original Linux fixed-address mapping
overwrites an occupied host page and conflicts with sanitizer shadow mappings.
The reviewed BSD-3-Clause derivative first reserves the complete address span
without replacement, retries occupied candidates and releases failed partial
mappings. The shared tests cover both executable layouts, alias coherence,
endianness, thread context/return/resume/termination, occupied host memory,
all eight partial-mapping failure positions and repeated synthetic load/unload.
These native callbacks are not a differential oracle for translated PPC.
The canonical PPC oracle and upstream SDK CPU tests remain separate evidence.

## Deliberate change to the experiment

The original task required executing the same MW3 slice on both candidates.
That did **not** happen: no MW2 title instructions were executed. As lead, we
replace that validation step with fail-fast preflight rejection plus common
runtime-service tests on the same machine. This change follows observed
correctness failures and the owner's instruction to avoid inefficient work.
It does not establish comparative title speed or excuse these failures. The
first-service/data-import audit moves to scoped runtime bring-up after
reproducible generation (009); it is not claimed complete by this selection.

## Costs, limits and reconsideration

The shared runtime has less demonstrated title-specific repair, reusable
platform services and a coherent memory/thread model. It requires C++23 and
Clang 20; maintained game-free project code remains C++20. Its upstream aggregate
tests expose shared-state/order failures even though the 261 selected tests
pass when isolated. These remain defects to investigate, not erased failures.
One focused Linux memory patch and isolated build-output setting are maintained
with exact base/patch identities. No renderer fork or generic emulator is added.

Both candidates are permitted for bounded private research under the existing
[assessment](../legal/runtime-and-distribution-assessment.md); SDK/game-linked
distribution remains on hold. The new runtime patch preserves BSD notices;
project harness/tools retain GPL-3.0-only. This choice grants no rights to game
content, vendor SDKs or production services.

No weighted performance winner is declared. Correctness/licensing are gates;
performance 30%, stability 25%, maintainability 20%, integration effort 15%,
hardware compatibility 10% remain the eventual criteria. Comparable MW3 frame
times, memory peaks, GPU results, loading and latency are unknown. Preparation
durations and synthetic callback timings are not gameplay benchmarks. Reassess
at first playable boot, first complete mode, major optimization and relevant
upstream security changes. Dependent product gates remain open.
