# Controlled native lifecycle integration

MW3-041 completes bounded lifecycle acceptance on 2026-11-19 after its
discovered blockers were repaired. Parent gate 010 requires its own review.
The integration checkpoint admits the audited
RtlImageXexHeaderField service, then stops at the next guarded import.
The owned Campaign and Multiplayer modules are regenerated privately against
the verified stop-repair SDK and rebuilt with the conservative guest policy.

The host records the diagnostic stop, waits for the runtime's title-exit
notification, checks the stopped guest thread's exit metadata, unloads and
destroys the title runtime, checks the former reservation is available, and
shuts down the app. It also compares SDK host-thread counts before and after.

The initial matrix runs three ordinary startup processes and separate invalid
binding, malformed-pointer, incorrect-oracle and interruption cases for each
executable. Each process owns its profile and temporary files. Interruption
uses a host gate at the audited header query and requests exit 88 while the
guest is waiting. Rejected cases must complete teardown as well as report the
specific failure. A watchdog termination cannot substitute for that evidence.

The standalone driver is `tools/verify_kernel_gate.py`. It checks all required
child task states and verifies the owned executable pair, SDK receipt, recipe,
analysis metadata and generated payload. The import wrappers still verify
every mapped function binding. The additional wrapper changes diagnostic
termination from process exit to guest-thread unwind.

```text
python tools/verify_kernel_gate.py --root PRIVATE_RUNTIME_CACHE --sdk-report NATIVE_XMA_RECEIPT --sdk-profile xma --owned OWNED_EXECUTABLE_PAIR --metadata VERIFIED_METADATA --output-root PRIVATE_OUTPUT --role sp
```

Repeat for `mp`. A generation receipt can be consumed with `--generation` and
`--expected-generation-sha256` after complete payload verification. Windows
requires this independent generation receipt. `--sanitizers` instruments the
maintained host code, while generated guest objects use their established
wraparound and exact floating-point compile policy.

The first full-span Linux Campaign native run passed all seven cases, including
reclaiming the entire 4.5 GiB former mapping span and recovering SDK thread
counts from zero to zero. Each attempt retains its own executable and source
snapshots; a serialized build cache cannot overwrite executed evidence.

The first host-ASan/UBSan run failed six cases after title launch; only the
pre-launch binding rejection passed. LeakSanitizer reported **41,991,680 bytes
in 1,280 allocations**, originating in the 320 XMA contexts created at launch.
A second run with slow allocation unwinding resolves the allocation stacks
through `XMAContext::Setup`, `XMADecoder::Setup` and the APU/title launch path.
The context destructor frees its codec and frame but omits its allocated
packet and packet buffer. All ordinary teardown markers still appear; the
driver correctly rejects these processes because they leak. Baseline failures
are retained privately and must not become passing evidence by suppressing
leak detection. MW3-044 scoped the SDK repair separately.

