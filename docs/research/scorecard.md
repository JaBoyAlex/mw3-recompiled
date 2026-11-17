# Architecture and optimization scorecard

Correctness and license/distribution feasibility are gates. A candidate that fails a required behavior or cannot be used under the intended terms cannot win by scoring well elsewhere. Unknown gates permit research only, not release selection.

After gates, use 0–5 evidence-backed scores: **performance 30%, stability 25%, maintainability 20%, integration effort 15%, hardware compatibility 10%**. Compute `sum(weight * score / 5)` out of 100. Mark unknown cells as unknown and do not compute a misleading total. Time-box a comparison if it cannot resolve the decision; record which missing measurement blocks it.

| Candidate | Evidence inspected | Expected advantage to test | Material uncertainty | Actual MW3 timing |
| --- | --- | --- | --- | --- |
| MW2 runtime + patched XenonRecomp | Related-title runtime/build/hooks/security source | Related-engine compatibility and existing split-screen path | MW3-specific mapping/device/ABI differences; GPL combinations | Not measured |
| ReXGlue AOT + shared runtime | Runtime memory/provider docs, source and PPC tests | Shared maintenance, existing device services and test infrastructure | Actual MW3 import/render coverage, overhead and changing APIs | Not measured |
| Unleashed-style engine-level renderer | Renderer/cache layout and released-port documentation | Efficient resources, prewarm and less hardware translation | Cost of discovering MW3 seams and preserving format/resolve behavior | Not measured |
| Existing compatibility renderer | Related-title Vulkan implementation/shared runtime options | Faster accurate bringup and a trusted fallback | CPU/GPU overhead and shader/format gaps for MW3 | Not measured |
| Native PC modification | Research alternative only | Existing host CPU execution | Console split-screen parity and exact binary constraints | Not measured |

## Measurements required for the runtime bakeoff

Use identical input/content hashes, machine, OS/driver, compiler configuration, scenario and reference assertions. Capture build/tool setup effort and changed LOC as maintenance observations, not performance proxies. Compare title entry/import progress, unknown targets, memory alias/atomic behavior, thread teardown, first frame and held-out workload. Do not make one candidate seem faster by skipping guest work, removing audio or lowering quality.

Once playable, capture CPU simulation/render submission and GPU times independently, p50/p95/p99 frames, worst-stall causes, memory/VRAM peaks, cold/warm load/compile behavior and 1/2/4-view scaling. At least three runs after a documented warmup; cold-run measurements start with an explicitly identified cache state. Match scene and timing length. Preserve raw traces privately and sanitized metadata publicly. Input latency requires appropriate event/measurement evidence; frametime alone is not input-to-photon latency.

The comparator in `tools/benchmark.py` rejects mismatched provenance, computes per-run percentiles then their medians, and marks >5% spread among run medians inconclusive. It is a lightweight regression indicator, not a statistical significance test. The initial JSON example is **synthetic** and says nothing about game speed. Do not optimize for one representative scene alone: verify held-out campaign, Survival and multiplayer loads before retaining LTO/PGO/scheduler/shader changes.

Revisit at first boot, first full mode, any large optimization, hardware/driver change and upstream security update. Each decision records baseline, change, raw evidence location/hash, quality assertions, outcome and migration cost. Drop a previously selected path if another gives a superior finished product at justified cost.
