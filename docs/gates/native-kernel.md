# Controlled native lifecycle integration

MW3-041 is in progress. The integration checkpoint admits the audited
RtlImageXexHeaderField service, then stops at the next guarded import.
The owned Campaign and Multiplayer modules are regenerated privately against
the verified stop-repair SDK and rebuilt with the conservative guest policy.

The host records the diagnostic stop, waits for the runtime's title-exit
notification, checks the stopped guest thread's exit metadata, unloads and
destroys the title runtime, checks the former reservation is available, and
shuts down the app. It also compares SDK host-thread counts before and after.

The initial matrix runs three ordinary startup processes and separate invalid
binding, malformed-pointer, incorrect-oracle and interruption cases for each
executable. Each process owns its profile and temporary files. Interruption
uses a host gate at the audited header query and requests exit 88 while the
guest is waiting. Rejected cases must complete teardown as well as report the
specific failure. A watchdog termination cannot substitute for that evidence.

The standalone driver is `tools/verify_kernel_gate.py`. It checks all required
child task states and verifies the owned executable pair, SDK receipt, recipe,
analysis metadata and generated payload. The import wrappers still verify
every mapped function binding. The additional wrapper changes diagnostic
termination from process exit to guest-thread unwind.

```text
python tools/verify_kernel_gate.py --root PRIVATE_RUNTIME_CACHE --sdk-report NATIVE_STOP_RECEIPT --owned OWNED_EXECUTABLE_PAIR --metadata VERIFIED_METADATA --output-root PRIVATE_OUTPUT --role sp
```

Repeat for `mp`. A generation receipt can be consumed with `--generation` and
`--expected-generation-sha256` after complete payload verification. Windows
requires this independent generation receipt. `--sanitizers` instruments the
maintained host code, while generated guest objects use their established
wraparound and exact floating-point compile policy.

The current Linux Campaign native run passes all seven cases, including
reclaiming the entire 4.5 GiB former mapping span and recovering SDK thread
counts from zero to zero. Each attempt retains its own executable and source
snapshots; a serialized build cache cannot overwrite executed evidence.

The first host-ASan/UBSan run fails six cases after title launch; only the
pre-launch binding rejection passes. LeakSanitizer reports **41,991,680 bytes
in 1,280 allocations**, originating in the 320 XMA contexts created at launch.
A second run with slow allocation unwinding resolves the allocation stacks
through `XMAContext::Setup`, `XMADecoder::Setup` and the APU/title launch path.
The context destructor frees its codec and frame but omits its allocated
packet and packet buffer. All ordinary teardown markers still appear; the
driver correctly rejects these processes because they leak. Baseline failures
are retained privately and must not become passing evidence by suppressing
leak detection. MW3-044 scopes the SDK repair separately, and blocks this task.

Acceptance remains open until both platforms and supported sanitizer cases
pass with the repaired profile. First-frame,
gameplay, original split-screen, four-player Survival, networking and renderer
modernization retain their existing dependencies and criteria.
