# Architecture and optimization scorecard

Reviewed 2026-11-18 for MW3-030 against project revision
`7ba15cf4ac896cb28ecf50a26c9484099ff54237`. **Keep ReXGlue for bounded private
development**, as selected by [ADR 0002](../adr/0002-runtime-selection.md).
The evidence below supports that engineering choice; comparative MW3 performance
and game-linked release eligibility remain unknown. MW3 is not playable.
This dated review does not complete another task's acceptance.

## Evidence and source identity

Use four separate evidence classes throughout a comparison:

- **Upstream claim**: what another project's pinned documentation reports.
- **Source inspection**: an implementation or limitation visible at an exact
  revision; presence of code does not establish working MW3 behavior.
- **Local synthetic test**: original game-free inputs run against identified
  tools/runtime libraries, including failing controls and sanitizer scope.
- **Owned-title observation**: execution or inspection of the owner's hash-bound
  MW3 executables. Bounded startup is distinct from gameplay and from timing a
  representative workload.

The [upstream lock](../../config/upstreams.lock.json) supplies complete source
and recorded license hashes. All nine local research checkouts matched their
locked HEAD and recorded license hashes with clean tracked/untracked status
during this review. No upstream pin, source, SDK package or active lane output
was changed. The links below are immutable primary sources, not current-release
promises.

