# XMA context lifetime investigation

MW3-044 is in progress. The MW3-041 Campaign host-ASan/UBSan attempt retained
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
and platform matrices must pass before task acceptance. Allocation-failure
injection, real audio decoding and playback remain outside this repair.
