# Thread and lifecycle validation

MW3-039 remains open. The baseline exposed a repeatable cancellation defect
at a native import boundary. MW3-043 supplies an isolated SDK repair for that
defect. The [repair validation](../../config/toolchains/rexglue-stop/validation.md)
covers kernel and XAM imports, thunk return, and explicit exits. The sections
below retain the original synthetic baseline and its failures.

## Maintained contracts

The driver builds against actual verified SDK DLLs, without embedding old
kernel implementation objects. Select --suite platform, kernel, or all.
The combined suite checks interactions and builds Catch2 once per fresh profile.
Its 17 cases comprise ten platform/reference and seven guest-kernel cases.
Each runs alone, then all run in declaration order and shuffled orders with
seeds 1 and 0x12345678. Two further processes deliberately reject a wrong
cancellation result and missing stop/wake. Detector checks require exit 42,
exactly the selected case, one failed assertion with the exact exception
marker, no skips or sanitizer error, and one armed deadline marker where
applicable. A crash, timeout or unrelated failure cannot pass. Five game-free
Python tests cover result classification.

Original contracts cover:

- Manual/automatic events, semaphore capacity/over-release rejection, recursive
  mutex ownership, counted suspend/resume and alertable queued callbacks.
- Eight concurrent host TLS values and four-worker seeded mutex contention.
- Guest create/suspend/resume, startup arguments, r13/PCR identity, stack
  alignment/bounds and inaccessible guard pages.
- Eight concurrent guest TLS blocks, allocation/exhaustion, private values and
  clearing a freed slot while all threads remain alive behind explicit gates.
- Self-termination with exit 42 and no return, stop during wait/import transition,
  and barrier-controlled pending-stop admission at an import boundary.
- Four concurrent producers/consumers and 512 interlocked-list nodes for each
  of three seeds: exactly-once accounting, depth, payload/complement/canary
  checks and independent expected sum.
- Handles and tracked title pages returning to their before-run counts,
  repeated runtime cycles, and unload/destruction before App shutdown.
- Allocation high-water accounting and fresh logger observations after a
  deliberately retained historical warning.

New concurrency contracts use explicit barriers and bounded waits, without
sleeps hiding races. Unchanged upstream start-data/CPU-time/priority references
include sleeps; their passing is not a scheduling proof. The ordinary cancel
case signals readiness before wait entry, so it can stop on either side of the
import boundary. The extra native fixture gate guarantees the boundary case;
it is not game code.

Guest callbacks are original native C++ functions dispatched by the actual SDK.
Interlocked tests exercise kernel APIs, not translated lwarx/stwcx reservations
or PPC memory ordering. MW3 instructions, fibers/APCs/nonlocal paths and full
console equivalence remain untested. TSan is NOT RUN; ASan/UBSan cannot prove
freedom from data races.

Every process owns private config/temp/profile paths. Ordered cases, raw
logs/XML, source copies, compile commands and executed binary/source/SDK/compiler
hashes are retained and rechecked. Emergency _Exit(3) cleanup paths are failures,
never orderly-shutdown evidence. Isolation does not repair aggregate failures.

## Baseline failure: requested stop exit lost

A native fixture gate holds the child outside guest code until RequestStop(77)
has completed, then releases it into NtYieldExecution. Windows and Linux record:

    THREAD_CHILD_STOP exit=0
    THREAD_BOUNDARY_STOP requested=77 actual=0 returned=0

The child stops, but loses the requested exit. The contract fails rather than
accepting zero. An earlier Linux core-sanitizer run caught this intermittently
in the ordinary cancel case while its aggregate orders happened to pass. The
new gate makes it repeatable without timing assumptions.

Pinned source corroborates this: GuestToHostThunk in include/rex/ppc/call.h
throws default ThreadStop{} before/after imports when the context stop flag is
set; its default exit is zero. KernelThread::CheckStop instead loads the requested
exit. Full hook/spin/fiber consumer audit and repair belong to MW3-043. That
separate task must preserve explicit exits and baseline packages, identify and
rebuild affected consumers, and retain these failures. No replacement SDK has
been silently substituted.

## Retained aggregate-suite investigation

The original unit binary embeds kernel objects: its original neighboring
libraries are a historical reference, not repaired-DLL validation. Binary SHA:
b7b1a996ec59e513e4d0bd1f228484c15368e16c48333df3e3b28ca0be5fcde2.

Selection:

    [ppc],[memory],[aliases],[thread],[threads],[tls],[interlocked],[barrier],[dispatcher]

Fresh declaration/seed-1/seed-0x12345678 orders retain 3/26/24 failed cases of
261. These remain FAIL. Three concrete problems were investigated; this does
not explain every historical failure:

