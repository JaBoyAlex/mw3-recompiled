# Bounded native kernel checkpoint — 2026-11-19

**MW3-010 passes its scoped controlled-entry/shutdown gate. Phase 2, first-frame
and all product gates remain incomplete.** This accepts real native execution
of a bounded prefix of both owned MW3 modules, supported by the reviewed memory,
CPU and thread contracts. It does not certify the complete guest kernel or ISA.

## Required evidence

| Requirement | Evidence accepted | Material limit |
| --- | --- | --- |
| Physical aliases and endian access | [Repaired memory matrix](../engine/memory.md): A/C/physical-window coherence, byte order, bounded allocation models, protection, commitment/decommitment and release; 300 passing cases across five profiles. | Synthetic callbacks/layouts, not the next guest allocation import ABI. Original decommit failures remain retained. |
| TLS/r13 and stack guards | [Thread acceptance](../engine/threads.md): actual SDK guest-thread startup/context, eight live TLS blocks, stack bounds/alignment/guards and resource accounting. | Original native callbacks; not full translated context/nonlocal behavior. |
| Atomic interfaces and waits | The same suite checks contended interlocked lists, events/semaphores/mutants, suspension, wait/cancel transitions and kernel/XAM import stops. Five profiles provide 380 ordinary case evaluations and ten deliberate negative outcomes. | Translated reservation instructions, fibers/APCs, TSan and general race freedom are unverified. |
| Selected translator behavior | [CPU oracle](../engine/ppc-validation.md): 2,410 original synthetic cases per run in six native/sanitizer/held-out runs, reproduced generation and rejected result mutations. | Selected ISA subset; no full VMX128/console-equivalence claim. |
| Fail-closed title service boundary | [Audited header query](../engine/startup-imports.md) and [lifecycle reconciliation](native-kernel.md) verify every SP/MP function binding and the actual module-handle cell/header chain. | One guest-imported function is admitted. Other functions stop diagnostically; twelve other data variables per image remain unaudited. |
| Native Windows/Linux execution and shutdown | [Merged lifecycle acceptance](native-kernel.md) and [packet-repair evidence](../engine/xma-lifecycle.md): 56 passing owned processes plus 20 focused lifecycle processes, actual loaded-kernel identities and retained artifacts. | No frame, playback, gameplay, owned same-process hot reload or universal OS-handle accounting. |

All required children 036–041 are merged and complete. The separately scoped
042 decommit, 043 cooperative-stop and 044 packet-ownership repairs are also
merged; original failures remain in their evidence rather than being relabelled
as passes. No failing or missing child is waived to pass this gate.

## First actual title checkpoint

The exact [Xbox 360 Rev 1 pair](../../config/titles/mw3-xbox360-rev1.json) is
privately generated and compiled into native Windows/Linux executables. The
326 C++/header generation files reproduce. The owned title's entry runs through
RtlImageXexHeaderField, whose missing-field result is independently verified,
and reaches guarded NtAllocateVirtualMemory. This allocator is **not admitted**
by this gate. The four present-field oracle probes are host instrumentation,
not additional original game calls.

The [041 reconciliation](native-kernel.md) binds the exact generation receipt
and recipe. The [machine-readable evidence](../../config/toolchains/rexglue-xma/validation.json)
binds native/core SDKs, source composition, compilers, executed binaries and
reported loaded kernel libraries. Runtime selection remains the reviewed
[ReXGlue private-development decision](../adr/0002-runtime-selection.md).
No game bytes, translated code, SDK packages or private traces are conveyed.

Positive cases deliberately finish with diagnostic exit 86 at the unreviewed
import; this is not successful game boot. Guard failures use 87 and controlled
interruption requests 88. The runtime's actual thread metadata preserves these
codes. The host waits for exit, unloads/destroys the title, reclaims the entire
former 4.5 GiB mapping without replacing existing mappings and shuts down with
SDK thread counts recovered. Linux host leak checks pass with the packet repair.

Three ordinary starts and binding/pointer/oracle/interruption cases run for
each SP/MP native/host-sanitizer profile on both platforms: 56 PASS. Every owned
attempt retains a separate executed package. Twenty focused processes add
same-process audio-pool cycles and actual Linux core instrumentation. Seven
receipt/composition/package mutations are rejected while original artifacts
remain unchanged. Public Windows/Linux checks and supported sanitizers pass.

Supported coverage remains explicit: Windows core ASan is unavailable, host
UBSan traps are calibrated separately, Linux core uses native XAM and disables
vptr instrumentation, and generated guest objects remain uninstrumented under
their conservative wraparound/exact-math compile policy. These are recorded
coverage limits, not hidden passing checks.

## What can advance

Content preparation 045 and allocation-import contracts 046 are independent,
disjoint prerequisites for extending startup toward first-frame 011. The lead
must split that epic into concrete service-admission/backend/owned-frame tasks
before claiming implementation. An export present in the SDK is not proof of
correct behavior; no success stub or unreviewed data-variable use may be admitted
to manufacture a later checkpoint. Discovered runtime defects need scoped
repairs before dependent advancement.

Original modes/split-screen, four-player Survival, secure Steam/SDR, renderer
enhancements, performance budgets and release acceptance retain their roadmap
criteria. No gameplay benchmark exists. Runtime/renderer choices are revisited
at measured boot/mode/optimization/security checkpoints. Source/local-build
delivery is the current [distribution disposition](../legal/distribution.md),
not clearance for a game-linked package or RecompLauncher release.

This document reconciles existing reviewed experiments without inventing new
execution or repeating unchanged code tests as new title runs. Self-review
checked merged dependency state, actual versus synthetic coverage, original
failures, immutable artifact identities and the gate's narrow conclusion.
No independent reviewer is claimed.
