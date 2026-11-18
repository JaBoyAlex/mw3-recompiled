# Thread and lifecycle validation

MW3-039 is **in progress**. No thread/kernel or normal title teardown gate passes.

The first tranche compiles selected original upstream platform-thread tests
against the actual prepared SDK DLLs. `thread_start_data`, thread CPU-time and
priority cases, plus original public-API synchronization contracts run individually and together in
declaration and seeded shuffled orders. These are platform/native-callback
diagnostics, not translated guest-thread instruction validation. Some unchanged
upstream reference cases use sleeps; new kernel contracts must use explicit
barriers and bounded waits. Their output cannot be labeled a scheduling proof.

The driver requires `--suite platform`, records that kernel contracts are
incomplete, and checks the actual base-library import. Per-case private roots,
raw XML/logs, seeds/orders, source/SDK/compiler/binary identities and distinct
aggregate results remain retained. Process isolation cannot resolve or hide
aggregate failures. The original large SDK unit binary embeds kernel objects;
staging a repaired DLL beside it does not validate that repair.

Required remaining work:

- Actual guest-runtime TLS/r13 and stack bounds; create/suspend/resume/terminate.
- Events, semaphores, recursive mutexes, cancellation/timeouts and ordering.
- Original deterministic seeded contention, explicit result/timeout mutations,
  handle/page/thread accounting and repeated runtime teardown.
- Investigate retained original aggregate-suite shared-state/order failures;
  report causes and remaining gaps separately from the focused diagnostic set.
- Supported Windows/Linux and sanitizer runs, with exact limitations.

The upstream real-module fixture mode (`REX_TEST_REAL_MODULES`) and exported
SDK test-access seams are useful references. Several original kernel tests also
reach private `TitleState` implementation symbols: they cannot automatically be
reused as DLL correctness tests. Prefer the public runtime/thread/memory/object
interfaces for original contracts. Do not embed old implementation objects or
enable unreviewed MW3 imports to make tests pass.

The first attempted upstream drain-helper build could not link the private
`kernel::ServeUI` symbol. That failure is retained. The helper was excluded from
DLL acceptance rather than supplied with a stub or linked implementation
objects. Original cases instead exercise public SDK events, semaphore capacity,
recursive mutexes, counted suspended starts, eight concurrent host TLS values,
seeded contended payload accumulation and alertable queued callbacks. These are
host/platform semantics; guest TLS/r13 and guest kernel cancellation remain open.

No owned game files are needed for this task. Actual owned-title orderly
shutdown remains MW3-041. This task does not advance the guarded header-service
checkpoint, admit more imports, or certify gameplay/performance.

## Initial platform evidence

Both initial native profiles pass nine cases in isolation and three aggregate
orders (declaration, seed 1, seed 0x12345678), 12 processes per host. This is
platform-only prototype evidence. Guest-kernel contracts, sanitizer/mutation
runs and the retained large aggregate-suite investigation remain unfinished.
The Windows run also includes the subsequent result-count guard checks; no
performance or full-kernel equivalence claim is made.

| Profile | Private output directory | Manifest SHA-256 |
| --- | --- | --- |
| Linux native | `f94758ccf05d425d8b83e9955967374f` | `26f02f87cfbe8a9e7c02f8bc9f3941c929f63a13ef1b8c528a8845624f78cbdd` |
| Windows native | `fd2c94da2c7d4affbc81c913b4cbf09b` | `a89f12e105eb37c0470096ce941112c291f63b6cca2ec6c335103b811db37c06` |