1. Delta reduction keeps the original seed-1 subsequence order and reduces 125
   predecessors in 12 runs to one: "the structural flags map to their settings"
   followed by "threads: ExTerminateThread ends the thread and signals its
   handle". The target passes alone; the pair fails opening its ToolApp. Source
   shows command-line settings persist, including gpu.driver=any and temporary
   paths. A later ToolApp's title-layer none cannot override command-line
   priority. The pair logs SDL selection with dummy video and missing temporary
   data. Settings contamination is supported by the pair and source; the exact
   ToolOpen error and all remaining declaration failures are not reduced.
   Our fixture sets its own private roots/none drivers at command-line priority;
   that does not repair the original aggregate suite.
2. host_alloc_test.cpp requires afterPeak >= beforePeak + 1000. Retained failure
   1000 >= 1500 demonstrates an invalid additive high-water assertion. Correct
   bound: max(beforePeak, beforeLive + allocation). Our original platform
   regression checks 500/1000/1000-byte allocations, live/count recovery and peak
   retention. The SDK allocator is unchanged.
3. core_test.cpp adds a logger sink, queues to an exited thread, then rejects
   warnings from CopySince(0). The public AddSink contract replays retained
   history. The token-expired and never-ran assertions passed; historical
   warnings invalidate its freshness predicate. Our regression deliberately
   retains a warning and checks only messages after the capture cursor, plus
   token release and no execution. The SDK logger is unchanged.

These findings bind to SDK ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d.
No upstream instructions or game text are treated as authorization.

## Corrected fixture assumptions

The first reference build could not link private kernel::ServeUI; it was
excluded rather than stubbed or linked as old kernel objects. Initial prototypes
also rejected invented NtResetEvent and a private address-space method; they
now use actual NtClearEvent and the exported GetAddressSpace test seam.

Two failed stack-guard assumptions are retained. Nonzero TLS can leave committed
alignment padding below PCR's usable stack limit. The misleading guest
stack_alloc_base is assigned the usable stack top in this SDK. The fixture
queries the actual heap allocation base and checks its first 64 KiB guard,
including the last byte. Those prototype failures did not prove a runtime guard
defect.

## Evidence and reproduction — 2026-11-18

Audited exact receipts follow. Earlier passing prototypes cannot supersede
expanded failures. Windows ASan is unsupported by the SDK allocator/link profile;
host UBSan traps are calibrated separately. Linux core instrumentation covers
base/PPC/kernel; unchanged graphics/module dependencies and Catch2 stay native.

    python tools/test_runtime_threads.py --root PRIVATE_CACHE --sdk-report VERIFIED_MEMORY_RECEIPT --output-root PRIVATE_OUTPUT --suite all [--sanitizers]
    python tools/check.py --config Release [--sanitizers]

--sanitizers permits an explicitly instrumented SDK receipt. The manifest records
whether the core or only callbacks are instrumented. Full commands and tool,
source and package hashes remain in each receipt. Actual owned-title orderly
shutdown remains MW3-041, blocked by unfinished thread acceptance and its repair.
No performance or release gate passes.

| Profile | Private directory | Manifest SHA-256 |
| --- | --- | --- |
| Linux native combined | `73d87a42248c4647bd7dad34b5c01677` | `173a2e9e93eebbf2782e5ddac0a12cf04793772f2a90e96b5a3f39f491ae89c1` |
| Windows host UBSan combined | `1195f38a4c3647d1845c742dce5540ce` | `b641732887d7d9a7e85da8d61fc1e48478353327b2c59a2a07de3dc9117e7697` |
| Linux core ASan/UBSan kernel | `e0066af355d34b8c81d238d4d921b02a` | `7a8888250eecf454905f68a5334749c4df1e44e1c1c601b706d212eb73aa1168` |
| Legacy orders | `6a788437fdbf4b8ba00c2ce9c27f7669` | `c84a4d2ab5939d8e63e033c888ef22d587f38855685a027ce6c377c88f3b3a72` |
| Legacy minimal pair | `f6fefa5369c34443bef8abc8e565a203` | `caf9d26a092ab0165760efa7198c252246f3c1c7ecbfa872db0eb46f5a6e966c` |

Expanded Windows/Linux combined runs each retain 18 PASS and 4 FAIL process
results: the boundary case alone and each of three aggregate orders fail. The
Linux core-instrumented kernel run retains 8 PASS and 4 FAIL processes. Both
mutation detectors pass in all three. These are intentionally retained failing
baselines, not completed acceptance. The binary, archived source/driver and every
XML/log hash were checked after collection. Legacy replay/reduction outputs are
under threads-039-legacy and threads-039-legacy-reduction; native diagnostics are
under threads-039 in their respective private host caches.
