# Host audio stream lifetime admission — MW3-062

`runtime/audio/streams` supplies an original C++20 ownership gate. It prevents
closed-session commands reaching a reused SDK stream ID. It does **not** revise
the SDK ABI, bind guest services, authenticate profiles, decode XMA, mix samples
or establish audible/title playback. Production integration needs a separate
agreed task. The SDK's raw lifetime behavior from [MW3-061](sdk-audio.md) remains
unchanged and is reproduced by the diagnostic bridge before testing admission.

## Ownership, execution and backend contract

The gate tracks at most eight active bindings per instance, using a fixed table.
An opaque copyable `Token` binds an instance identity, slot and monotonically
allocated lifetime serial. Default/moved tokens, other instances, closed/replaced
serials and wrong nonzero host owner IDs are refused before backend submission.
A token retains only instance identity, not a raw stream, gate or callback state.
Old tokens keep that identity alive, preventing address reuse from manufacturing
a matching instance. Tokens are neither persistent IDs nor authentication.

Every public operation belongs to the creating host thread. Wrong-thread calls
fail before touching the backend. Mutating backend reentry is rejected; the
backend contract forbids gate reentry. The gate is noncopyable/nonmovable and
**must also be destroyed on its creating thread**, outside an operation; violating
that lifetime precondition terminates rather than calling a thread-affine backend
unsafely. No concurrent destruction is supported. Backend outlives the gate;
SDK bridge/gates/tokens are scoped before application shutdown.

The new standalone `Backend` port has only open, submit and close. It must:

- Return a unique nonzero currently active raw ID, or throw without retaining
  a new stream. Different gates may share a backend with lower global capacity.
- Copy/consume the supplied PCM before submit returns, or throw on refusal.
  The gate checks a readable host span's length is exactly 1,536 floats and
  forwards that span. It does not normalize/copy samples or validate guest pointers.
- End a stream's callbacks and release it on nonthrowing close. Callbacks for
  one binding must be serialized, as with the selected SDK mixing contract.

This is an agreed new port with no parallel production consumer. Existing
audio-output/input/startup interfaces and SDK packages are untouched. The SDK
adapter in the test lane delegates to the actual `IAudioSystem`; it is not a
maintained production guest adapter or substitute mixer.

## Callback credits, failure and resource semantics

Each open creates independent shared callback state with an active flag,
monotonic played counter and fault flag. Its callback captures that state only;
it has no gate/backend/client pointer. The serialized producer performs atomic
loads/stores, with no allocation, locks, CAS spin, SDK reentry or arbitrary client
callback. The owner polls credits. Only the producer writes the total; polling
never resets it. This is explicitly not a general multi-producer callback API.

Close invalidates the binding and deactivates its callback state before closing
the raw backend stream. Owner-close deactivates all that owner's bindings before
the first close; other owners remain intact. A late retained callback therefore
cannot credit a replacement. In-flight old state can outlive the gate safely and
contains no reference to replacement state. The actual SDK already promises a
close barrier; deliberately delayed callback copies are model fault tests, not
claims that the SDK produced those late callbacks.

Successful opens and accepted frames have explicit positive lifetime budgets
(`Limits`, uint64 maxima by default). Checks precede increments/submissions,
so identifiers/frame counters cannot wrap. Small budgets exercise exhaustion.
Callbacks saturate and latch a fault instead of wrapping. Observed completions
must be monotonic and no greater than accepted frames. A callback fault blocks
further submit/poll for that binding until it is closed; another owner continues.
A callback may arrive during backend submit; owner polling cannot reenter it,
and accepted accounting advances only after a successful return.

Ordinary open/submit exceptions propagate unchanged; no successful frame or
binding is invented and earlier valid owners remain usable. A zero or duplicate
active raw ID is a broken backend identity contract: admission latches a global
fault. It does not close an ambiguous returned duplicate, which could destroy an
earlier owner. Explicit shutdown still closes each previously owned ID once.
The gate cannot certify recovery of unidentifiable resources inside a broken
backend. A conforming backend must clean partial allocation before throwing.

