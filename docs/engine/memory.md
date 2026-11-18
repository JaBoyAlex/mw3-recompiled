# Selected-runtime memory contracts — 2026-11-17

**Memory correctness gate remains open.** MW3-037 supplies a reproducible
regression harness and records an actual SDK defect; it does not certify the
selected runtime. MW3-042 repairs decommit behavior before kernel integration
041 can pass. No title code executes in these tests and no performance claim
is made. The owned-title startup checkpoint remains separately documented in
[Windows bring-up](windows-bringup.md).

## Reproduce

Use the already reviewed private SDK preparation and exact analysis metadata:

```powershell
python tools/test_runtime_memory.py --root <private-runtime-cache> `
  --sdk-report <verified-sdk-manifest.json> --metadata <verified-analysis-directory> `
  --output-root <private-memory-results>
```

Add `--sanitizers` for Linux host ASan/UBSan or Windows calibrated host UBSan trap
mode. An explicitly verified instrumented Linux core SDK can also be supplied
with that flag. This test-only option does not relax the generation driver's
refusal to use a validation-only SDK. See the Windows profile for its ASan/CRT
limitations. Compiler/source/package verification happens before execution, and
SDK identity is checked again afterward. Each attempt keeps commands, geometry,
source/compiler/library/binary/log hashes and an individual result per process.
The helper returns **1 while these real decommit failures remain**; do not
convert it to a passing exit merely to merge testing infrastructure.

`tests/memory` is an isolated SDK-facing C++23 adapter; public core remains
C++20. Public CI runs only its Python evidence-classifier tests, with no SDK or
game content. Run `python tools/check.py` for those ordinary checks. Private
integration builds require the selected SDK. This is not a user-facing installer.

## What runs

The original synthetic PPC image contains one native callback, not translated
instructions. A bounded semaphore handshake keeps its runtime-created stack
alive while testing its actual PCR stack limits, guard and alignment. Completing
that callback releases its stack even when its object handle remains open;
the first fixture incorrectly assumed otherwise. The corrected fixture waits
for and closes its own thread, then unloads the runtime normally. Deliberate
hardware-fault processes cannot run orderly teardown or leak checks.

Three layouts run independently: synthetic geometry and exact hash-bound SP/MP
image/code extents from the reviewed inventory. Geometry is not original title
execution. Each profile has 48 processes: 14 scenarios, with three distinct seeds
instead of one for allocation stress. Each stress process performs 2,048 bounded
operations with up to 32 live blocks, 64/128 KiB sizes and 64 KiB–1 MiB alignment.
All live ranges and edge words are compared with an independent record after
every operation; allocations must avoid image/function-table extents. A deliberate
expected-word mutation must fail the actual content comparison.

Cases cover A/C/physical-window coherence and byte order, foreign host pointers,
null/wrapping/cross-heap ranges, rejected cross-protection writes without prefix
mutation, reserve/middle-page commit/read-only/decommit/recommit/release, released
checked-pointer rejection and double-free refusal. Real raw accesses test stack
guard, read-only, strict released-page and decommitted-page behavior. An armed
case marker alone cannot pass: the subprocess must terminate with the correct
platform fault. Timeout, wrong marker, normal return and sanitizer errors fail.
For deliberate page faults only, Linux ASan signal interception is disabled;
all other instrumented cases retain normal ASan diagnostics and leak checking.

The SDK intentionally defaults `runtime.protect_on_release` to false. Default
host access is recorded separately; checked released-pointer rejection still
passes. The strict raw-release case explicitly enables the setting and faults
on both hosts. An earlier test assumed strict protection without enabling it;
that failure is retained and is not presented as an upstream defect. This is
separate from decommit, which has no such opt-out in this test contract.

## Actual results and defect

