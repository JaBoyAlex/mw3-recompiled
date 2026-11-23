# Allocation-import ABI investigation

MW3-046 passes its scoped actual-kernel allocation-import contracts using the
explicitly selected [MW3-091 safety profile](memory-imports-profile.md).
No allocation import has been admitted into owned MW3 startup.
Direct address-space tests and a successful binding do not establish
the ABI or failure behavior of an export.

The first original fixture invokes the selected SDK's actual kernel export
table from a real SDK-created guest thread. It loads an empty original image,
executes native callbacks and embeds no title bytes or translated instructions.
Manual big-endian byte stores/loads check the in/out words, committed allocation
edges and neighbouring canaries. Thread exit metadata, handle/title-page
accounting, unload/destruction and SDK thread recovery are checked. The executable
links the real kernel library, without embedding kernel object libraries, and
the driver hashes the kernel path actually reported loaded.

## Source and contract review

Selected source: ReXGlue `ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d` with the
reviewed `xma-packet-v1` composition. Its `xboxkrnl_memory.cpp` declares
allocation as two mapped big-endian in/out words followed by allocation flags,
protection and region type. Free takes the two mapped words, free type and
region type. `ppc/call.h` truncates mapped-pointer arguments to guest 32-bit
addresses and translates them; that conversion does not validate the pointee's
range, permissions or alignment. The entry must handle unsafe inputs before
dereferencing them.

