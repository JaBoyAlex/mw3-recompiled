# Selected SDK decommit repair

Original changes in `decommit.patch` are BSD-3-Clause, copyright (c) 2026,
mw3-recompiled contributors. The modified file retains its Copyright 2020
Ben Vanik notice and Tom Clay's adaptation notice. Conditions and disclaimer
are preserved in [the upstream license](../../../experiments/runtime-bakeoff/patches/LICENSE.rexglue).
No GPL implementation was copied into the SDK patch; public preparation/test
tools remain GPL-3.0-only. This grants no game or SDK distribution clearance.

The patch checks commitment in access queries, revokes host access on decommit,
validates complete ranges before mutation and rounds both ends of partial-page
requests. Physical parent/alias requests cover identical guest pages. Released
physical mappings retain the existing configurable access policy; reserved,
decommitted pages cannot be revived by the stale-protection fault recovery.

The preparation driver composes this exact patch with the separately reviewed
host-range/output-directory patch and, on Windows, API typing patch. A fresh
source/build/package identity preserves all earlier baseline artifacts. This
is private research integration, not a redistributable SDK.
