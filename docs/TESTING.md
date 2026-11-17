# Testing, evidence and release criteria

Tests are organized by evidence strength:

1. Game-free synthetic unit/property tests: parser bounds/endian fields, dependency DAG, claim conflicts, inventory preservation, benchmark validation.
2. Runtime contract/differential tests: PPC instruction behavior, memory aliases, synchronization, graphics formats/operations and packet parsers, using original synthetic fixtures.
3. Owned-title integration: actual boot/load/shutdown, missions, saves, audio, profiles and independent local inputs through engine-level scenario adapters.
4. Multi-process/multi-machine: actual authoritative state and gameplay, latency/loss/host failure, supported split-screen/network combinations.
5. Release qualification: clean install/rollback/uninstall, cross-vendor GPU matrix, extended soak, packaging rights and independent reproducibility review.

Only level 1 has been run initially, plus metadata inspection of the supplied ISO/executables. An upstream README is not local test evidence. Neither a successful hash nor a rendered menu proves gameplay compatibility.

## Required observations

Reports identify task/case, source/build/compiler, content hashes, OS, GPU/driver, configuration, deterministic seed, timeout, assertion results, process exit and artifact hashes. Use PASS, FAIL, SKIP or NOT RUN; missing prerequisites cannot count as PASS. A timeout, unexpected player count, solo fallback or crash on exit fails. Keep raw traces/dumps/screenshots private by default; publish only sanitized, rights-reviewed summaries.

Build game bots/adapters that invoke real gameplay paths and assert state. Automation supplements human review of visual/audio quality and input feel; neither replaces the other. Mutation/negative cases should prove a real behavior can fail. Screenshots are the game's render output, not captures of the owner's unrelated desktop. Test profiles/install copies are isolated and never overwrite original saves. CI for fork PRs has no private content/SDK credentials and must not use a trusted runner automatically.

## Original mode coverage

Freeze primary manual plus actual selected-build capabilities in MW3-004. Candidate expectations (pending full reference verification): Campaign is single-player; Special Ops/Survival provide two-player co-op; local MP supports up to four. Verify online local-player limits separately rather than inferring them from local MP. Enumerate missions/maps/difficulties, death/retry, checkpoint/load, progression, cinematics, round/map transitions, controller disconnect/reconnect, keyboard/mouse and local profile ownership. Enumerate licensed DLC separately from the disc baseline.

Four-player Survival has an additional suite: four distinct local controllers and viewports; four remote players; feasible mixed configurations; concurrent revive/down/spawn/death; synchronized waves, AI targeting, purchase/reward attribution and fail/retry; disconnect/rejoin and all-view performance. Default console limits remain a tested fallback until the extension is accepted.

## Network and security gate

Test malformed/oversized/truncated/reordered packets, stale sessions and unsolicited peers before exposing guest parsers. Validate authenticated identity, invite expiration, lobby membership, build/content compatibility and guest slot binding. Two households behind CGNAT/restrictive NAT must complete actual sessions over a confirmed relay route with no inbound forwarding and direct paths unavailable. Record loss/jitter, route and failure behavior without publishing tokens or IPs. Encryption does not fix unsafe legacy parsers. Host migration, reconnect and mixed local players require explicit case results, not implied support.

## Performance

See [budgets](performance-budgets.md) and [scorecard](research/scorecard.md). Preserve raw repeated runs and distinguish CPU/GPU/present/latency metrics. `tools/benchmark.py` validates exported runs and compares p95 changes; it does not capture engine timings or prove latency. Synthetic examples exercise the comparator only. Accept no optimization with unexplained correctness regressions; record CPU time, GPU time, p50/p95/p99, memory/VRAM, cold/warm load, pipeline stalls and split-screen scaling.

Release requires the full required-case matrix with no unresolved P0/P1 crashes/corruption/security defects, multi-hour all-mode soak, approved package contents, recoverable installation/update, non-developer-machine setup and explicit supported hardware/content. Optional features must fail gracefully. Phase gates carry the actual numeric thresholds and evidence when runtime measurements exist.
