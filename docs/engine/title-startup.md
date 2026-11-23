# Bounded post-allocation startup — MW3-093

This checkpoint returns from the reviewed first reservation, admits one
independently audited commit using the existing selected kernel, checks the
title's following heap initialization and stops before the next service.
It does not establish a rendered frame, menu, playable mode or general heap ABI.
Acceptance verification is in progress; MW3-093 remains unfinished until the
supported matrix and artifact review below are recorded.

## Identity and source review

Use MW3 **2011**, Xbox 360 USA/Korea Rev 1, the unchanged owner-supplied
[SP/MP identities](../../config/titles/mw3-xbox360-rev1.json), the MW3-091
memory-imports preparation, and the MW3-041 generation receipt
`eacf6eed533a3e5a88dae07a68f6080fdd3be9d92bf5e9a8b4104eaf6d1ac52b`.
The [startup contract](../../config/runtime/title-startup.json) binds each
role's original-source window, LLVM disassembly, owned data word, executable,
metadata and private precall capture. Its digest must be explicitly supplied.
The earlier [first-allocation contract](title-allocation.md) stays separate.

The private source audit observes the original loaded XEX before import
normalization, verifies the observed words remain identical afterward, decodes
direct branches independently, and reads the same window with LLVM MC 18.1.3.
The full enclosing-function window and its one accessed owned data word remain
private. SP and MP have separate addresses and signed data displacements;
no MW2 guest address or inferred retail symbol is used.

| Boundary | SP LR | MP LR |
| --- | --- | --- |
| Reviewed first reservation | `824652e4` | `824e6f64` |
| Following commit | `82465334` | `824e6fb4` |
| Next `KeGetCurrentProcessType`, not invoked | `82465438` | `824e70b8` |

Both native Windows precall captures observed a 64 KiB commit inside the
1 MiB reservation, type `60001000`, protection 4 and region 0. In/out words
are at the same audited frame plus 84/332. The original title path accesses
the audited stack, allocated heap and one zero-valued owned data flag before
the next service. No new imported data variable is enabled.

The initially attempted source audit rejected an incorrect assumption that
MP used SP's data displacement. Deriving and independently checking each
role's original signed load resolved it: SP −13112, MP −14072. The failed
attempt is retained privately and is excluded from accepted evidence.

## Runtime and evidence contract

`--checkpoint startup-inspect` executes the already accepted first reserve,
returns to title code, records the second request and stops **before commit**.
`--checkpoint startup` additionally admits that one exact request and returns
to the audited heap initialization. Header remains the default checkpoint;
`allocation-inspect` and `allocation` preserve the preceding stop behaviors.

The guarded host checks caller, frame, context, aligned mapped read/write
big-endian in/out words, captured values and a two-allocation-call budget.
The original dynamically resolved kernel export must differ from the local
trap. Every other function remains a diagnostic trap. The commit oracle checks
status/output, original allocation extent, committed region/edges, read/write
access, reserve-only inaccessible tail, title-page accounting, fresh zero fill,
neighbouring bytes and unchanged header/module/owned-data bindings before
returning. Host checks do not initialize the title heap.

At the next service the read-only oracle checks the title-written heap markers,
flags, halfwords and eight-node links, exact caller and unchanged frame/global.
The next kernel service is never called. Wrong callers, pointers and values are
rejected before commit; result/heap oracle controls require a valid real-call
baseline. Incomplete evidence follows orderly teardown but omits the footer.
The late control reaches the real heap baseline and is killed at five seconds;
it is not claimed to recover its mapping or threads. Normal probes have a
30-second outer deadline and an eight-second title-exit deadline. Build workers
are capped at two, and heavy runs are serialized.

The parser requires per-process nonces, exact event order/multiplicity, the
actual call and result, complete recovery, and matching loaded kernel hashes.
Missing, stale, reordered, duplicated, late or sanitizer/crash evidence fails.
Input/generation/SDK/source/config/package identities are checked before and
after execution. Retained artifacts are separately reviewed before acceptance.

## Reproduction

Use the private owned input and verified preparation paths for each host; never
place game inputs, generated code, dumps or traces in Git. For example:

```text
python tools/verify_kernel_gate.py --root PRIVATE_CACHE --sdk-report MEMORY_IMPORTS_RECEIPT --sdk-profile memory-imports --owned OWNED_REV1 --metadata PRIVATE_ANALYSIS --generation GENERATION_RECEIPT --expected-generation-sha256 eacf6eed533a3e5a88dae07a68f6080fdd3be9d92bf5e9a8b4104eaf6d1ac52b --expected-allocation-contract-sha256 d7339f9a99a4d357faf1893a266213030807363dcc727604d95c7e87c1f49be7 --expected-startup-contract-sha256 STARTUP_CONTRACT_DIGEST --role sp --checkpoint startup --output-root PRIVATE_LANE_OUTPUT
```

Run separately with `--role mp`, `--checkpoint startup-inspect`, `header` and
`allocation`. `--sanitizers` instruments maintained host code on supported
profiles; the Linux participating-kernel profile uses its separately prepared
sanitized SDK. Public checks are `python tools/check.py --config Release` on
Windows and `python3 tools/check.py --config Release --sanitizers` on Linux.

## Limits and review

This remains a private headless startup probe with graphics/audio/input disabled.
It uses the minimal two-XEX input directory. Prepared full game content is
available separately but has not been loaded by this checkpoint. Original
Campaign, MP, Spec Ops, Survival and split-screen parity remain unverified.
The first-frame epic stays unfinished. No gameplay performance or calendar
delivery estimate follows from this milestone.

The integration reuses the selected SDK; it adds bounded diagnostic validation,
not a replacement allocator or renderer. Probe zero-fill and identity scans
have diagnostic overhead, with no claim about gameplay performance. Windows
kernel sanitizer support remains unavailable; Linux/WSL is the same physical
machine. Generated guest code and retained native dependencies are outside
parts of instrumentation. Review is self-review; no independent reviewer or
second-machine validation is claimed.
