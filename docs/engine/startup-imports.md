# Audited header-query startup checkpoint — 2026-11-17

**Private Linux/WSL translated startup admits one reviewed read-only service,
then stops at NtAllocateVirtualMemory. Not playable. Native Windows title
execution and orderly title teardown remain unverified.** Exact input identity
is [Rev 1](../../config/titles/mw3-xbox360-rev1.json); no title-update identity
is inferred. All generated/native artifacts and raw logs stay private.

## Service and data boundary

The maintained [probe](../../tools/runtime_probe.py) verifies the complete
private generation cache, current SDK/source/patch/recipe identities and exact
[analysis hashes](../../runtime/bringup/analysis-lock.json). Every one of the
258 SP / 262 MP function bindings must point at its expected host wrapper before
launch. Only RtlImageXexHeaderField calls its real SDK implementation. Every
other imported function remains an exit-86 diagnostic stop. No successful
placeholder is introduced; title functions and their addresses are not patched.

The original bounded C++ oracle in `src/xex.cpp` reads the complete raw header.
It distinguishes absent and present-zero fields, immediate values, inline value
addresses and fixed/variable payload pointers. It rejects duplicate keys,
truncated spans/payloads, misalignment and 32-bit address wrap. Synthetic tests
use original fixtures and explicit expected values; no SDK code is copied.

Before entering the title, the probe checks the XexExecutableModuleHandle
import slot against xboxkrnl ordinal 0x0193's allocated cell, its value against
the actual executable module's loader entry, and that entry's header pointer
against the loaded module object. Checked guest-memory reads guard each access.
The 20,480-byte loaded header must match the owner's raw file byte-for-byte;
it is checked again before and after the admitted service. The other **12 data
variables remain semantically unaudited**. This review does not approve the
runtime's whole export table or its compatibility/version placeholders.

Reviewed pinned SDK references at `ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d`:
`src/kernel/xboxkrnl/xboxkrnl_module.cpp` allocates the cell;
`src/kernel/process.cpp` initializes it to the executable's loader entry;
`src/kernel/user_module.cpp` copies the raw header and resolves optional fields;
`src/kernel/xboxkrnl/xboxkrnl_rtl.cpp` implements the query. These are source
observations, combined with the actual module/cell/header checks above, not a
claim of complete console kernel parity. The original SDK and Linux memory
derivative remain [hash-bound](../adr/0002-runtime-selection.md).

## Actual title observations

| Observation | SP | MP |
| --- | --- | --- |
| Header query return LR | `0x82462e8c` | `0x824e4b2c` |
| Requested key | `0x00020401`, default-heap field | Same |
| Owned field present | No, among 17 optional entries | No, among 18 |
| Independently predicted and real SDK result | Zero (missing field) | Zero (missing field) |
| Next guarded function | NtAllocateVirtualMemory | NtAllocateVirtualMemory |
| Next stop LR | `0x824652e4` | `0x824e6f64` |

These are observed return sites, not reusable guest hook addresses. The
canonical independent instruction scan confirms each original call at LR−4
targets the respective resolved import. Returning zero here is the real
missing-field result, not an allocator success or an invented stub.

To cover more than that missing-field path, the first guest-thread callback
also performs four **host-initiated read-only audit calls** using copied PPC
contexts: entry-point immediate, image-base inline value, execution-info fixed
payload and import-libraries variable payload. All four keys are present and
produce nonzero predicted results matching the real SDK. These four audit
queries are instrumentation, not calls observed in the original game flow.
Guest arguments are preserved for its original query. A budget of 16 actual
title queries bounds the service experiment.

Final matrix: two titles × native/host-ASan-UBSan × (three independent positive
processes + wrong binding + changed pointer + incorrect oracle result) =
**24 pass**. The wrong binding makes the real verifier look up a different
import; the pointer fixture changes r3 by four before the pointer check; the
oracle mutation changes the expected result after the real SDK is called.
Each fails at its expected diagnostic and never records a successful guest
query. Positive processes reproduce the same next-service stop.

Sanitizers instrument the original host harness, traps, allocator shim and
bounded parser. Generated guest objects and the linked SDK in this matrix
remain uninstrumented. The separately instrumented SDK-core tests are different
[evidence](../../experiments/runtime-bakeoff/conformance-2026-11-17.md). Abrupt
exit 86/87 intentionally skips final leak/teardown reporting, so this matrix
does not establish leak-free title shutdown. Windows/Linux game-free parser
checks and Linux parser sanitizers are separate from Windows title execution.

## Reproduction and private evidence

Use [the build guide](../BUILDING.md#guarded-header-service-probe) with the exact
normal SDK receipt, canonical private cache entry and canonical analysis
directory. Original SP/MP builds passed three title runs and two forced guard
checks each. The strengthened matrix rebuilt only the original host code in
those private build trees, retaining the original binaries by hash, and staged
fresh binary/library/profile directories for native and sanitizer runs. Guest
objects were reused unchanged; no generated source was edited. The public
driver supports fresh native or host-sanitizer builds for reproduction.

Paths relative to `~/.cache/mw3-recompiled/kernel-bringup/`:

| Manifest | SHA-256 |
| --- | --- |
| `d09532ff604645b38a324b2da2b6ab85/manifest.json`, original SP build/checkpoint | `67ed2a98f959658f384d5b6d8aff661d37b3f329f147520c6a04c9f7bd44e312` |
| `f887b520d53f4452ae09217ce76aa649/manifest.json`, original MP build/checkpoint | `e7352b676c03b3977c5402a260af5762590c6189c1156043d0db237ab7942131` |
| `recheck-fc2ebc948a1f4b81ad0dd4170c16719c/manifest.json`, strengthened native/host-sanitizer matrix | `e8b405aaca0da4fd5db8d5cf9425654ba72edd8ccf43327bc30c5ccad683752f` |
| `recheck-fc2ebc948a1f4b81ad0dd4170c16719c/independent-call-checks.json`, four original call-site checks | `8fbfcbcd3974e1334faffd1ff1602c9268d3a382f430266dc39419b8b5c77217` |

Private receipts identify exact source/config/binary/library hashes and
commands. The second matrix's helper is private orchestration; the reusable
host/parser/driver implementation is maintained here. Self-review only; no
independent reviewer was available. No gameplay speed/latency/memory benchmark
has been measured. Header comparison and the four audit queries are diagnostic
overhead and are not a shipping optimization. Release/provenance holds remain.

Next: memory boundary/stress (037), PPC oracle (038), thread/lifecycle (039) and
native Windows bring-up (040) can proceed in their own scopes. Virtual-memory
service admission needs its own scoped audit after the relevant memory tests;
reaching its trap does not approve its flags, pointers or allocation semantics.
Kernel gate 010 and all first-frame/gameplay/network/release gates remain open.