Shutdown is idempotent and invalidates all tokens before closing owned streams.
Destructor cleanup uses the same path. Normal admitted submissions perform no
ownership allocation or PCM copy; opens allocate lifetime state, and diagnostic
exceptions may allocate. Backend queue/copy/allocator costs remain the backend's.
The gate's budgets are total lifetime limits, not a replacement queue-depth policy.

## Distinct evidence classes

| Evidence | Actual observation and scope |
| --- | --- |
| Original model contracts | Nine groups cover lifetime/raw-slot reuse, owner/instance/move rejection, backend open/submit refusal, duplicate/zero raw IDs, delayed callback copies, credit/admission limits, frame bounds, wrong-thread calls, one serialized callback producer, close-owner, shutdown/destructor and reentry. These inject model faults and do not prove SDK playback. |
| Actual unchanged SDK bridge | Three isolated runs per case/mode plus both combined orders exercise reuse, owners, queue refusal/recovery and 32-cycle lifetimes. The raw baseline still accepts an old ID after reuse, but the host token is rejected without another SDK Submit. Replacement and other owner credits continue. |
| SDK cleanup | Opens/closes match, streams/queues are empty, SDK-tracked threads recover 0 to 0, and SDL audio state returns to zero. This is not proof of every OS/library allocation or general race freedom. |
| Completion guards | Eight Python tests reject wrong/stale/duplicate/malformed/partial/typed/metric/resource/device-fallback results, wrong SDK call counts and implausible baselines; they include a real captured child timing out after plausible output. Those fixtures do not load an SDK. |

Native model contracts pass on Windows/MSVC and Linux/GCC ASan/UBSan; a separate
Windows MSVC ASan run also passes all nine groups. Model tests verify a span
reaches the backend at the original address, including nonfinite bits; they do
not claim what a mixer does with them. Counter exhaustion uses explicit small
budgets rather than pretending to execute 2^64 opens/frames. Wrong-thread
destruction is a lifetime precondition, not a supported recovery operation.

The SDK bridge uses required six-channel SDL **dummy** output or explicit
two-channel `none` timer mode. A dummy-mode two-channel fallback cannot certify
device opening. All four native/host-sanitizer profiles pass **128 process
checks**, including **16 expected wrong-result/incomplete controls**. Forty
ordinary reuse observations retain raw ID 2 aliasing, alongside successful host
admission protection. There are **1,360 ordinary stale-command rejections before
SDK submission** across reuse, owner-close and repeated lifetimes. Additional
controls remain separate. The SDK raw ownership gap has not become a passing
SDK contract; MW3-061's original failing receipts remain valid.

Only owned profiles, output/config/user roots, handles and original finite PCM
are used. No game bytes, generated guest code, keys, private traces, production
services or physical audio devices are accessed. There is no owner/account
authentication, guest render-client binding, DSP/channel/order verification,
physical device-loss test, audible latency/listening or playable-mode claim.

## Reproduce

```text
python -m unittest discover -s tests/host_platform/audio_streams -p test_*.py -v
cmake -S tests/host_platform/audio_streams -B <private-model-build> -DCMAKE_BUILD_TYPE=Release
cmake --build <private-model-build> --config Release --parallel 2
ctest --test-dir <private-model-build> -C Release --output-on-failure
python tools/test_audio_streams.py --root <private-cache> --sdk-report <approved-native-xma-manifest.json> --output-root <new-private-output>
python tools/test_audio_streams.py --root <private-cache> --sdk-report <approved-native-xma-manifest.json> --output-root <new-private-output> --sanitizers
python tools/check.py --config Release
python tools/check.py --config Release --sanitizers
```

Public discovery uses the C++20 model project (Linux ASan/UBSan by default).
Set `MW3_AUDIO_STREAM_TEST_SANITIZERS=ON` and place the installed MSVC ASan runtime
on PATH for a separate Windows run. The SDK runner snapshots both maintained
core and test source, builds with two workers and links the original core as
C++20 while its SDK-facing executable is C++23. The pinned SDK's Clang 20.1.2
compiler/configuration is required. SDK runs use three isolated repetitions by
default, ordered/reversed combined cases and fresh nonce-bound controls.

Public CI never obtains an SDK/game or runs a title. The SDK runner verifies
the immutable approved native package before and after, all relevant loaded
library bytes, both source snapshots, driver/binary and every retained artifact.
It imports existing read-only MW3-060/061 verification helpers; their code and
the other input/memory/SDK-preparation lanes are not edited. Test-only bridge
files are excluded from public model targets.

