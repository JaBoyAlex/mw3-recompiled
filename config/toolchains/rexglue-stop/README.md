# Explicit stop-boundary SDK derivative

MW3-043 is in progress. The patched SDK is not yet a passing thread gate.
Baseline failures remain in [thread evidence](../../../docs/engine/threads.md).

Start from a verified decommit-v1 receipt. All source/package baselines remain
unchanged; the new worktree is `sources/rexglue-stop`. Build jobs are serialized
per machine with at most two workers. Native and core-sanitizer build caches
are separate; every attempt receives a new copied SDK package and receipt.

```text
python tools/prepare_runtime_stop.py --root PRIVATE_CACHE --baseline-report MEMORY_RECEIPT --fetch
python tools/test_runtime_threads.py --root PRIVATE_CACHE --sdk-report STOP_RECEIPT --sdk-profile stop --output-root PRIVATE_OUTPUT --suite all
```

`--fetch` is required for the first worktree/submodule preparation. Later runs
can omit it. The Linux core-sanitizer variant requires both an instrumented
memory parent and `--core-sanitizers`; the diagnostic driver then also requires
`--sanitizers`. Native SDK plus `--sanitizers` instruments callbacks only.
Windows uses native runtime libraries with supported host UBSan traps; core
ASan remains unsupported.

The patch adds a cooperative-stop exception tag derived from the existing
explicit-exit exception. The original base layout and explicit payload remain
unchanged. The kernel resolves the tag to its own recorded requested exit;
fiber forwarding keeps that existing request. Import/hook entry and exit checks,
plus stoppable spin acquisition, use the tag. Standard explicit thread exits
continue through the original exception path.

Preparation rebuilds base/PPC/kernel and stages the three modified public
headers together with those libraries. Other module/dependency files retain
their verified parent identities. This is not full-SDK instrumentation or ABI
compatibility proof with arbitrary external modules. Every affected maintained
callback is freshly compiled against the chosen package. Any future owned-title
consumer must regenerate/rebind its preparation identity and rebuild with these
headers before acceptance. Current owned-title preparation does not automatically
accept this separate SDK profile.

The verifier refuses stale preparers/locks, modified compositions, reset/changed
sources, changed parent receipts, compiler mismatches, changed package files and
instrumentation mislabeling. Those local provenance checks are not signed
attestation, an access boundary, or permission to execute untrusted inputs.
No game assets, generated game code or private SDK packages belong in Git.
See [patch terms](NOTICE.md); release clearance remains separate.
