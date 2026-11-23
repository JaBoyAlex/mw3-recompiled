# MW2 input-code reuse

SDL enumeration/open/connection/close, named control reads, Y complement,
trigger quantization and rumble API usage are adapted from
PaulCombal/mw2-recompiled, `runtime/kernel/input.cpp`, revision
`b3aa7d8ef184de8ec1f0d2fe7fa0e19a4c92b68b` (GPL-3.0-only).
Attribution: PaulCombal and mw2-recompiled contributors.

The upstream project's own-code grant and full GPL text are recorded in the
project's root LICENSE; no game-derived source or vendor SDK is incorporated.
The exact upstream source/license hashes are recorded with this task's evidence.

Modifications for MW3: fixed sixteen source records, explicit existing ingress
owner/incarnation bindings, bounded enumeration and rumble, balanced per-object
SDL references, per-object handle ownership, single-thread/lifecycle guards,
exact-zero Y neutral, validated complete host samples and diagnostic failure
cleanup. SDL names map to original MW3 host control bits. The original global
ordinal user slots, UI/online hooks, keyboard/scripts/autopilot, guest/PPC
layouts and fallback policy are omitted. No guest address is reused.

This is a host adapter, not physical-controller, console or title certification.