The core and bridge are instrumented in SDK-facing Linux ASan/UBSan and Windows
calibrated UBSan-trap profiles; native SDK/audio/SDL libraries remain
uninstrumented. The selected SDK profile does not provide Windows core ASan;
the standalone C++20 core is separately exercised with MSVC ASan. No general
SDK allocator, physical-hardware or two-machine coverage is inferred.

Self-review only; no independent review is represented. Host admission is
complete for this scope; production scheduling, owner identity mapping, guest
service admission and actual MW3 audio compatibility require agreed follow-ups.

## Recorded identities and provenance

These are original GPL-3.0-only project sources. The public change contains no
SDK implementation, package, binary, game-derived code or private record. The
approved SDK/SDL packages keep their existing provenance and licenses; local
diagnostic linkage does not authorize redistributing them or game binaries.

Final matrix receipts bind all maintained core/bridge/driver sources, build
commands, compiler, package, binary, loaded libraries, nonces and retained
artifacts. An independent collector rehashed those artifacts and checked the
current source against each snapshot after the runs. SHA-256 values follow.
Unchanged verification helpers are bound to base commit
`4df31548683faef3a63055d94079b6396ff00ddb`; the task's changed source hashes
below identify the implementation independently of documentation edits.

| Profile (32/32 each) | Private attempt ID | Manifest SHA-256 | Binary SHA-256 |
| --- | --- | --- | --- |
| sdk-windows-native | `2c91fcd9c403491e98b6bd21c9794147` | `7a7611df51a2494e719288e0d902b69f62b5ed2fd8b5b1887c7ad07de3259776` | `814c5168fe463491c6dd741dfce9ea53bd95155085bcf808d2d713cb5f1258d2` |
| sdk-windows-ubsan | `4c2aa2211edd40a0810395f6863f9c16` | `1e33bad4ff93459fdfe4efde99e68628c055b7f8a4f8dcbd32615cce2b48fbde` | `2751e83e319e599dd120e86583dd968b6f4687ab8bc13dda7a92c1e6c239706d` |
| sdk-linux-native | `9ff21a9821344304a82d9ebfc98fa5f8` | `230a84b526357521eaae59c203f8dae5ef090171b3b9fc862a83d8682cfb01e1` | `1b53853be7f4a2f5b3a79d4d8e5c2d448e144c848cdf3fc3792d4c0452157d71` |
| sdk-linux-asan | `79bb05d818714afa9464ce329e7f74a4` | `c2902212515c8e6d67a322f9bf2411386e3507354eda6cc1fb57ceb0932276b4` | `e811c68fab08277d67d7224171612084129c8725cb1007607c8ef7bb0608c65f` |

The two Windows profiles use approved preparation receipt
`6d435da877fe2bce5eab777cf19d2aa34159f230e5a7f06e30446f6c7c2c8558`;
the two Linux profiles use
`480059015ad3f14e36b972b416aa67458f016f2f5cecf23b886afd6680245c17`.
Both use Clang 20.1.2, Release `-O2 -DNDEBUG`, x86-64-v2 and two build workers.
Windows pinned compiler archive/files hashes are
`8e771a685cd718303ea0d632a8a95ad7b3cb17068f3952fbefa64a77290324d8` /
`300ca7cd9b2d224ef1e57b70fa3351166047bb313de6b49ae2fbc7becbaef3d7`;
Linux clang binary hash is
`b15e7640bf3082f36ef14321711706b265df3058721e3c2caef3a4b83895d07d`.

