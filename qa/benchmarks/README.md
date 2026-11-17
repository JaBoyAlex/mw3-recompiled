# Benchmark evidence

`synthetic.json` tests the comparator, not MW3 performance. Run `python tools/benchmark.py qa/benchmarks/synthetic.json qa/benchmarks/synthetic.json`. Real exports use the same schema but require actual content/hardware/build/settings identity and `synthetic: false`. Record instrumentation, scenario window and warmup in the accompanying case report. Keep raw private traces separately with hashes.

The comparator measures per-run p50/p95/p99 frame samples, the median across runs and a simple noise check. It neither captures game frames nor measures input latency. Memory, VRAM, load and latency metrics require separate real instrumentation in future runtime tasks.
