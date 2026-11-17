---
name: mw3-evidence
description: Inspect owned MW3 inputs or document engine behavior with exact build identity and reproducible reverse-engineering evidence.
---

Use docs/BUILDING.md and docs/research/title-identity.md for input layout. Inspect explicit owner-supplied paths with tools/inventory.py and tools/disc.py. Originals are read-only. Reports/extracted executables belong under ignored private storage. Do not commit game bytes, generated/decompiled game code or keys.

Before assigning an address or structure, bind observations to exact executable SHA-256, entry/module identity and analysis tool version. Preserve raw evidence privately; maintain public address/behavior notes only where provenance permits. Verify important claims through a second reader or independent observation. MW2 names/addresses are hypotheses until checked against MW3.

Distinguish observed facts, upstream reports, inference and unknowns. Check whether the analysis provider actually supports XEX, big-endian PPC and relevant VMX128 behavior; tool branding is not proof. Stop a proposed fix when its input identity contradicts the evidence and update the task's blocker.

Test the negative case and record reproducible commands and limitations. A decompiler output or function count alone does not prove semantic accuracy or gameplay completeness.