| Maintained input | SHA-256 |
| --- | --- |
| `runtime/audio/streams/streams.cpp` | `3ebd9e0de64134572698176edd016be652c8f353fda031324742d8b61958f7c0` |
| `runtime/audio/streams/streams.hpp` | `6b4e89146bdc6000de2a57ca81fec2f76926e3df774de1a3268abe73e4e93f99` |
| `tests/host_platform/audio_streams/__init__.py` | `005968a953091e26becb75148418187a7737a57731485eec99d23fc07a6677b9` |
| `tests/host_platform/audio_streams/CMakeLists.txt` | `5d2ed84c1709dd6b791dee649e76dc9f88ce29a920498fa4094df91b4769794f` |
| `tests/host_platform/audio_streams/contracts.cpp` | `dc3dc0938444ecdb37c350529aa547355d673ef1ff86b5549efd4f9c379e35f3` |
| `tests/host_platform/audio_streams/sdk_contracts.cpp` | `8a312f27aa319a30b1486aff19ddf6f4e89d48d910e6aabff0e20794fb7bf2c3` |
| `tests/host_platform/audio_streams/test_driver.py` | `3f3b81df5d86002834e2cc4d5ab914ed626c8ddf22bd4d72a365b1b26e67008d` |
| `tests/host_platform/audio_streams/test_native.py` | `04877a1fd78e2a81fb4fa63666319250fe67ab460a7374089bdfda8a8879b69c` |
| `tools/test_audio_streams.py` | `35b263f4c3730acf3bf8d7ed239b3c4b32f74766286c1bc3f3f19f69fa9d4376` |

Actual loaded-library bytes are identical between native and host-sanitizer
profiles of each OS, and match the approved package before/after testing.
Timer mode does not load the SDL audio provider; dummy mode must load it.

| Module | Windows SHA-256 | Linux SHA-256 |
| --- | --- | --- |
| audio | `e35cda901c79f0e176ee01ff90b0f542f60df81a45870c2ce77b2034ccd7407b` | `be9994cc33965f313872233cae90a0638b2e7d0bb308c4e652290cf2754ed4c3` |
| app | `da6439e68dac00329ded39654cb10e726430a2f374810dbff563bf7a9800b569` | `9d66fa4b10cff33b708798d2dbef7e1f7a0d0f8cc280435e61dc68cb7a745d1f` |
| base | `3149476e16d580859e8a953df2890e7cd3cf5e225dc37402ccf57817eca46faa` | `83e249a8d25fb605168876e0fc68bf10bb978425084c314962292dfcb49f1c4f` |
| sdl | `34a0c251b281bc58060ab1c271e9c59227b51347b1ab1e9c7ac2e2a1c218b61d` | `9c83b5d1a533825354dc64a7153f3722840fcf4abac894e2c277bbff15e161d4` |
| provider | `e7843a8e0ebf0db151b2e02a164c11260a12a814802b0166a740c93b8f001ea5` | `b483f4482e1f744b4e54dd7a72218e67adb22b74548b822a2b73f69c168e2337` |

## Measured costs and architecture decision

All observations are game-free on one i5-11400 (6 cores/12 threads), about
32 GiB RAM, Windows 11 Pro build 26300 / WSL Ubuntu 24.04. Builds are
serialized within this lane, with two workers. Other contributor background
activity is not controlled; these are neither an OS comparison nor a title
performance budget. Raw timings, commands and correctness records stay private.

The original model benchmark uses three fresh native Release processes per OS
(MSVC 19.44 Windows, GCC 13.3 Linux), each with 256 discarded warmup submissions
and 4,096 measured batches of 64 admitted submits. Credit polling and batch
assertions are outside the timed batches; the backend span check remains inside
each measured submit. Every batch conserves all 64 completion credits.
The allocation override observes **zero allocations** during those measured
submits; pointer checks separately verify no gate PCM copy. The model backend
does trivial counter/callback work and supplies no SDK/device/mixer cost.

| Synthetic model | Three batch-averaged submit medians (ns) | Three p95 (ns) | Three maxima (ns) |
| --- | --- | --- | --- |
| windows | 9.375, 9.375, 9.375 | 9.375, 9.375, 10.9375 | 157.8125, 117.1875, 182.8125 |
| linux | 11.765625, 9.21875, 7.203125 | 13.6875, 14.421875, 11.828125 | 454.28125, 318.28125, 875.296875 |

These are batch-averaged observations, not individual-call tail latency.
Medians use the central mean, p95 nearest rank; Windows timer quantization
is visible. No instruction-level/nanosecond-resolution claim follows.

