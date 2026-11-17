# Benchmark evidence

`synthetic.json` is the retained **schema-1 synthetic-only** demonstration. It is not accepted as real evidence. New exports use [schema 2](schema-v2.md); [synthetic-v2.json](synthetic-v2.json) is an original labelled example with no MW3 measurements or actual raw traces.

```sh
python tools/benchmark.py qa/benchmarks/synthetic-v2.json qa/benchmarks/synthetic-v2.json
python tools/benchmark.py '<private before.json>' '<private after.json>' --trace-root '<private capture root>'
```

The tool validates exported frame/CPU/GPU times, memory/commit/VRAM, loading and input latency as **distinct metrics**. It does not capture any of them or verify that samples were correctly derived from the raw trace. Real schema-2 exports require accessible private raw files with matching SHA-256 values. Keep those files and exports under ignored private storage; upload only explicitly reviewed, sanitized summaries.

Comparison gives each independent run equal weight. Timing uses the median of run p95 values; memory uses the worst observed peak. A >5% run spread makes the decision inconclusive. These are regression indicators, not statistical confidence estimates, gameplay proofs or latency guarantees. Three runs with one loading/latency observation each do not establish population tail behavior.

Exit codes: **0** within the requested budget; **1** regression or inconclusive noise; **2** invalid/incomparable/unverifiable input. A zero result does not pass a real-game gate. A separate runtime collector and reference assertions remain required.