The repair is merged in [PR 70](https://github.com/JaBoyAlex/mw3-recompiled/pull/70).
Its [evidence](../engine/xma-lifecycle.md) passes all 56 controlled SP/MP cases
on native Windows/Linux and supported host sanitizers, plus 20 focused
game-free lifecycle cases across five profiles. Post-audit checks all loaded
kernel hashes and confirms the repaired Campaign comparison retained the
original game identity, generation, host source and compiler. The former blocker
is resolved. The acceptance reconciliation below completes 041; parent 010 and
product gates remain open.

First-frame 011 also requires complete content preparation (045) and allocation
import ABI contracts (046). These disjoint foundation tasks can run beside the
lead's lifecycle acceptance. Their specifications implement no feature and pass
no gate. First-frame remains an epic to split before implementation claims.
Gameplay, original split-screen, four-player Survival, networking and renderer
modernization retain their established criteria.

## Acceptance reconciliation

| Required child | Accepted evidence and boundary |
| --- | --- |
| 036 — header service | [Independent oracle and raw-header/module-cell checks](../engine/startup-imports.md); only the reviewed query calls its real SDK implementation. |
| 037/042 — memory | [300 repaired-profile cases across five profiles](../engine/memory.md), with original decommit failures retained; direct memory semantics do not establish the next guest import ABI. |
| 038 — CPU | [2,410 selected synthetic cases per run across six runs](../engine/ppc-validation.md), reproduced generation/held-out seeds and deliberate-result rejection; full ISA/console equivalence is unverified. |
| 039/043 — threads | [Scoped thread acceptance](../engine/threads.md) covers actual kernel/XAM boundaries, TLS/r13, guards, waits, interlocked interfaces and cancellation, with repaired exit preservation; reservation instructions/fibers/APCs/race freedom remain outside that acceptance. |
| 040 — native Windows | [Owned Windows startup and calibrated host UBSan](../engine/windows-bringup.md); current lifecycle coverage extends its earlier abrupt-stop experiment. |
| 044 — audio-pool cleanup | [20 focused and 56 owned-title processes](../engine/xma-lifecycle.md) pass with the packet repair, including actual Linux core instrumentation in the focused suite; original leaks remain retained. |

All child task states are complete. The packet-only derivative preserves the
tested parent's public headers, CPU libraries and unrelated package files.
The affected title launch/teardown path was executed again on both platforms;
unchanged child experiments are referenced by exact receipts rather than
relabelled as new runs.

## Exact checkpoint identity and coverage

The owned pair is bound by
[`mw3-xbox360-rev1.json`](../../config/titles/mw3-xbox360-rev1.json), with no
inferred title update. The independent private generation receipt is
`a69cab32b2cd4172890fdc2cf83b317f/generation.json`, SHA-256
`eacf6eed533a3e5a88dae07a68f6080fdd3be9d92bf5e9a8b4104eaf6d1ac52b`.
Its payload is fully rehashed before and after use; all 326 C++/header files
match the earlier verified generation. Generated code is not edited. The
conservative recipe and actual guest compile commands retain register/context
policy, wraparound and exact floating-point flags without guest sanitizers.

The selected runtime is `xma-packet-v1`, based on ReXGlue commit
`ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d` plus the reviewed platform,
reservation, decommit, cooperative-stop and packet patches. Exact native/core
SDK receipt, compiler, source-composition, binary and loaded-kernel hashes are
in [the evidence index](../../config/toolchains/rexglue-xma/validation.json).
No validation-only SDK is silently substituted into a native title run.

| Image | Verified function bindings | Admitted function | Reviewed guest data |
| --- | ---: | --- | --- |
| Campaign | 258 | RtlImageXexHeaderField | Executable-module handle cell → loader entry → raw header |
| Multiplayer | 262 | RtlImageXexHeaderField | Executable-module handle cell → loader entry → raw header |

All other function imports retain diagnostic wrappers, not successful stubs.
Both title flows make the reviewed query and reach guarded
NtAllocateVirtualMemory. Four additional present-field queries are host audit
calls using copied contexts, not original title behavior. The other twelve
data-variable imports per image remain unaudited; this checkpoint grants no
approval to use them or to advance into later services without review.

## Execution and resource results

Eight owned profiles (SP/MP × Windows/Linux × native/host sanitizer) each pass
three ordinary starts and binding/pointer/oracle/interruption cases: 56 PASS.
Diagnostic exits are 86 for the next-import stop, 87 for the expected guard
failure and 88 for requested interruption. Rejections must have the exact
failure reason and complete cleanup; wrong exit, crash, timeout, missing
metadata, duplicate completion or a sanitizer report cannot pass.

The host waits for title exit, inspects retained actual guest-thread termination
metadata, releases the pin/provider, unloads/destroys the runtime, reclaims the
entire former 4.5 GiB reservation without replacing any mapping, and shuts down
the app with SDK host-thread counts recovered. Linux host ASan/UBSan reports no
leak in the repaired runs. The independent post-audit verifies every retained
log/source/binary hash and the loaded kernel reported by all 76 focused/title
processes. Each owned attempt retains its own executed package.

Owned repeats are isolated processes. Four same-process audio-pool lifetimes
are tested by the game-free launch-error fixture; successful owned hot reload
in one process is NOT RUN. SDK thread counts do not measure every possible OS
handle. Windows uses native libraries and calibrated host UBSan traps; core
ASan is unsupported. Linux core coverage here is the separate focused suite,
with native XAM and vptr instrumentation disabled. Generated guest code,
graphics, playback, subsequent imports and full kernel/ISA parity are unverified.

The maintained result/trap guards and public Windows Release/Linux Release
ASan/UBSan checks pass; exact commands, public counts/skips and private receipt
hashes remain in the linked evidence. Reproduction requires legally obtained
inputs and trusted reviewed local source. Documentation/catalog-only acceptance
changes need no new title execution when audited implementation hashes remain
identical.

Self-review reconciled every child, exact input/SDK/host identity, positive and
negative cases, actual loaded libraries and stated coverage gaps. No independent
reviewer is claimed. This completes the bounded task, with no first-frame,
playable-boot, original-mode, split-screen, networking or release acceptance.