| Model receipt | Manifest SHA-256 | Binary SHA-256 |
| --- | --- | --- |
| windows | `255b4be678d1440a230ad4a3cb6d125d07aa62beb6665c36a1f3f30db354f461` | `a1972bb0a8e9fc31d22ec835b92bc09762360232fe453932fa2d1758bdf15ddf` |
| linux | `ef088dd39d29cdbca6bbc58666f4fa2d9fcdd94f0c40993732ce54783b8c0b51` | `e78655249e74454c90213c93bc0fc2ac27fa5e0a63bcfe1de9859fb740c426a2` |

Actual SDK lifecycle measurements use three independent processes per mode,
32 close/reopen cycles, 160 accepted submits and 32 stale refusals/process.
There is no discarded SDK warmup: all calls are retained. Whole-case elapsed
includes open/close, callback waits and checks; submit timing includes the
gate plus real backend copy/queue work, but excludes later callback waiting.

| Native SDK mode | Three lifecycle elapsed times (ms) | Three submit medians (us) | Three p95 (us) | Three maxima (us) |
| --- | --- | --- | --- | --- |
| windows timer | 170.715, 171.630, 172.168 | 0.7000, 0.7000, 0.8000 | 2.5000, 2.5000, 3.2000 | 5.0000, 3.6000, 4.9000 |
| windows sdl | 683.357, 682.280, 682.038 | 0.6000, 0.8000, 0.7500 | 2.7000, 2.5000, 2.6000 | 14.3000, 4.2000, 7.6000 |
| linux timer | 170.608, 170.919, 170.585 | 0.5405, 0.5145, 0.5060 | 2.1150, 1.7640, 2.3780 | 8.9330, 9.1420, 11.3630 |
| linux sdl | 677.300, 677.003, 676.688 | 0.5070, 0.5315, 0.5260 | 1.9970, 2.4170, 2.4830 | 9.1870, 7.9000, 10.4430 |

The 32 stale refusals/process include exception construction/unwinding; these
are diagnostics, not a real-time path. Their per-run median/p95/maxima (us):

| Native SDK mode | Three medians | Three p95 | Three maxima |
| --- | --- | --- | --- |
| windows timer | 15.2500, 15.0500, 17.3000 | 24.6000, 24.4000, 24.8000 | 33.8000, 27.9000, 29.5000 |
| windows sdl | 15.5000, 15.0500, 14.7500 | 24.7000, 21.2000, 21.8000 | 64.9000, 24.3000, 22.4000 |
| linux timer | 15.9460, 15.0250, 16.4270 | 21.3140, 23.1570, 24.4990 | 40.9230, 29.7220, 33.7110 |
| linux sdl | 15.5150, 16.0410, 16.2495 | 29.9710, 26.0970, 33.9940 | 45.3910, 28.1680, 45.4310 |

All raw call durations and separate sanitizer-profile timings remain in the
hashed receipts. The raw-ID baseline is correctness-ineligible and provides
no performance winner. These measurements do not establish a speedup, audible
latency, gameplay performance, codec fidelity or a fastest framework.

Decision: retain this bounded host admission boundary for review, with the
production adapter deferred to an agreed integration task. Correctness and
licensing precede scoring. Performance (30%) has measured synthetic admission
cost/zero hot-path ownership allocations, but no title budget or comparative
score. Stability (25%) has repeated owner isolation/cleanup evidence with
uninstrumented SDK limits. Maintainability (20%) favors one small fixed table
and detached counters over a second audio implementation. Integration effort
(15%) still requires explicit owner mapping and production scheduling. Hardware
compatibility (10%) is unknown for physical devices. Missing scores stay
unknown; no numeric aggregate or architecture-speed ranking is justified.

Final public checks from this isolated worktree: Windows Python 3.12.14 /
CMake 3.31.6 / MSVC 19.44 `python tools/check.py --config Release` passes
**203 Python tests, eight explicit skips, parser CTest 1/1**. Linux Python
3.12.3 / CMake 3.28.3 / GCC 13.3 `python tools/check.py --config Release
--sanitizers` passes **203 Python tests, two Windows-only skips, parser 1/1**.
This lane adds eight evidence-guard tests and three native-driver tests;
the native driver runs all nine C++ groups plus wrong-result/argument controls.
An earlier Windows prototype also passed 16/16 SDK process checks; it is
retained separately from the final 128 and is not silently pooled.