| Profile | PASS | FAIL | Coverage limit |
| --- | ---: | ---: | --- |
| Linux native | 36 | 12 | Uninstrumented SDK/adapter |
| Linux host ASan/UBSan | 36 | 12 | Packaged SDK uninstrumented |
| Linux core + host ASan/UBSan | 36 | 12 | Core base/PPC/kernel instrumented; prepared graphics/dependency archives uninstrumented |
| Windows native | 36 | 12 | Uninstrumented SDK/adapter |
| Windows host UBSan trap | 36 | 12 | Calibrated host checks; SDK uninstrumented, no Windows ASan |

Every profile reproduces four failures in every layout:

- `decommit-copy`: GuestMemory accepts a read span after commitment is cleared.
- `decommit-view`: MemoryView reads the decommitted page.
- `decommit-store`: GuestMemory actually writes the decommitted page.
- `decommitted-read`: a raw read returns instead of faulting.

The fixture independently checks the SDK's page metadata no longer has the
commit bit. Source inspection at SDK commit
`ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d` explains the observation:
`BaseHeap::DecommitLocked` clears commitment but retains current protection;
`QueryProtect` reports those protection bits without checking commitment, and
checked-access callers rely on them. `SyncHostPageAccess` returns early when
guest pages are at least as large as host pages, leaving the old host mapping
accessible. These are observed implementation paths, not a proposed verified
repair. Task 042 owns their caller audit, patch, isolated derivative, regressions
and eventual cache/owned-title integration. No SDK source is changed by 037.

The initial stack-lifetime and release-policy fixture failures remain private.
No final pass count includes them as successful SDK behavior. The final stricter
classifier also revalidates all 240 retained log/binary hashes against unchanged
compiled C++/CMake sources; classifications remain identical. Its validation
receipt is `classifier-validation.json` in the private Windows memory-results
root, SHA-256 `5fb1de0d47bf415a3317d6666a4a30fbdbb05e7812afbeb4a31fc30ab0090016`.

## Private receipts

Linux manifests are relative to `memory-contracts/` in the owner's Linux cache;
Windows manifests are relative to the private Windows `memory-contracts/` root.
All five manifests report **FAIL**, with 36 passing/12 failing cases each.

| Profile | Attempt / manifest.json | SHA-256 |
| --- | --- | --- |
| Linux native | `3d8424b3c4d34b4f8031665f53538261` | `31d051cdfc443ed5938250e1ce03c897803484eae8fbd2a648e6beca9fe08279` |
| Linux host sanitizers | `b95e2350d7fa4dfaa82d51c69392a1f8` | `8281a50dfb283057a717ead35ab4485936719efc35ae9dcf69ad9939a3f99ae8` |
| Linux core sanitizers | `692bcd5fdfa74422bd863dab6ab3f078` | `ad4b114ae38cd8319f0dc91363df46f4ccf76b61ff328beff75982bd2408e2e3` |
| Windows native | `1aef990253cf46b3b541aa9b7c8b2555` | `6c2b8699a350cea0d3dfe199f15ee1246ce0487290b3a814d32720ec27c9ecf9` |
| Windows host sanitizers | `2bca91a0b5694a2bbfa354b7560f60fc` | `97d10ff5931e212bada847411deee299827ddde6eeff1eaecfa58cc0047ccd2d` |

Self-reviewed. No independent review, gameplay correctness, aggregate SDK pass,
performance improvement or game-linked redistribution approval is claimed.

Final public checks: Windows `python tools/check.py --config Release` passes
86 Python tests with five explicit LLVM/symlink skips and native CTest. Linux
`python3 tools/check.py --config Release --sanitizers` passes 88 Python tests
without skips and ASan/UBSan CTest. The catalog and repository provenance
heuristic pass; the latter is not legal clearance. Exact-head CI is required
before merge. Actual SDK integration results above intentionally remain failing.

The lead extends 037's reservation to the root status summary after 040 closed,
so future contributors see the retained failures and current public test counts.
No other active owner overlaps this summary change.
