# Runtime selection: ReXGlue leads the bounded bring-up experiment

Status: **provisional, MW3-008 incomplete**. Evidence dated 2026-11-17.

Continue bounded MW3 bring-up with pinned ReXGlue v0.11.0 while retaining the
related-title generator as a control. Do not commit to a permanent runtime,
combine runtime internals or unlock dependent product gates yet. The
[reproduction and evidence](../../experiments/runtime-bakeoff/README.md) preserve
both failures and successes.

ReXGlue generated both owned executables without forced validation, compiled
both private native host programs, and reached the first function import from
each translated entry path. All function imports were guarded stops, not
successful stubs. Each title reproduced that stop in three separate processes;
the observed return sites match the independently decoded MW3 call inventory.
This establishes bounded Linux/WSL execution only. Windows boot, full modes and
normal shutdown remain unverified.

The MW2-derived analyzer usefully finds main-engine switch candidates that the
original analyzer misses. Reuse its proven tool patch and review its techniques.
Its translator also emits 377 SP / 436 MP switch-target/function-boundary error
diagnostics despite returning zero. Its unmodified runtime heap starts inside
MW3's generated function-table range. Those are correctness/integration blockers
before a comparable title run, not a reason to call generation successful or
hand-edit generated C++. No MW2 guest addresses were imported into MW3.

The shared runtime currently requires less demonstrated title-specific repair.
Its 261 selected original host cases pass in isolated processes, but aggregate
execution exposes shared-state/order-sensitive failures. Its SDK requires
C++23/Clang 20 and has unresolved distribution/provenance obligations. Related
title code remains a reference; its GPL licensing alone does not decide this
technical choice. Neither candidate has release clearance.

No weighted performance winner can be declared. Correctness and licensing
remain gates; performance 30%, stability 25%, maintainability 20%, integration
effort 15%, hardware compatibility 10% remain the eventual criteria. There are
no comparable MW3 frame times, memory peaks, GPU results, loading distributions
or input-latency measurements. Generation/build durations are preparation
observations with unequal work and cache histories, not gameplay benchmarks.

To finish MW3-008:

1. Resolve or narrowly isolate the MW2 translator boundary failures and memory
   collision before running the same bounded title workload. Do not grow this
   into a second permanent port; reassess the stop decision if repair becomes
   disproportionate, retaining the explicit unmet comparison requirement.
2. Run common original CPU/memory/thread workloads on both actual runtime
   paths. Existing ReXGlue tests and the canonical PPC oracle are different
   workloads and cannot be scored against one another.
3. Audit the first imported service and all used data imports against the exact
   MW3 module; permit services only with explicit semantic evidence. Continue
   diagnostic stops everywhere else.
4. Record actual memory aliases, TLS/thread behavior, shutdown, native Windows
   constraints and link/provenance issues, then select one base and stop the
   losing experiment. If the spike exceeds three days, split testable follow-ups
   before more implementation claims.

Revisit the choice at first playable boot, first complete mode, major
optimization and relevant upstream security changes. Steam/NVIDIA work,
four-player Survival, community interoperability and launcher packaging remain
behind their existing dependencies.
