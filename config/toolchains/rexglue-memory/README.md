# Isolated memory repair profile

Task 042 is in validation. Do not mark its acceptance complete from compilation
or the first Linux result. Follow [memory evidence](../../../docs/engine/memory.md)
for baseline failures and final integration status.

Start with the verified native baseline SDK from task 008 (Linux) or 040
(Windows). Keep its preparation receipt and cache unchanged. Then:

```powershell
python tools/prepare_runtime_memory.py --root <private-runtime-cache> `
  --baseline-report <verified-baseline-sdk-manifest.json> --fetch
```

`--fetch` creates a separate source worktree and obtains exactly pinned
submodules. Later builds omit it. Source/build outputs are distinct from the
baseline; each preparation receives its own immutable package and receipt.
An absolute, unused install prefix avoids an upstream repeat-configure issue;
no global installation occurs. At most two build workers are used.

Linux additionally supports `--core-sanitizers` for a test-only instrumented
base/PPC/kernel package. That package is refused for title code generation.
Windows full-core ASan is not supported by this profile. Both platforms consume
the previously prepared graphics/dependency components; this is not full-SDK
instrumentation or a renderer verification.

Run the original memory harness with the new receipt:

```powershell
python tools/test_runtime_memory.py --root <private-runtime-cache> `
  --sdk-report <new-memory-manifest.json> --metadata <verified-analysis> `
  --output-root <private-results>
```

Add `--sanitizers` for the supported host instrumentation. Expected raw-fault
cases must actually fault; mismatched metadata, modified packages, reset sources
and rewritten patch receipts fail rather than being silently repaired.

For the native Linux package, use the **new** receipt with `tools/recompile.py`,
including `--reproduce` for clean generation comparison. The cache identity
records patch composition and package/preparer/config hashes. It cannot reuse
an older generation under the same key. Windows imports only a locally reviewed
generation receipt with an independently checked SHA-256; the current memory
profile must match. Generated source remains private and is regenerated, not
edited. Title probes retain their original narrow service allowlist.

This is local provenance checking, not signed build attestation or permission
to execute untrusted SDKs/receipts. Patch terms are in [NOTICE](NOTICE.md).
No SDK/game-linked redistribution or performance improvement is established.
