# Selected-kernel display-query audit (MW3-051)

The declared default display-query policy matches the observed selected SDK on
five local profiles. The investigation is complete; console compatibility and
invalid-output containment remain **INCONCLUSIVE**. Invalid pointers terminate
owned processes, a near-4-GiB pointer returns on Linux, and a misaligned output
returns except in the instrumented core. None is a compatibility pass.

This is original synthetic guest-callback evidence, not MW3 execution. No title,
GPU service, frame, menu, gameplay, mode or split-screen gate passes. The bounded
real-title startup limitation in STATUS remains unchanged. There are no game
executable hashes in this audit because no game executable is used; all host
callback binaries and actual SDK modules are bound below.

## Scope and provenance

The already assigned issue [121](https://github.com/JaBoyAlex/mw3-recompiled/issues/121)
was resumed in `codex/MW3-051-gpu-display`, isolated from allocation work MW3-046.
Scope PR 120 merged as `eac50a613458306cf6ecb3b17aaf92d012a965ae`;
serialized claim run `44516375545` succeeded before implementation. Dependencies
MW3-037/039/044 are catalog-done and their issues are closed. Only this audit's
tests, driver, report and task JSON change. SDKs, shared interfaces, GPU packets,
shaders, guarded startup, service allowlists and other task reservations do not.

The SDK base is `ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d`, using the
reviewed memory, thread-stop and XMA lifecycle repairs. Its final derived source
tree is `1074403692f2259ac2d19abf36d2be9afa60c771`, patch SHA-256
`9af19fc3bd961d9bbd2353e2980f14d3df82a04477a25ba5c902cb323590f770`.
The driver verifies the selected preparation, recursive source identity,
libraries, helper and tool bytes before and after the suite. It does not build
or modify the SDK. Separate re-reading on November 22, 2026 reconciled the sealed
artifacts, current maintained sources/helpers/declarations/tools, loaded module
bytes, plans, nonces, observations and controls. This is a second analysis pass
by the owner agent, **self-review**, not an independent human review.

The five maintained inputs and driver have these SHA-256 identities:

- `__init__.py`: `005968a953091e26becb75148418187a7737a57731485eec99d23fc07a6677b9`
- `CMakeLists.txt`: `ab3bb08dba09eb2c246c559eab4cbe4274bfe31a261059f04ccac01267a76681`
- `oracle.py`: `48fba95f82d00c87bb52e230f26754850cb8f6f845f9c781a8bd469c474c2d57`
- `probe.cpp`: `0e6675e90d1547d7d3c0d5e48e9c2a010a3d72fa97ec9ac573b986d1a2c755c7`
- `test_evidence.py`: `5a966c589d49e1ecc48824dd147955bd5b5715bd25d31d0a76ab5de286268ba5`
- `tools/test_gpu_display.py`: `7fe5f96eca74de1c96cf23476059e5e8b3e9e55736e9897a8167e790da609b93`

Inspected declarations/implementation, identical across the five runs:

- `src/kernel/xboxkrnl/xboxkrnl_video.cpp`: `e19a31f6795733f4c68733d9eb9fca885086a270a5ae8f5fd61527edc6c51347`
- `src/kernel/xboxkrnl/export_table.inc`: `187758bc47a757b4ad3fed3edc37076362a4d3ef7e8711e44eb301ae73aabae7`
- `include/rex/kernel/xboxkrnl.h`: `a65eae0ab8dd8e4077cce76cdcc17e0705c9c8e5166cb59e316e140b7e52789b`
- `include/rex/ppc/call.h`: `52bfe314fa5af87d1c6fc685e3e151e583ff0db4c4e8129e244e118757c50309`

The implementation is inspected upstream data, not copied into public source.
The Python oracle uses standard-library big-endian packing and its own offset
table; it does not call the SDK serialization routine. It checks the declared
SDK policy, which is not a retail-console oracle. The original host probe uses
an isolated C++23 target because the selected SDK headers require it; public
game-free project code retains C++20. Compilation inputs are only `probe.cpp`
and the SDK's host allocator bridge `rexglue_host_alloc_stub.cpp`; no kernel
implementation translation unit is compiled or substituted into the probe.
Game data, translated code, SDKs, binaries and raw private logs remain outside Git.

## Observed query ABI

Each export is looked up by Xbox kernel ordinal, exact name and function type.
The live function address must belong to the same actual kernel module; the
module path and full SHA-256 must match the selected package (or an identical
copy in the owned build). A separate actual base-library address is checked.
No local stand-in export supplies a success result.

| Export | Ordinal | Pinned prototype/output policy |
| --- | --- | --- |
| `VdQueryVideoMode` | `0x1ca` | `void(GuestPtrT<X_VIDEO_MODE>)`; 48 bytes, 4-byte packed fields |
| `VdGetCurrentDisplayInformation` | `0x1ba` | `void(GuestPtrT<X_DISPLAY_INFO>)`; 88 bytes, including zeroed padding |
| `VdGetCurrentDisplayGamma` | `0x1b9` | `void(MappedU32, MappedF32)`; two separate 4-byte outputs |
| `VdQueryVideoFlags` | `0x1c9` | `u32()`; full observed `r3 == 3`, no output-memory writes |

The observed default mode is 1280 by 720, progressive, widescreen, high definition,
60 Hz. Mode fields use big-endian integers/floats, video standard 1 and declared
reserved values `0x4a`, 1, 0, 0, 0. Display information includes matching source
and scaled rectangles, vertical/horizontal filter type 1, overscan 320/180 on
each axis, actual width 1280 and 60 Hz; unspecified fields/padding are zero.
Gamma writes big-endian type 2 and float32 bits `0x400e38e4` (2.22222233 rounded
to float32). The flags are widescreen bit 0 plus width-at-least-1024 bit 1;
the source's width-at-least-1920 bit 2 is clear in this default configuration.
Alternate resolutions, refresh rates, standards, gamma settings and retail
expectations are unmeasured. The adjacent mode-setting no-ops cannot inject a
validated alternative configuration.

Original callback addresses/data are synthetic and have no MW3 address meaning.
Calls execute inside real owned SDK guest threads with PCR/TLS and `r13`
validated against the actual calling thread. A poisoned high half in `r3/r4`
exercises the wrapper's 32-bit guest pointer handling. Before/after checks cover
`r1`, `r2`, `r13` and `r14` through `r31`; the initial stack is aligned. The void
calls' volatile return register has no invented return-value requirement.
FPRs, CR/LR, arbitrary PPC code and general ISA conformance are outside coverage.

Each ordinary process executes 128 observations: four services at eight bounded
16-byte-aligned scratch offsets, repeated four times. Four offsets are fixed
(including a near-page-boundary position), four are seeded. The independent
oracle checks all 128 serialized bytes per observation plus a full surrounding
128-KiB scratch canary, exact endian/extent, flag placement and preserved GPRs.
Three independent repeated processes, one genuinely reversed input plan and a
different held-out seed give five ordinary processes per profile.

## Runs and boundary findings

Four saved profiles ran November 19, 2026; the missing non-sanitized Linux
baseline was run on resumption November 22 using unchanged producer/source bytes.
These are five profiles, not the saved orchestrator's erroneous "five" label
for its original four. Every profile has 13 owned subprocesses: five ordinary,
five invalid-output boundaries and three controls. Total: **65 subprocesses,
25 ordinary successes, 3,200 ordinary serialized observations, 25 observed
boundaries and 15 successful rejection controls**. Rejection-control success
means detection worked; it does not turn the audit into a compatibility pass.

| Profile | Null mode / guard-crossing display / read-only gamma | Near-4-GiB mode (`0xfffffff0`) | Misaligned display |
| --- | --- | --- | --- |
| Windows native | access violation `0xc0000005`, each | access violation | returns |
| Windows host UBSan trap | access violation `0xc0000005`, each | access violation | returns |
| Linux native | signal 11, each | returns | returns |
| Linux host ASan/UBSan | code 1 with sanitizer diagnostic, each | returns | returns |
| Linux participating-core ASan/UBSan | code 1 with sanitizer diagnostic, each | returns | code 1 with alignment diagnostic |

Each fault follows a nonce-bound armed service/pointer record in that isolated
process. A fault is retained as a termination observation, not as verified guest
error handling. Fatal probes have no verified normal cleanup footer. Returning
boundaries likewise never pass containment: in particular the wrapped output's
complete destination extent is not serialized, and a host accepting an unaligned
store does not establish console alignment semantics. Intentional bad-boundary
sanitizer findings remain findings. No sanitizer/SDK-error finding appears in
the ordinary exercised paths; that statement does not cover all 65 processes.

Ordinary completion requires equal pre/post owned guest pages and objects,
guest exit metadata, closed guest handles, freed scratch, real unload/destruction
and App shutdown, `runtime_loaded_after == false`, and zero SDK errors including
teardown. This is bounded owned-resource evidence, not proof of global leak
freedom. No other lane's process, files, ports, profiles or SDK is changed.

Wrong-result controls flip one serialized observation byte and require exactly
`0:output-extent/endian/canary`; they do not modify the SDK result. Incomplete
controls finish cleanup and print READY but omit COMPLETE, so no completion can
be accepted. Deadline controls print a plausible full completion then remain
alive for 30 seconds; the owned eight-second subprocess timeout rejects them
(`-999`) despite those bytes. The public suite also tests duplicate/stale/missing
records, wrong types/exports, module path/hash mismatches, register/canary/flag
mutations, output overlap, and rejected SDK receipts before output/build.

Instrumentation is host-only undefined-behavior trap on Windows, host-only
ASan/UBSan on Linux, and host plus the selected participating SDK core on Linux.
`vptr` is excluded. Host-only instrumentation cannot certify an uninstrumented
SDK; native third-party coverage remains limited. Windows core/SDK ASan and
independent Linux hardware are not supplied by this audit. Windows and WSL
Ubuntu 24.04 run on the same machine; WSL is not an independent hardware result.

Private run roots under `gpu-display-051` and sealed manifest SHA-256:

- windows-native: `9d3e7da522314f2694dea5b70c93e298`, manifest `6b098f70ef770f8adf214d44a83529481fd1bea053005f466881a77aea3e4c72`.
- windows-host-ubsan: `c13049a750534ba1ab1b329f28c40df5`, manifest `49755ef5cc9969d4e1044130cd5d1b39ede0e7bd3e05444a3ace7fc47b2dfbe4`.
- linux-native: `bf50ef06a37f444fabb6a937bc5d89bd`, manifest `c9147d881e413ece7b7a089db823fec3fd4d75676cc9e620f89cb5818b847c4f`.
- linux-host-asan: `ecfb02db5a8345a9927702e8f807c464`, manifest `c48415f654830cd77e4dee6e437d9918685f864df9062468c1c01e7a12455cc2`.
- linux-core-asan: `a29448ecf5624db3a3fe6af3d62428a1`, manifest `e0dd21ec5b25b052fb83bbeb1959733253a8a5fe28d6036b7289bd05b372da61`.

Callback executable identities, in the same profile order:

- windows-native: `75b0786cc583536b3087ac838f3c98ea8003733d9aeda8c7f50d9fc699537bae`.
- windows-host-ubsan: `5da3309ee93cda5a922644dd2e3786afdb8304a7a61d06b3b3efa8612f920034`.
- linux-native: `45a9de6383bd710f39e196dd4fdaeeaa2b0cc3dced0dba3aa71270b491f16943`.
- linux-host-asan: `eea26c026931506c2eae5c106f2f79987029e6d73c79d42a0cf1ac30f098f120`.
- linux-core-asan: `3781bc94a640c2a013e22cb5170335dca8aa74b0379df093e5d71bdf65710ac4`.

Actual kernel/base module identities and prepared package tree digests:

- windows-native: kernel `2ac5f027dc4a0975d1dfc51440c282448057a02daa9fd3367b9d46b4a82a27f1`, base `3149476e16d580859e8a953df2890e7cd3cf5e225dc37402ccf57817eca46faa`; SDK tree `0cc9067e87990c70dd508fa45b95cda938828dda5dc82c85cd44314da71f6189`.
- windows-host-ubsan: kernel `2ac5f027dc4a0975d1dfc51440c282448057a02daa9fd3367b9d46b4a82a27f1`, base `3149476e16d580859e8a953df2890e7cd3cf5e225dc37402ccf57817eca46faa`; SDK tree `0cc9067e87990c70dd508fa45b95cda938828dda5dc82c85cd44314da71f6189`.
- linux-native: kernel `006fa034d23dfc6837f4e3e05c5113ddce3478affac5a735418fb821a90b6cb9`, base `83e249a8d25fb605168876e0fc68bf10bb978425084c314962292dfcb49f1c4f`; SDK tree `69078f33e742ed26ce99b36bce3e0c2132a599889b8f2e49da89c12534094c36`.
- linux-host-asan: kernel `006fa034d23dfc6837f4e3e05c5113ddce3478affac5a735418fb821a90b6cb9`, base `83e249a8d25fb605168876e0fc68bf10bb978425084c314962292dfcb49f1c4f`; SDK tree `69078f33e742ed26ce99b36bce3e0c2132a599889b8f2e49da89c12534094c36`.
- linux-core-asan: kernel `36153ce9115cc8071b268bb0012c2f72720e9df41e287b4b877a43ade315f942`, base `a9b7ecb6e2d453f353d32a08ae906a92676a8bdcd7c94d6c5e78997702ee7457`; SDK tree `981e1511394375b20fec9d207f92d52ab5d2a62a053603c3e9adc9545aba8430`.

Full receipts additionally retain compiler/tool hashes and versions, complete
configure/build/run commands, compile-command SHA-256, helper/source/declaration
snapshots, each input plan and log digest, process codes and artifact size/hash
maps. The re-read checked all 341 retained artifact entries. Manifest hashes are
recorded separately because each manifest's artifact map precedes its own write.
The Windows compiler is Clang 20.1.2 (archive SHA-256
`8e771a685cd718303ea0d632a8a95ad7b3cb17068f3952fbefa64a77290324d8`,
installed file-set digest `300ca7cd9b2d224ef1e57b70fa3351166047bb313de6b49ae2fbc7becbaef3d7`),
MSVC host toolset 14.44.35207, CMake 3.31.6-msvc6 and Ninja 1.12.1.
Linux uses Ubuntu Clang 20.1.2 (binary SHA-256
`b15e7640bf3082f36ef14321711706b265df3058721e3c2caef3a4b83895d07d`),
GCC 13 headers/libraries, CMake 3.28.3 and Ninja 1.11.1. Both callbacks use
Release `-O2 -DNDEBUG`, `-march=x86-64-v2`; instrumentation is explicitly recorded.

## Bounded timing evidence

Only the first three independent ordinary processes contribute timing below.
There are 32 calls per service per process, hence 96 pooled samples per service
and profile. Order is mode, display information, gamma, flags. Each entry is
median / nearest-rank p95 / maximum, **nanoseconds**, around the actual export
wrapper call. Scratch fill, canary scanning and serialization occur outside
that interval. The interval includes steady-clock overhead and indirect dispatch,
not complete guest scheduling, rendering or frame latency.

| Profile | Mode | Display information | Gamma | Flags |
| --- | --- | --- | --- | --- |
| windows-native | 100/200/300 | 100/100/2000 | 100/100/300 | 100/100/300 |
| windows-host-ubsan | 100/100/400 | 100/100/1400 | 100/100/200 | 100/100/200 |
| linux-native | 105/335/557 | 114/323/690 | 93/244/488 | 118/455/1286 |
| linux-host-asan | 446.5/801/1322 | 476.5/803/1325 | 313.5/668/1120 | 492/666/680 |
| linux-core-asan | 851/1998/5566 | 1014.5/1747/2683 | 764/2687/17809 | 710.5/1249/2503 |

Startup through `App.Init`, real runtime load, scratch/thread construction and
guest launch return, followed by real runtime unload/destruction and App shutdown:
three per-process values in **milliseconds**, without pooling query samples:

| Profile | Startup to launch return (ms) | Teardown (ms) |
| --- | --- | --- |
| windows-native | 16.515, 15.585, 15.943 | 3.659, 3.662, 3.677 |
| windows-host-ubsan | 14.951, 14.908, 14.676 | 3.465, 3.570, 3.526 |
| linux-native | 8.912, 6.445, 5.178 | 1.448, 1.144, 1.149 |
| linux-host-asan | 15.038, 9.878, 9.437 | 2.234, 2.125, 2.221 |
| linux-core-asan | 16.590, 17.404, 18.244 | 3.588, 3.382, 3.132 |

Windows has 100-ns quantization here: 135/153 of 384 query intervals are zero
in the native/host-trap runs, respectively. Zero does not mean free work.
Cache state is uncontrolled; repeated callbacks, timer overhead, WSL scheduling,
instrumentation and the different collection dates prevent a platform/framework
ranking. Samples within one process are correlated; pooled percentiles are
descriptive, not independent confidence estimates. Original receipts retain
every interval and process-level medians. No MW3 performance score is assigned:
correctness beyond this default policy, stability, maintainability, integration
effort and hardware compatibility remain insufficient for the project's
30/25/20/15/10 weighted architecture decision. No renderer is called fastest.

## Adjacent controls: source evidence only

At the exact implementation hash above, `VdSetDisplayMode_entry` ignores its
flags and returns 0; `VdSetDisplayModeOverride_entry` ignores its arguments and
returns 0; `VdInitializeEngines_entry` ignores setup and returns 1 without
starting engines; `VdShutdownEngines_entry` is empty. Other listed display
exports include explicit `REX_EXPORT_STUB` entries. This is source classification,
not an execution/compatibility result for those controls. No such call is
admitted, substituted into startup, or represented as functioning graphics.

## Reproduction and checks

Use an already verified lifecycle-repaired XMA preparation, not the memory-only
GPU or input-profile packages. Set `WROOT` to the private Windows runtime cache,
`LROOT` to its Linux counterpart and `OUT` to a private audit-only output root.
Each invocation allocates a fresh UUID and per-process configuration/profile.
Original sources and user-owned installations remain read-only.

```text
python tools/test_gpu_display.py --root WROOT --sdk-report WROOT/xma-preparations/5630f18f4eae43e68f61d7a4025e5862/manifest.json --output-root OUT
python tools/test_gpu_display.py --root WROOT --sdk-report WROOT/xma-preparations/5630f18f4eae43e68f61d7a4025e5862/manifest.json --output-root OUT --sanitizers
python3 tools/test_gpu_display.py --root LROOT --sdk-report LROOT/xma-preparations/720f4ff41cab492485af32e5166fa753/manifest.json --output-root OUT
python3 tools/test_gpu_display.py --root LROOT --sdk-report LROOT/xma-preparations/720f4ff41cab492485af32e5166fa753/manifest.json --output-root OUT --sanitizers
python3 tools/test_gpu_display.py --root LROOT --sdk-report LROOT/xma-preparations/841dee25fe7d45fca75cf68f7bdf49fd/manifest.json --output-root OUT --sanitizers
```

All five investigations finish with exit **1**, `status: INCONCLUSIVE`,
`investigation_complete: true`, `declared_default_policy_passed: true`. Exit 1
must not be relabeled exit 0/PASS. Exit 2 denotes an incomplete/error investigation.
Prior development attempts/logs are retained separately and excluded from final
counts; neither an old partial attempt nor a mock is called a final SDK result.

Fresh public checks on November 22:

```text
python tools/project.py list --ready
python tools/project.py prompt MW3-051
python tools/check.py --config Release
python3 tools/check.py --config Release --sanitizers
git diff --check
```

Windows Release: 277 Python tests with eight existing skips and parser CTest
1/1. Linux Release ASan/UBSan: 277 Python tests with two Windows-junction skips
and parser CTest 1/1. All twelve new public synthetic evidence guards pass on
both platforms. The 62-task dependency graph, artifact heuristic and diff check
pass. Hosted final-head Windows/Linux Debug/Release and sanitizer results are
recorded in the pull request; private SDK executions are local evidence only.

No console-reference capture, alternate-mode injection, graphics debug-layer run,
GPU command processing, shader output, actual display presentation, real-title
adoption or gameplay is provided. Follow-up repairs require separate scopes;
this completed bounded investigation leaves those gates open. Review includes
manual provenance and license/scope checks in addition to the repository's
heuristic artifact scan. No independent review or distribution clearance is
implied by the scan or public repository visibility.