| Candidate and locked revision | Upstream claim / inspected boundary | MW3 evidence and disposition |
| --- | --- | --- |
| [MW2 runtime](https://github.com/PaulCombal/mw2-recompiled/blob/b3aa7d8ef184de8ec1f0d2fe7fa0e19a4c92b68b/README.md), `b3aa7d8e` | README reports native MW2 Campaign/MP, local split-screen and networking. These are upstream MW2 claims. | Actual common service tests fail MW3 layout/termination requirements; title generation fails preflight. Stop runtime adaptation, retain analysis tools. Its reported split-screen and Steam behavior do not prove MW3 parity, authorized AppID access or SDR. |
| [XenonRecomp / XenonAnalyse](https://github.com/hedge-dev/XenonRecomp/blob/ddd128bcca99fe8bfbb99bea583c972351fa6ace/README.md), `ddd128bc` | CPU translation and boundary/switch analysis, with a separately required runtime. README describes game-dependent switch patterns, incomplete MMIO and exception support, and optional register-local optimizations. | [Toolchain checks](../../config/toolchains/validation-2026-11-17.md) and [executable analysis](../engine/executables.md) are useful independent evidence. Detection of five BINK tables is not main-engine switch coverage. No runtime or speed score follows from compiling output. |
| [XenosRecomp](https://github.com/hedge-dev/XenosRecomp/blob/70a084c2392378818a4da4086e8e3420b4c3ea8d/README.md), `70a084c2` | Shader translation to HLSL, then DXC to DXIL/SPIR-V. README documents Unleashed-specific assumptions and missing dynamic register indexing/integer constants. It supplies no complete graphics runtime. | Synthetic DXIL/SPIR-V compilation is recorded in the toolchain evidence. MW3 shaders, formats, resolves and rendered output remain unvalidated. Keep as shader-tool research, not an interchangeable renderer. |
| [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk/blob/ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d/README.md), `ebac1cf0` | AOT plus shared runtime; upstream warns of early development and changing APIs. [Pinned build source](https://github.com/rexglue/rexglue-sdk/blob/ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d/CMakeLists.txt) identifies SDK 0.11.0. | Selected private base, using exact reviewed derivatives rather than the unchanged baseline. Memory, CPU and thread receipts below establish bounded contracts; real-title lifecycle still has a leak blocker. A service implementation count is not supported-import coverage. |
| [Unleashed Recompiled](https://github.com/hedge-dev/UnleashedRecomp/blob/7949ed5371b091be310771564a8f1c020974a2ca/README.md), `7949ed53` | Upstream reports a Windows/Linux port and enhancements. XenosRecomp's pinned documentation explains its title-specific translation-layer design. | Reference for later engine rendering/resource work. No local Unleashed gameplay benchmark or MW3 renderer comparison was run. Adopting its seams requires MW3 discovery and visual regression evidence. |
| [CoD3Recomp](https://github.com/FrankHUN88453/CoD3Recomp/blob/3c3178a85075cfa6e0703de5e553ff472acc7916/README.md), `3c3178a8` | README reports playable CoD3 levels. Its [renderer account](https://github.com/FrankHUN88453/CoD3Recomp/blob/3c3178a85075cfa6e0703de5e553ff472acc7916/docs/renderer.md) describes a native D3D11 translation layer and title-specific optimization observations. | Upstream claims/source documentation only; no CoD3 execution or independent timing here. Different title/engine seams, unverified reuse terms and no MW3 equivalence prevent adoption by analogy. The lock records no root license hash; that is not permission to copy. |
| [REA](https://github.com/morluto/rea/blob/e9c72dbd1fa6b318cb3e455c92df064eed62333a/README.md), `e9c72dbd` | Reverse-engineering orchestration/providers, not an AOT runtime. | Provider capability and reproducibility evaluation belongs to MW3-035. No provider execution, native XEX/VMX128 support or speed advantage is certified here. |

The locked Streamline and coop-anything checkouts are peripheral research inputs,
not competing CPU/runtime candidates. Proprietary feature integration remains
subject to its own service, temporal-input and license gates. No community
interoperability or launcher research is added by this review.

## Gates and observed results

Correctness and license/distribution feasibility are gates. A candidate that
fails a required behavior cannot win through a weighted score. Unknown release
rights permit only the bounded research already allowed by the
[license assessment](../legal/runtime-and-distribution-assessment.md).
Root MIT/BSD labels do not resolve transitive GPL/LGPL, file provenance,
generated-game rights or proprietary SDK terms. **No game-linked release is
cleared for any candidate.**

This ledger summarizes existing reproducible evidence, not new executions of
the title or SDK suites by MW3-030. Follow each report for exact input, binary,
compiler/configuration, receipt and private trace hashes. Counts across different
profiles are not independent title workloads and must not be combined into a
compatibility percentage.

| Evidence class / report | Recorded observation | Decision boundary |
| --- | --- | --- |
| Local synthetic: [runtime comparison](../../experiments/runtime-bakeoff/conformance-2026-11-17.md) | Same Linux common contracts: MW2 12 PASS / 9 FAIL; repaired ReXGlue 51 PASS. Instrumented ReXGlue core 21 PASS / 3 explicit collision-fixture SKIP. Original fixed-mapping overwrite and aggregate suite failures remain recorded. | Reject MW2's tested layout/termination behavior. A passing repaired subset does not certify the whole SDK or measure game speed. |
| Owned-title preflight: [runtime decision](../adr/0002-runtime-selection.md) | MW2 translator reports 377 SP / 436 MP boundary errors despite exit zero; fixed heap conflicts with MW3 function tables. MW2 title instructions were not executed. | Fail before execution. The two-runtime gameplay A/B never occurred. |
| Local synthetic: [memory repair](../../config/toolchains/rexglue-memory/validation-2026-11-18.md) | 300 cases pass across five repaired native/sanitizer profiles. Original decommit failures are retained. | Validates the repaired tested memory contracts, not a faster allocation policy. Baseline and derivative receipts are distinct. |
| Local synthetic: [selected-translator CPU oracle](../engine/ppc-validation.md) | 2,410 original cases per run across six Windows/Linux profiles/seeds; six incorrect-result mutations rejected. | Selected ISA/exact-mode coverage only. VMX128, PPC reservations/memory ordering, nonlocal exits and all nine math algorithms are not established. |
| Local synthetic: [threads](../engine/threads.md) and [stop repair](../../config/toolchains/rexglue-stop/validation.md) | Five final profiles exercise 19 isolated cases, three combined orders and two failure detectors each. Requested-stop exit 77 is preserved after repair. | Native callbacks and actual SDK boundaries; not translated PPC atomics or console equivalence. TSan and full fiber/APC behavior remain unverified. |
| Owned-title execution: [header service](../engine/startup-imports.md) and [Windows bring-up](../engine/windows-bringup.md) | Private native Windows/Linux SP/MP startup passes the audited header query and stops at guarded NtAllocateVirtualMemory. | One audited service and its used module-handle chain; remaining imports/data semantics are not admitted by analogy. No playable boot. |
| Owned-title lifecycle: [integration report](../gates/native-kernel.md), snapshot at review revision | Linux SP native passes seven bounded teardown cases. Host ASan/UBSan rejects six launched cases: LeakSanitizer reports 41,991,680 bytes in 1,280 XMA allocations; pre-launch binding rejection passes. | MW3-044 owns the separate repair; MW3-041/010 remain open. Ordinary teardown markers cannot override sanitizer failure. Do not suppress the leak to pass. |

## Weighted comparison when eligible

After gates, use 0-5 evidence-backed scores and
`sum(weight * score / 5)` out of 100. Unknown is **U**, never zero, an assumed
midpoint, or a reason to renormalize the remaining weights. Record the exact
baseline, target and scoring thresholds before comparing candidates; do not
invent thresholds after seeing which candidate wins.

| Dimension | Weight | Evidence required for a score |
| --- | --- | --- |
| Performance | 30% | Matched MW3 CPU/GPU frame distributions, peak memory/VRAM, loading/compile stalls and input latency against declared budgets. Build duration and synthetic callback latency cannot substitute. |
| Stability | 25% | Same repeated modes/load/unload, failure recovery and negative cases, with supported sanitizers and every failure/skip retained. Isolated test passes cannot erase aggregate failures. |
| Maintainability | 20% | Audited patch/interface surface, reproducible provenance, upgrade replay and measured recurring repair effort. Stars, language choice and translated function counts are insufficient. |
| Integration effort | 15% | Recorded setup/adapter effort and remaining scoped seams on both target hosts, including migration, regeneration and regression costs. A working other-title port is not an MW3 estimate. |
| Hardware compatibility | 10% | Observed behavior on declared CPU/GPU/OS/driver tiers and view counts, with feature fallbacks. Upstream advertised minimums do not establish MW3 support. |

Current performance, stability, maintainability, integration-effort and hardware
scores for ReXGlue are **U / U / U / U / U**; there is no numeric total. The
bounded evidence favors continuing its integration, but does not yet provide
agreed full-workload score thresholds or comparable measurements. MW2 is
ineligible on tested correctness. Renderer alternatives and standalone tools
have no comparable full-runtime scores. No fastest-framework claim follows.

## Measurement and reconsideration contract

Use identical executable/content hashes, scenario, hardware/driver, quality,
compiler flags, instrumentation and cache state. Record SP/MP separately and
preserve original simulation and native console split-screen. Four-player
Survival is an extension with separate feasibility/regression budgets.
Collect at least three independent runs with a documented warmup and equal
sample windows; identify cold and warm caches separately. Capture CPU main/job/
render submission and GPU times, p50/p95/p99 frames, worst stalls, peak memory/
VRAM, loading, compilation and actual input-latency measurements. Frametime is
not input-to-photon latency.

Use the [schema-2 measurement contract](../../qa/benchmarks/schema-v2.md),
[comparator](../../tools/benchmark.py) and
[provisional budgets](../performance-budgets.md). The comparator validates
provenance and private trace hashes, weights runs equally, and treats excessive
run-to-run noise as inconclusive; it is not a collector or statistical proof.
The >5% p95 regression trigger requires explanation or rejection at equal
quality. The committed synthetic example supplies no MW3 timing. Retain held-out
Campaign, Survival and MP scenarios as well as 1/2/4-view results when available.

| Reconsideration trigger | Required decision and migration accounting |
| --- | --- |
| Now: bounded startup, memory/stop repairs, lifecycle leak | Continue private ReXGlue integration; finish independently scoped lifecycle correctness before widening service admission. This avoids replacing a coherent memory/PPC/thread model without evidence that another passes. No shared SDK repair is authorized by this scorecard. |
| First playable boot / first faithful frame | Recheck imports, teardown, visual parity and initial CPU/GPU profiles. Compare compatibility rendering with a discovered engine seam only on the same slice. If correctness or measured overhead blocks the baseline, time-box one alternative and record the unresolved measurement if inconclusive. |
| First complete mode | Repeat held-out loads, split-screen, saves and long-session stability; set measured hardware/memory budgets. A single startup or scene result cannot retain an otherwise failing architecture. |
| Each major optimization | Change one policy at a time against a conservative baseline. Test register locals, LTO/PGO, scheduler or cache changes with held-out correctness and noise-aware timing; reject a speedup that skips required work. |
| Relevant upstream/security update or material hardware/driver change | Inspect exact changed sources/licenses and affected dependencies before adopting a new pin; rebuild isolated packages, regenerate hash-bound outputs and replay affected negative/sanitizer/platform cases. An upstream patch claim is insufficient. |

A runtime pivot must budget replacement of memory aliases/layout, PPC context,
thread/TLS/import boundaries, regeneration of both SP/MP modules, SDK/thunk
rebuilds, sanitizer/platform replay and renewed provenance/license review.
Keep the previous reproducible baseline until the replacement passes; retire
the losing production path afterward rather than maintaining two schedulers.
These costs are presently unmeasured, so no person-day estimate is supplied.
The observed MW2 preflight/termination failures make resuming its adaptation
unjustified now. A renderer pivot separately requires shader/format/resolve,
resource-lifetime and per-viewport regression evidence; another title's
renderer timings cannot pay that migration cost.

At each trigger, append a dated decision with exact identities, evidence links,
remaining U cells, pass/fail gates, measured benefit/noise, migration effort and
the next required observation. This completed review establishes the procedure;
future boot/mode/security reviews remain work to perform when triggered.
