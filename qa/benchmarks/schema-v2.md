# Exported measurement contract — schema 2

This is an evidence export/comparison contract, not an instrumentation implementation. No real MW3 measurement exists yet. Start from [the original synthetic example](synthetic-v2.json), retain `synthetic: true` for every simulated/exporter test, and generate real metadata from the actual capture/build/input identities when a runtime collector exists.

| Field | Required meaning |
| --- | --- |
| `schema_version`, `synthetic` | Integer 2 and explicit boolean. Schema 1 is accepted only for legacy synthetic tests. |
| `build` | Object with nonempty `id`, `source_revision`, `flags` and lowercase 64-hex `artifact_sha256`. Different builds/flags may be the intended A/B change; every other comparison condition must agree. |
| `file_sha256` | Nonempty role/name → lowercase SHA-256 mapping for actual executable/content/manifests. Include every identity needed to distinguish region/update/DLC/content; do not use filenames or human revision labels as hashes. |
| `scenario` | Stable case ID including the tested mode/scene/protocol. Reference assertions belong in the associated case record. |
| `hardware` | Object with CPU, GPU, positive integer `ram_bytes` and stable `machine_id`. Fields are `cpu`, `gpu`, `ram_bytes`, `machine_id`; no anonymous "same PC" substitution. |
| `os`, `driver`, `compiler` | Nonempty exact identities/versions. Compiler identity must agree across a comparison; build flags/source/artifact changes are recorded separately. |
| `settings` | Nonempty JSON object containing actual quality, resolution, pacing, timing/instrumentation and workload configuration. Every key/value participates in comparability. |
| `cache` | `state` is `cold` or `warm`; `policy` records how caches were cleared or prewarmed and which caches are covered. Cold results cannot include warmup. |
| `warmup` | Object with nonempty `description` and finite nonnegative `duration_ms`; record excluded warmup explicitly. |
| `view_count` | Integer 1–4; never compare one view with split-screen or share a one-view result as a four-view claim. |
| `metric`, `unit` | One of the distinct metrics below, with the required unit. FPS and throughput are intentionally unsupported rather than interpreted with the wrong regression direction. |
| `measurement`, `capture_tool` | Exact method and version/configuration of the exporter/instrument. CPU duration, GPU timestamps, present intervals and input-to-photon observations are different methods. Naming a metric does not prove it was measured. |
| `sample_window_ms` | Positive finite planned sample window. Match workload/window across runs and before/after. Record actual timing deviations in the case notes and reject unsuitable captures. |
| `runs` | At least three independent run objects, each with a unique `id`, relative `trace_file`, unique lowercase `trace_sha256`, and nonempty `samples`. Frame/CPU/GPU metrics require at least two samples per run; other metrics permit a scalar observation per run. |
| `notes` | Optional explanatory metadata; not an alternative location for configuration that should affect comparability. Unknown top-level fields are rejected to catch schema mistakes. |

Supported metrics and units:

| Metric | Unit / interpretation |
| --- | --- |
| `frame_time` | `ms`; specify whether present-to-present or another precise method |
| `cpu_main_time`, `cpu_render_submit`, `gpu_time` | `ms`; distinct instrumented stage durations |
| `load_time` | `ms`; define load start/end and cold/warm protocol |
| `input_latency` | `ms`; define observed input and output events; frame time is not a substitute |
| `working_set`, `commit`, `vram` | Integer `bytes`, 0 ≤ value < 2^64; define process/device scope and capture sampling |

Timing samples must be finite and positive. Booleans are not numbers. Memory samples can be zero but cannot be fractional/negative. Export files are limited to 64 MiB; keep large original traces outside the export and stream their hashes. Raw trace names use portable relative paths, without parent traversal, drive prefixes, backslashes or NUL. Resolved files must remain inside the explicit private trace root; symlink escapes are rejected.

For real exports (`synthetic: false`), use `load(path, trace_root)` or the CLI's `--trace-root`. Every raw file must exist and hash correctly. JSON cannot assert its own verified state. The returned in-memory evidence is fingerprinted; changing it after loading requires a fresh export/load rather than retaining a stale verified label. The comparator reads/hashes files without modifying or uploading them. Keep capture files immutable after verification.

`raw_trace_integrity_verified` means existence/hash integrity **at load time**. It does not mean the exporter derived samples correctly, the machine/configuration description is truthful, the workload is representative or gameplay passed. Reports deliberately set `sample_derivation_verified: false` and `statistical_confidence: not-estimated`. Real collector/reference work remains in the runtime/testing roadmap.

Timing summaries are the median of per-run p50/p95/p99 values; runs have equal weight regardless of their sample counts. Timing budgets compare p95. Memory budgets compare the **worst sample across all runs** so a peak is not hidden by percentiles. Noise uses run medians for timing and run peaks for memory; spread above 5% of their median yields `inconclusive-noisy`. This heuristic is not a statistical test. Each report retains sample counts and worst values.

All supported metrics use lower-is-better regression direction. Default tolerance is 5%; nonfinite/negative tolerances are rejected. A zero memory baseline followed by any increase is a regression with `change_percent: null`; an unrepresentable relative percentage is also null rather than infinity. Build/context/absolute summaries remain available. Near-threshold changes still require case/reference review and repeated runs, not automatic acceptance from one CLI status.

Before/after must match schema, synthetic flag, scenario, input/content hashes, hardware, OS, drivers, settings, cache/reset policy, metric/unit, views, warmup, capture method/tool, compiler and sample window. Build IDs/artifact/source/flags are allowed to differ as the intended tested variable. Document the actual change in the case report; this does not validate unrelated simultaneous changes. Raw trace files stay private; source-controlled examples contain original synthetic data only.

For the MW3-008 runtime comparison, use a common compiler/version and configuration capable of building both candidates, the exact owned build, the same bounded guest workload and explicit correctness/failure assertions. If a candidate cannot execute the same work, record the failure and do not manufacture an FPS comparison from skipped work. Game-free correctness and build-effort evidence can proceed independently of meaningful MW3 timing.
