# Explicit stop-boundary SDK derivative

MW3-043 passes the standalone [validation matrix](validation.md).
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
can omit it. The Linux core-sanitizer variant takes an instrumented memory
parent, `--core-sanitizers`, and `--native-report NATIVE_STOP_RECEIPT`. It uses
the verified patched native XAM so its shared-library link can resolve all
symbols. Run the diagnostic driver with `--sanitizers`. A native SDK plus
`--sanitizers` instruments callbacks only.
Windows uses native runtime libraries with supported host UBSan traps; core
ASan remains unsupported.

The patch adds a cooperative-stop exception tag derived from the existing
explicit-exit exception. The original base layout and explicit payload remain
unchanged. The kernel resolves the tag to its own recorded requested exit;
fiber forwarding keeps that existing request. Import/hook entry and exit checks,
plus stoppable spin acquisition, use the tag. Standard explicit thread exits
continue through the original exception path.

Preparation rebuilds base, PPC, kernel and XAM and packages the three modified
public headers with those libraries. XAM instantiates the thunk in its own
binary. The other packaged dependencies retain their verified parent identities.
Each maintained callback compiles against the selected headers. The synthetic
tests cover kernel and XAM import entry, native thunk return, and explicit exit.
The profile is selected explicitly for standalone diagnostics.

The verifier refuses stale preparers/locks, modified compositions, reset/changed
sources, changed parent receipts, compiler mismatches, changed package files and
instrumentation mislabeling. Those local provenance checks establish the
identity of the tested package. See [patch terms](NOTICE.md).
