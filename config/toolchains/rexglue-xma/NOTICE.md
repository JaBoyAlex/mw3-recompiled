# Selected SDK packet ownership repair

The original change in `packet.patch` is BSD-3-Clause, copyright (c) 2026,
mw3-recompiled contributors. Modified code retains the upstream Ben Vanik and
Tom Clay notices. Conditions and disclaimer remain in the
[upstream license](../../../experiments/runtime-bakeoff/patches/LICENSE.rexglue).
No GPL implementation was copied into this SDK patch. Maintained preparation
and test tools remain GPL-3.0-only. Game-linked distribution clearance remains
separate.

The patch releases the context-owned FFmpeg packet after codec/frame cleanup.
FFmpeg's null-safe packet destructor also releases its buffer reference; it
does not free the context's separate frame array used as packet data. The
codec is destroyed first so its retained packet references have been released.
There is no change to allocation, packet preparation or decoding behavior.
