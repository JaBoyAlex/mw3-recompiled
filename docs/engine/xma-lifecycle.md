# XMA context lifetime investigation

MW3-044 is complete for this bounded ownership repair. The MW3-041 Campaign
host-ASan/UBSan attempt retained
at `0b884cdd81ab4bf28972509dd89c17eb` fails six post-launch cases. The
pre-launch binding rejection passes. A separate slow-unwind reproduction
`47ae1efd96ee4e12bbb0a63ef859493a` resolves the allocation chain:

`TitleRuntime::Launch` → title system attachment → `APU::Setup` →
`XMADecoder::Setup` → `XMAContext::Setup` → FFmpeg packet/buffer allocation.

The leak is 41,991,680 bytes in 1,280 allocations: 320 packet objects, 320
128 KiB buffers and their reference bookkeeping. The decoder owns an array
of 320 contexts. Its worker is stopped/joined before context destruction.
Each context destructor frees its codec and frame but omits its packet.
The packet destructor releases its reference-counted buffer and packet
allocation, and accepts a null pointer. During decode, packet data points
at a separate context-owned frame array. FFmpeg's packet unref releases
`buf` and resets the packet; it does not free that external frame array.
Codec destruction precedes packet destruction to release retained references.

The [original patch and explicit profile](../../config/toolchains/rexglue-xma/README.md)
add that missing ownership release. Allocation/decoding algorithms remain
unchanged. There is no measured gameplay or frame-time improvement; the
expected benefit is recovering the demonstrated per-pool shutdown leak.
Private evidence and baseline failures remain retained. Supported sanitizer
and platform matrices pass as recorded below. Allocation-failure
injection, real audio decoding and playback remain outside this repair.

## Validation — 2026-11-19

| Profile | Game-free lifecycle | Owned Campaign | Owned Multiplayer |
| --- | --- | --- | --- |
| Linux native | 4 PASS | 7 PASS | 7 PASS |
| Linux host ASan/UBSan | 4 PASS | 7 PASS | 7 PASS |
| Linux instrumented core + host ASan/UBSan | 4 PASS | NOT RUN | NOT RUN |
| Windows native | 4 PASS | 7 PASS | 7 PASS |
| Windows host UBSan traps | 4 PASS | 7 PASS | 7 PASS |

The matrix passes 20 original game-free processes and 56 owned-title processes.
Each title profile runs three ordinary checkpoints plus bad binding, malformed
pointer, wrong oracle and controlled interruption. Every case checks teardown;
the title cases also reclaim the entire former 4.5 GiB mapping and inspect the
actual stopped guest-thread metadata. SDK host-thread counts recover. This is
bounded startup, not playable boot. The first unreviewed memory import remains
guarded; no new guest service is admitted by this repair.

The original two leaking synthetic cases remain FAIL. Unlaunched controls pass;
one pool leaks 41,991,680 bytes and four pools leak 167,966,720 bytes. The earlier
owned Campaign sanitizer attempt also retains its six failures. Post-audit
confirms the repaired Campaign comparison uses identical owned identities,
generated payload, maintained host source and compiler, with the exact original
SDK as the repair's parent. Leak detection remains enabled. Seven actual receipt,
composition and package mutations are rejected without changing that parent.

The independent post-audit rehashes retained logs, source, executed binaries and
SDK packages, and checks the kernel library actually reported loaded by all 76
processes. Guest compilation retains wraparound and exact floating-point flags,
without guest sanitizer instrumentation. Every owned attempt retains a separate
executed package, so later cache rebuilds cannot replace its binary evidence.

Exact receipts, binary/kernel identities and public-check results are in the
[game-free evidence index](../../config/toolchains/rexglue-xma/validation.json).
Commands and supported instrumentation are in the
[profile instructions](../../config/toolchains/rexglue-xma/README.md).
Public Windows Release and Linux Release ASan/UBSan checks pass. Four Python
guard tests cover leak/incomplete-cleanup rejection, distinct repeated cycles,
changed patch/parent composition and stale preparation receipts.

Self-review checked packet/buffer ownership, destruction order, the retained
baseline controls, unchanged parent artifacts and unrelated package files,
compiler/profile selection, failure cleanup, immutable execution and reported
library identities. No independent reviewer was available. The initial harness
compile used an incorrect requirements type; its failed attempt is retained.
A Windows test fixture's implicit CRLF was corrected to explicit LF. Neither
change affected the SDK repair.

No measured gameplay/frame-time improvement is claimed. Allocation-failure
injection, decoding/playback correctness, full kernel/ISA parity and all product
gates remain separate. Windows core ASan, Linux XAM instrumentation and guest
sanitizers retain the limitations recorded in the evidence index.