[Pinned Xenia source](https://github.com/xenia-project/xenia/blob/95a5c3ee250f80c3b9d139658649d9ffb6db3eec/src/xenia/kernel/xboxkrnl/xboxkrnl_memory.cc)
is a comparison, not an independent retail oracle: the implementations share
ancestry. Its fifth allocation argument and rounding/release behavior differ
from the selected fork. Microsoft's
[NT allocation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntallocatevirtualmemory)
and [free](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntfreevirtualmemory)
documentation supplies general reservation/commit/release concepts; the Windows
signatures and some rules differ and are not substituted for the Xbox ABI.
No retail-console differential capture is available. Expectations use an
original bounded allocation model and independently checked byte/range/state
properties; selected-fork policies are identified as such.

## Evidence method and failure boundary

The fixture resolves export names and checks allocation/free ordinals `0xcc`
and `0xdc` against the actual selected-kernel export table. The SDK creates
and joins the guest thread; no kernel object files or replacement functions
are compiled into the fixture. The synthetic image and callback address map
are original test data, unrelated to MW3 executable addresses. There is no
generated guest code or owned-title execution in this lane.

Cases use manual big-endian byte access, fresh/recommitted edge-word checks,
canaries and rejected-call byte snapshots. They exercise ordinary reservation,
commit, decommit/recommit and release, negative-size rounding, physical in/out
aliases, double release, unsupported flags/protection/region values, both
in/out words with null, unaligned, unmapped, wrapping and read-only addresses,
and identical in/out words through ordinary and physical-alias addresses.
A repeated case alternates forward/reverse orders for twelve successful
allocation/lifecycle scenarios. Recovery checks cover title pages, handles,
thread termination, runtime unload/destruction and process thread counts.
They do not prove general race freedom or every memory service.

Each final process must echo its fresh nonce at arming and completion. The
verifier requires each call/return and verified step in order, exact counts,
matching teardown thread counts and the expected return code. The three
controls deliberately produce a wrong result, omit completion or exceed a
five-second deadline. A control cannot pass with a missing/failed baseline
allocation/free, an unrelated failure, a stale nonce or an unexpected record.
Synthetic protocol tests exercise these rejection rules; they are not kernel
execution evidence.

The driver verifies the selected XMA/stop/memory SDK composition before and
after execution and hashes each kernel path reported loaded. Windows CMake
copies SDK DLLs beside the probe; these copies must have the exact approved
kernel content. Source, driver, compiler, SDK receipt/package, compile commands,
binary and logs are retained with hashes in each private manifest. Logs and
binaries remain private. A FAIL manifest is retained and returns nonzero;
faults and sanitizer reports never become successful negative tests.

## Retained earlier baseline

The original Linux participating-kernel ASan/UBSan attempt
`ceb7cb11b36e460aab8b2b5f84b3ca85` passes ordinary allocate/write/free and
retains null free-pointer and signed-minimum negation failures. Its missing
symbolizer is recorded; subsequent runs select an available LLVM symbolizer.
The later pre-nonce matrix retains 190 processes (38 in each of five profiles):
Windows native/host UBSan each have 15 failures, Linux native/host ASan+UBSan
each have 13, and Linux participating-kernel ASan+UBSan has 17. All fifteen
control processes are rejected as designed. These are historical artifacts,
not evidence for the final nonce-bound producer. Initial private audit-helper
assumptions about the SDK allocator translation unit, Windows Optimus helper
and copied DLL location were corrected before artifact auditing; original
failure logs are retained.

## Final retained baseline — 2026-11-22

The final producer runs **205 actual-kernel processes**, 41 per profile. These
are retained baseline failures, not acceptance of the SDK. All loaded kernel
contents, source snapshots, compiler identities, SDK package inventories,
compile commands, probe binaries and log hashes were rechecked after the run.

| Profile | Ordinary passes | Correctly rejected controls | Actual failures |
| --- | ---: | ---: | ---: |
| Windows native | 21 | 3 | 17 |
| Windows host UBSan traps | 21 | 3 | 17 |
| Linux native | 23 | 3 | 15 |
| Linux host ASan/UBSan | 23 | 3 | 15 |
| Linux participating kernel ASan/UBSan | 19 | 3 | 19 |

All ordinary allocation/lifecycle/repeat cases pass. The failures are unsafe
in/out words and aliased free output words; participating-kernel UBSan also
reports signed-minimum negation and typed misalignment. A fault remains a
failure even when the argument is deliberately invalid. Host instrumentation
does not instrument the linked native SDK. Windows core ASan is **NOT RUN**
because the approved profile does not support it. Linux participating-kernel
coverage retains the parent's native XAM library and disabled vptr checks;
external/system libraries remain native. No translated code is instrumented.

The earlier nonce-bound 205-process attempt also retained one Windows host
incomplete-control failure: deliberately calling `_Exit` in a live guest
callback triggered a DLL shutdown access violation. The final control returns
normally, verifies full recovery and omits only its footer. The verifier now
also rejects SDK crash/exception diagnostics, including with a zero exit code.
The failed attempt is retained; no SDK shutdown repair is claimed here.

The byte-identical final driver SHA-256 is
`6425f2c62b8a8532cd233f5377d878746f998e609d018c22d24c7dfa9d98e0cc`.
Per-profile retained artifact identities (SHA-256):

| Profile | Manifest | Actual loaded kernel | Probe binary |
| --- | --- | --- | --- |
| Windows native | `552400f2469e0edd1c39174b85bedccc8ba5ceecd5919176868175d10fd748e5` | `2ac5f027dc4a0975d1dfc51440c282448057a02daa9fd3367b9d46b4a82a27f1` | `e0a212d860b925926ccc67a0de06e43e5a4e33daf084769d586f278fab5964bb` |
| Windows host UBSan traps | `cc8cb6d14010ddd1eff0c313bc10619ecb05c14c8a4dcb432924c74fdc390261` | `2ac5f027dc4a0975d1dfc51440c282448057a02daa9fd3367b9d46b4a82a27f1` | `4ff67b9482bdbced3794f27d77454fbafd620ef956a9e250fc05a743b9a8b6b6` |
| Linux native | `2caac48448b7d90d884d60efca1e826fd54af78d774f8a49583623ff7c3e5dae` | `006fa034d23dfc6837f4e3e05c5113ddce3478affac5a735418fb821a90b6cb9` | `7686a44766be5b8e4b3e62748334dc0a9257c710a34873b5e8fea23efb090ead` |
| Linux host ASan/UBSan | `14a41572e2dd1c302b2d8726fcdbb0f9cc6381530a60346202c485d806066ff2` | `006fa034d23dfc6837f4e3e05c5113ddce3478affac5a735418fb821a90b6cb9` | `9eb37046459f89ab2bbaced557357dae4d038f459fda3db92e1064051aade35d` |
| Linux participating kernel ASan/UBSan | `5d02157d9061c804018c1e233ef48feebbcd94c47b361cf692c48931b2477b47` | `36153ce9115cc8071b268bb0012c2f72720e9df41e287b4b877a43ade315f942` | `3fa0f947f42049d62f51cd6f2525c941096900c7717aba2ac846bf259dbbfbfa` |

Reproduction (all paths are private and machine-specific):

```sh
python tools/test_startup_memory.py --root "$SDK_CACHE" --sdk-report "$VERIFIED_XMA_REPORT" --output-root "$PRIVATE_RUNS"
python tools/test_startup_memory.py --root "$SDK_CACHE" --sdk-report "$VERIFIED_XMA_REPORT" --output-root "$PRIVATE_RUNS" --sanitizers
```

Run the first command once for each native host and the second for Windows
host traps, Linux host sanitizers with its native report, and Linux
participating-kernel sanitizers with its matching XMA core report. Exit 1 and a
FAIL manifest are expected for these defective parents. Do not relabel that
nonzero result as a passing ABI audit. `--cases` permits focused reproduction.
All 41 selections and exact per-attempt configure/build/run commands are
retained privately. Public positive/negative protocol checks require no SDK:
`python -m unittest discover -s tests/startup_memory -v` (7 tests pass).

## Retained baseline public verification

`python tools/check.py --config Release` passes on native Windows: 305 Python
tests with 8 explicit skips, and the native parser CTest passes. Skips cover
the POSIX FIFO contract, unavailable Windows symlink privilege and the
unavailable LLVM assembler/objcopy pair. Native Windows junction contracts run.
`python3 tools/check.py --config Release --sanitizers` passes on Linux/WSL:
305 Python tests with 2 Windows-only junction skips, plus parser CTest under
ASan/UBSan. The standalone selected-kernel fixture uses Clang 20.1.2;
the Windows public build uses MSVC 19.44.35229.0 and SDK 10.0.26100.0.
These public checks exercise original game-free code and retained-result
rejection logic. They do not turn the failing actual-kernel matrix green.

## Retained repair handoff (before adoption)

MW3-091 is a bounded, separate SDK derivative. It must check both in/out words
before trace reads, typed dereferences or mutation; reject null, alignment,
range, permission and overlapping/aliased-word hazards; and calculate negative
32-bit size magnitude without signed-minimum negation. It must retain valid
physical aliases, ordinary lifecycle behavior and all unaffected parent-package
files. Its native and supported participating-kernel sanitizer evidence must
use isolated derived sources and a strict preparation verifier. The original
SDK/source/build outputs remain read-only.

After that child passes, re-claim MW3-046, adopt the verified derivative in a
separately reviewed consumer change and rerun the complete ABI matrix. Do not
complete 046 or admit either memory import while these safety criteria fail.
Any additional demonstrated SDK defect needs its own agreed repair scope.

No retail-console differential capture, concurrent mutation guarantee,
full memory-import parity, title allocation call, later startup, rendered MW3
frame, gameplay, latency or performance result is claimed. This PR changes
only original tests/driver, this report and the explicit parent/child task
scope. No SDK or guest service allowlist is changed. Public test source is
original GPL-3.0-only code; it calls the private selected BSD-licensed SDK
without copying SDK implementation or proprietary content. SDK-facing fixture
builds use its required C++23 headers; the fixture uses C++20 language features.
Self-review only; no independent review is represented.

## Verified repair adoption — 2026-11-22

MW3-091 completed the isolated SDK repair in PR135. Lead unblock PR136 records
that dependency resolution; its successful serialized claim is task-admin run
45113147849. This separate consumer change explicitly selects and verifies
`memory-imports-v1`, preserves `xma-packet-v1` as the historical default, and
never retries another verifier after a receipt failure. A repaired receipt
without its explicit profile selection is rejected. The selected verifier's
byte hash and profile label are recorded and rechecked with the SDK/package.

All **205 actual-kernel consumer processes pass**: 190 ordinary passes and 15
correctly rejected wrong-result/incomplete/deadline controls. Each of five
profiles runs all 41 cases, including the twelve-scenario repeated-order case.
All 205 per-process nonces are distinct. The original C++ callback and CMake
inputs are byte-identical to the retained failing baseline; `steps`,
`calls_match`, `classify` and `mutation_rejected` are AST-identical. The CLI,
profile verification and output-isolation code change; rejection rules are
not weakened. No kernel source or package is changed by this consumer.

| Profile | Ordinary passes | Rejected controls | Unexpected failures |
| --- | ---: | ---: | ---: |
| Windows native | 38 | 3 | 0 |
| Windows host UBSan traps | 38 | 3 | 0 |
| Linux native | 38 | 3 | 0 |
| Linux host ASan/UBSan | 38 | 3 | 0 |
| Linux participating kernel ASan/UBSan | 38 | 3 | 0 |

A second artifact audit rehashes every actual loaded kernel, probe binary,
compile-command record, source snapshot and run log, then revalidates the
current preparation, compiler and complete SDK package. Its matched baseline
uses the exact original XMA package as parent, the same compiler and matching
host instrumentation. The new uncompiled Python profile tests are not guest
or kernel code. All old baseline failures and earlier development attempts
remain retained, not relabeled as passing negative tests.

The fresh consumer driver SHA-256 is
`bbcaee5b1bc53e53e7722049011ddd556d5d74148664b3aae530df0dc8730592`.
Original C++ SHA-256 remains
`73e7d4be8445eca261fea1369ee53b1cac0d9b82d7d92bd26a20d120b6abd7ef`.
Per-profile artifact identities (SHA-256):

| Profile | Manifest | Actual kernel | Probe binary |
| --- | --- | --- | --- |
| Windows native | `6c3048f11ab44a80761d4b28f25472aff62fd8a077592293ec3599bf1c4715ef` | `aaa93ebbfa3706ae54ac5aaae33931651abf79d4b976299cd2164c48224f3d92` | `7f8fb9b6867596d073fd925b5c978adde6afd4b3281eaaab1c837578d2af9688` |
| Windows host UBSan traps | `4cbbb7f0093475326c61f91f74bcab8df1c89dc4f8062fa53efc0571ed275d09` | `aaa93ebbfa3706ae54ac5aaae33931651abf79d4b976299cd2164c48224f3d92` | `62ba11930e6752d4dd9db7b6f337feb796d0ba53ee59d401c70e29491967cbf0` |
| Linux native | `c5b94c35f3ae05dbddbd5ed76c6bf0129d7b02cd67154d9664858f6615dc9e65` | `828fc85eabd1c07bfa32dadf92ee2a6547a44444fde945a9384b9ae56169139b` | `7686a44766be5b8e4b3e62748334dc0a9257c710a34873b5e8fea23efb090ead` |
| Linux host ASan/UBSan | `a551ce126138e1ef435f2553e0a0e7982e468a79575cbafc3e7d2a4cafd05b6c` | `828fc85eabd1c07bfa32dadf92ee2a6547a44444fde945a9384b9ae56169139b` | `4e62c36c5228ec49ecd517c02b3381be14cc784ec07caa04ce35aee2e4906dd2` |
| Linux participating kernel ASan/UBSan | `011ca934c4bf3218cfb6192a1ca797f93bcd47716c4add8172a1119b88ef119a` | `ef88723255d88a31f092eff0a169782b8bca8611442330e7588058838adfdce6` | `255e7665d6d63d4479cb3118bb71883c6bb3ef5df946419978af5f01d98d6ace` |

Private retained run IDs: `windows-native:609060abd772403a973b542a8c55d751`, `windows-host:04d148d282d44a1eafc4b728c4c456cb`, `linux-native:64f4bdae842946079a9f2a3a4bbc9cbd`, `linux-host:2e986f3094b142e2998b54f4a39cb62a`, `linux-core:9069a584ed204f9bbfb7e99f7d2e0365`.

Six real receipt-refusal CLI processes pass (three per native host): repair
selection with an original-parent receipt, default/baseline selection with a
repair receipt, and a changed repair-lock receipt all exit 2 before creating
their requested output directory. Eleven public protocol/profile/isolation
tests pass, including four new synthetic guards. Rejected output roots include
both SDK preparation families, selected receipt/package, source/build/install
caches and maintained inputs. Accepted roots are canonicalized, including
Windows short-name aliases. No input directory is used as writable output.

Reproduce repaired acceptance on each native host, then with host sanitizers
and the matching Linux participating-kernel receipt:

```sh
python tools/test_startup_memory.py --root "$SDK_CACHE" --sdk-report "$VERIFIED_REPAIR_REPORT" --sdk-profile memory-imports-v1 --output-root "$PRIVATE_RUNS"
python tools/test_startup_memory.py --root "$SDK_CACHE" --sdk-report "$VERIFIED_REPAIR_REPORT" --sdk-profile memory-imports-v1 --output-root "$PRIVATE_RUNS" --sanitizers
python -m unittest discover -s tests/startup_memory -v
python tools/check.py --config Release
CXX=clang++-18 python3 tools/check.py --config Release --sanitizers
python tools/project.py validate
python tools/check_repository.py
git diff --check
```

Windows Release: 317 Python tests, eight explicit FIFO/LLVM/symlink skips,
parser CTest 1/1 PASS (Python 3.12.14, MSVC 19.44). Linux Release ASan/UBSan:
317 tests, two Windows-junction skips, parser CTest 1/1 PASS (Python 3.12.3,
Clang 18.1.3). The private kernel/probe profiles use matched Clang 20.1.2.
The 66-task DAG and heuristic/manual provenance/diff checks pass. The retained
report's single legacy Windows-1252 dash is normalized to UTF-8; hashes and
historical results are unchanged. Only this task's JSON is completed.

The old XMA default intentionally reproduces failures; matching its historical
tests is not current acceptance. Windows participating-kernel sanitizers remain
unsupported; host traps do not instrument native SDK libraries. Linux kernel
coverage retains native XAM/system dependencies and disabled vptr checks.
Linux/WSL uses the same machine as Windows, not independent hardware. No
generated guest code participates in these game-free callback cases.

This passes the scoped selected-fork contract gate, not retail-console ABI
parity or every memory service. No MW3 allocation call or later startup import
is admitted here. Concurrent mutation and self-unmapping output buffers remain
outside this bounded fixture. Follow with a separately claimed, hash-bound
actual-title allocation/call-site checkpoint before advancing first-frame 011.
No gameplay or performance claim follows; this consumer changes no shipping
runtime policy. Self-review only; no independent reviewer claimed. Existing
BSD/Xenia notices and GPL tooling provenance remain unchanged; no SDKs, game
bytes, translated title code, private logs or binaries are published.
