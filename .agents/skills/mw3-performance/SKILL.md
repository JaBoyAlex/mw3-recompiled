---
name: mw3-performance
description: Evaluate mw3-recompiled architecture or optimization using comparable correctness, stability and performance evidence.
---

Read docs/research/scorecard.md and docs/performance-budgets.md. Correctness and licensing are required gates. Score eligible choices using performance 30%, stability 25%, maintainability 20%, integration effort 15%, hardware compatibility 10%. Leave missing measurements unknown.

Compare identical content, scenario, hardware/driver, quality, cache state and instrumentation. Use at least three independent runs with documented warmup. Preserve CPU/GPU frame-time distributions, memory/VRAM, loading/compile stalls and view-count scaling. Do not equate CPU timing with end-to-end input latency.

Use `tools/benchmark.py` for exported frame observations; it is not a collector or statistical proof. Label synthetic data explicitly and retain raw traces privately. Validate held-out gameplay/visual cases as well as the training/profile scene.

Recommend keeping, revising or replacing the architecture based on measured benefit and migration/maintenance cost. Avoid simultaneous unrelated changes in an A/B comparison. Record inconclusive noise honestly and never retain a speedup that skipped required work or changed gameplay semantics.
