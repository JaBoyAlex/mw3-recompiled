# Provisional performance targets

These are design goals, **not achieved performance claims**. Target hardware tiers must be selected after the first playable MW3 slice; no minimum/recommended GPU is advertised yet. The native host metadata tool is not a useful game benchmark.

Preserve original simulation behavior independently of rendering speed. Initial baseline rendering target is stable 60 fps at an agreed resolution/quality on declared target hardware. Higher-refresh rendering is desirable only after frame-rate-dependent gameplay/physics/scripts/audio are verified. Four-view play gets its own budgets and quality settings, not an assumption that a one-view result scales.

Measure 1-, 2- and 4-view frame p50/p95/p99, CPU main/render/job time, GPU time, worst stutter and compilation stalls, working set/commit, VRAM, cold/warm map load, audio underruns and input latency. Record settings, sample windows, device/driver, build/compiler, content and scenario. Use at least three independent runs; document warmup separately. Test both GPU- and CPU-bound situations.

Provisional regression trigger: >5% p95 frame-time increase at identical quality/provenance needs explanation or rejection. High run-to-run variance means inconclusive, not a pass. No accepted change may introduce broken visuals, altered simulation, profile corruption, unstable frame pacing or disabled audio to meet a speed target. Absolute memory/loading/latency limits will be set from measured usage and the selected hardware tiers; missing measurements are tracked work.

The team must revise these budgets at first playable slice and each major mode gate. Benchmarks should exercise demanding gameplay and held-out scenarios, including late-wave four-player Survival once implemented. Optimize against the product workload and maintain a conservative correctness baseline for A/B comparisons.
