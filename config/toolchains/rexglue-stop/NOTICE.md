# Selected SDK stop-boundary repair

Original changes in `stop.patch` are BSD-3-Clause, copyright (c) 2026,
mw3-recompiled contributors. Modified files retain upstream Ben Vanik and/or
Tom Clay notices. Conditions and disclaimer remain in the
[upstream license](../../../experiments/runtime-bakeoff/patches/LICENSE.rexglue).
No GPL implementation was copied into this SDK patch. Maintained preparation
and test tools remain GPL-3.0-only. This grants no game/SDK distribution clearance.

The patch distinguishes a cooperative stop from an explicit exit without
changing the existing ThreadStop payload/layout. Pending import/hook/spin stops
carry a derived tag; the kernel entry resolves the owning thread's recorded
exit. Fiber forwarding preserves a pending request instead of overwriting it
with the tag's default payload. Explicit exits retain their existing handling.

The exact patch composes with the reviewed decommit/reservation repairs and
Windows API typing repair. Baseline source, SDKs and evidence stay unchanged.
