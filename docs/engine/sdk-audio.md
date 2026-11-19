# Selected-SDK host audio investigation — MW3-061

This original game-free diagnostic executes the actual approved audio system and,
when requested, the actual SDL3 audio provider. The investigation is complete;
**raw stream IDs do not meet the project's lifetime-ownership requirement**.
All four final private suites correctly return 1. Their failures remain failures.
No title is launched, XMA decoded, physical device exercised or audible output
verified. MW3-082, guest audio services and platform/gameplay gates remain open.

## Actual boundary and observed ownership gap

The C++ harness uses `App::GetAudio()` from the loaded `rexapu` module. Its
virtual-method address identifies that actual module. The driver also resolves
the loaded app/base/SDL/provider libraries and checks their bytes against the
already-approved package; an approved copy staged beside the private executable
is allowed. No SDK audio implementation is embedded, replaced or repaired.

Two explicit modes run the same cases:

- `timer`: `apu.driver=none`, no SDL audio device, reported output channels 2.
- `sdl`: required audio, `apu.driver=sdl3`, actual SDL `dummy` backend, reported
  output channels 6. This is a real driver/callback path with an artificial sink.

Neither mode proves the mixed samples, surround/downmix coefficients, speakers,
audible latency, codec fidelity or title playback. The installed Windows SDL
enumerates WASAPI, DirectSound and dummy, with no disk-capture backend. No shared
SDK rebuild is used to add one. Physical output/listening/device-loss tests are
NOT RUN. Full title playback still requires MW3-011 and a separately agreed
service/format integration task.

Each case supplies original finite float PCM in host byte order: six planar
channels, 256 samples/channel at 48 kHz, 6,144 bytes/frame. The small alternating
tagged values are generated in the maintained harness; no game audio is read.
Played callbacks record only atomic counters/semaphore notifications, never
reenter or block on the SDK. Byte-level output/order correctness is not inferred
from callback counts.

The identity probe holds another stream open, plays one frame on stream ID 2,
closes ID 2, and confirms a submit to that closed ID is rejected. After opening
a replacement, its raw ID is again **2**. Submitting via the old ID then succeeds
and invokes the replacement's played callback. The first owner's callback stays
at one, the other stream stays at zero, and the replacement receives one callback.
The probe closes all streams, checks cleanup, records
`stale-stream-id-retargeted-replacement`, and exits 42.

This repeats in every native/host-sanitizer mode and both combined case orders.
It is an observed reuse of an SDK raw slot identifier, not a claim that its API
promises a generational handle. Such an ID is insufficient as an MW3
profile/client/session ownership token. A future agreed adapter must reject old
session commands before forwarding to a reused raw ID, or an independently
reviewed SDK/interface change must supply that guarantee. Do not wire guest
render clients or local-player ownership directly to the raw ID. No shared
interface or SDK fix is included here.

## Cases, accounting and negative controls

| Case | Required/observed result |
| --- | --- |
| `capacity` | Eight streams open; a ninth fails. IDs 0, 9 and UINT32_MAX refuse submissions; invalid closes preserve all owned streams. No frame means no played callback. PASS. |
| `identity` | Closed ID is refused before reuse; old ID retargets the reopened stream and its callback. FAIL, with exact old/new IDs and accepted/callback counts retained. |
| `queue` | Queue limit configured to four; a full queue fails without waiting for a device. Accepted frames drain with matching callbacks; a second stream receives only its own callback. Empty-stream underruns increase. PASS. |
| `lifecycle` | 32 cycles each submit four frames, close/discard, then open an observer, submit one frame, await its callback and close. Closed-owner counters stay unchanged during observer progress; 64 opens/160 accepts, all streams/queues recover. PASS. |

For each mode/profile, three isolated processes per case are followed by both
combined orders. A case failure does not skip the remaining combined cases;
streams are cleaned up before continuation. Deadlines, queue/submission budgets
and per-process timeouts are bounded. No sleep is used to manufacture callback
success. Shutdown must recover the SDK-tracked thread count (0 to 0 here), all
open/queued streams and SDL audio initialization. This is not proof that every
OS allocation/thread or uninstrumented SDK object is leak-free.

Ordinary completion is a single strict JSON record bound to the fresh nonce,
mode and ordered case list, plus exactly one loaded-library record. Duplicate
fields/records, wrong types/case/mode/nonce/libraries, malformed/partial output,
resource mismatches, sanitizer/crash markers or inconsistent exit/status cannot
pass. A valid FAIL record stays FAIL. Logs and source/config/binary/artifact
identities remain private and are rehashed after execution.

Each profile also runs two wrong-result controls, two incomplete-record
controls and one unavailable-backend control. A wrong-result case must complete
the capacity work and cleanup, then fail with the exact deliberate reason and
exit 42. Incomplete controls shut down cleanly but omit ordinary completion and
exit 43. An invalid SDL backend must be refused with the actual wrapped
`kModule` error, the specific no-audio-driver message, cleaned resources and the
SDK's preserved startup-failure shutdown code 1; its detector exits 44. These
five controls are expected detector passes, not audio success.

Earlier Windows attempts are retained separately: 17 ownership-marker setup
refusals caused by text newline translation; a wrong expected init-error
category; a wrong expected failed-startup shutdown code; and one access
violation from deliberately forcing CRT process exit while SDK audio remained
active. Marker bytes/control expectations were corrected. The incomplete
protocol control now shuts down before returning without completion. The forced
exit crash is not counted as passing, not a normal lifecycle observation, and
not represented as a repaired SDK crash. Ordinary crashes/timeouts always fail;
the guard tests include an actual owned child timing out after printing plausible
completion. All predecessor attempts remain outside the final matrix below.

## Exact execution identities

The approved native packages are those already accepted by MW3-044 and verified
read-only through MW3-060's package checker. Every SDK file must still match the
approved receipt, both before and after the suite; source checkouts are not
regenerated or modified. The SDK reports 0.11.0.0-dev.unknown, so that label alone
is not identity: receipts, source identity and actual library hashes are used.
SDL's runtime version is checked as 3.4.14 (`3004014`).

| Identity | Windows | Linux/WSL |
| --- | --- | --- |
| Approved preparation receipt SHA-256 | `6d435da877fe2bce5eab777cf19d2aa34159f230e5a7f06e30446f6c7c2c8558` | `480059015ad3f14e36b972b416aa67458f016f2f5cecf23b886afd6680245c17` |
| Approved source identity SHA-256 | `3f93b2a941986a79f0407fc6151928e72b0b0565b216a6fabfba2f993e5fc530` | `f80844d9f1968b48c63c967b82fabca5b0c32b7166d5a1b669b6a0b1adcf7944` |
| Compiler | Clang 20.1.2, MSVC 14.44 tools | Ubuntu Clang 20.1.2, GCC 13 C++ library |
| Compiler archive/files or executable SHA-256 | `8e771a685cd718303ea0d632a8a95ad7b3cb17068f3952fbefa64a77290324d8` / `300ca7cd9b2d224ef1e57b70fa3351166047bb313de6b49ae2fbc7becbaef3d7` | `b15e7640bf3082f36ef14321711706b265df3058721e3c2caef3a4b83895d07d` |
| Actual `rexapu` SHA-256 | `e35cda901c79f0e176ee01ff90b0f542f60df81a45870c2ce77b2034ccd7407b` | `be9994cc33965f313872233cae90a0638b2e7d0bb308c4e652290cf2754ed4c3` |
| Actual `rexapu-sdl3` SHA-256 | `e7843a8e0ebf0db151b2e02a164c11260a12a814802b0166a740c93b8f001ea5` | `b483f4482e1f744b4e54dd7a72218e67adb22b74548b822a2b73f69c168e2337` |
| Actual SDL3 SHA-256 | `34a0c251b281bc58060ab1c271e9c59227b51347b1ab1e9c7ac2e2a1c218b61d` | `9c83b5d1a533825354dc64a7153f3722840fcf4abac894e2c277bbff15e161d4` |
| Actual `rexbase` SHA-256 | `3149476e16d580859e8a953df2890e7cd3cf5e225dc37402ccf57817eca46faa` | `83e249a8d25fb605168876e0fc68bf10bb978425084c314962292dfcb49f1c4f` |
| Actual `rexapp` SHA-256 | `da6439e68dac00329ded39654cb10e726430a2f374810dbff563bf7a9800b569` | `9d66fa4b10cff33b708798d2dbef7e1f7a0d0f8cc280435e61dc68cb7a745d1f` |

All four profiles use identical maintained C++/CMake/driver/guard bytes.
Harness SHA-256: `b28a969986bba20078c827093ae3ba225de81c27d76f2873ab6c158d6bcdc47c`;
driver SHA-256: `d011c6723979d2726aa493eaea1d8c794f0990b425f6e8f0f78ffe270a36ba73`.
SDK-facing code uses C++23 as required by its headers, `-O2 -DNDEBUG`,
`-march=x86-64-v2`, and two build workers. Public guard tooling uses Python's
standard library and does not load an SDK in CI. Original source is GPL-3.0-only;
the existing approved SDK/SDL packages retain their own provenance/licenses.
No SDK, codec source, library, game-derived output or private log is published.

| Final profile | Private attempt ID | Manifest SHA-256 | Harness binary SHA-256 |
| --- | --- | --- | --- |
| Windows native | `8b031639a1cc413cab98e2fc0ff9e1af` | `b5fe2f122d5ce875bdd511a62a6616d6e5c85f4d8a2855e06c8afc4a49ecd20b` | `97f6e5d18dca4bd060abb50479d14a5a215c17e7900d48cba250379ece3fe292` |
| Windows host UBSan traps | `68e2e3e8382e464f903799dbc0a3f9ee` | `d83427af41fcb68239329ca5ab4ecb64b4969bf029d8f9609d24779fdb7c4868` | `c57ba2d4fe87bba9d9d8151f7d257589d59e1cd628c65a88de06745b74814a2b` |
| Linux native | `7b355ce70f144969a51f4eed0cd4bf60` | `fe6302377b87af00a1a87e7d93e9aca6f4020fc3fa54e2313eccf6d53ad70352` | `5795d04670b5c4bd5df937871eeb09a60e7cd7f1544bbb20520ef00922214510` |
| Linux host ASan/UBSan | `f6008e9e7f9e4911885d0d775b7df9af` | `3fa92304137d93eca9296f5909e24a8336ba8b8016cd6fa206e3408f4d8690df` | `09705d06b8dba3c017c4579c3055b23f8a0ff82d4e4aaf062e14a159dc06175e` |

Each profile retains **33 process outcomes: 23 PASS / 10 FAIL**, including five
expected detector passes. Total: **132 = 92 PASS / 40 FAIL**, no runtime cases
silently skipped. There are 128 loaded-library identity records across the four
profiles; the four deliberately failed startup controls do not claim an active
audio interface. Native and host-sanitizer profiles load identical SDK bytes.
All ordinary recorded failures have the exact identity-retarget reason, old/new
ID 2, two accepted frames/two callbacks and recovered resources.

Sanitizers instrument the original host harness only; audio/SDL SDK libraries
are uninstrumented. Windows uses a calibrated UBSan trap profile because core
ASan is unavailable in the selected SDK profile. Linux uses ASan/UBSan with leak
detection and disabled vptr instrumentation for the SDK boundary. Custom SDK
allocators/library internals are not certified by host-only sanitizers. This is
one physical i5-11400 Windows 11/WSL Ubuntu 24.04 machine, not two machines or a
physical audio-device matrix.

## Synthetic costs and design implications

Three independent Release processes per case/mode/profile retain all raw
`Submit` call durations and whole-case microseconds. Each lifecycle process does
32 close/observer-progress cycles and 160 accepted submissions. There is no
separate discarded warmup: the first observations are retained. The following
native results use identical original inputs on the one host, with ordinary
background activity from the other contributor. They are not a controlled OS
comparison or a framework ranking.

| Native profile/mode | Three lifecycle elapsed times (ms) | Three per-run Submit medians (us) | Per-run p95 (us) | Maximum Submit (us) |
| --- | --- | --- | --- | --- |
| Windows timer | 171.076, 171.830, 172.099 | 1.000, 1.000, 0.800 | 3.600, 4.000, 3.300 | 23.300 |
| Windows SDL dummy | 553.405, 554.289, 555.428 | 0.700, 0.700, 0.800 | 4.200, 4.100, 4.200 | 30.500 |
| Linux timer | 170.601, 170.550, 170.648 | 0.547, 0.595, 0.507 | 3.780, 4.426, 3.941 | 69.519 |
| Linux SDL dummy | 676.870, 676.269, 675.697 | 0.541, 0.595, 0.566 | 3.964, 3.976, 4.539 | 10.435 |

Medians are the mean of the two central observations; p95 uses nearest rank
over 160 calls/run. Nanoseconds are storage units, not a nanosecond-resolution
claim (Windows observations are quantized). These numbers are independently
recomputed from retained records. Host sanitizer costs are separate; Linux
ASan/UBSan lifecycle Submit medians are 7.558–8.773 us, not native performance.
All maxima, including the Linux native 69.519 us observation, are retained.

Capacity cases take 3–8 us in the native runs. Queue/drain cases take roughly
26–28 ms with the timer and 42–43 ms with dummy; these include waiting for played
callbacks. Lifecycle elapsed times include opens, closes, queue discard,
observer callbacks and checker overhead. They exclude app startup. Driver
`seconds` additionally includes verification work and is not a process-latency
benchmark. Queue-case Submit samples include the one intentional full-queue
rejection; lifecycle samples above are all accepted frames. No audible latency,
sample mixing correctness, renderer/frame performance or title speedup follows.

Correctness/licensing are the first decision gates: raw-ID lifetime isolation
fails and must be handled before guest/local-profile integration. For performance
(30%), the nonblocking bounded queue and callback progress are measured here,
but no actual playback budget/comparative score exists. Stability (25%) has
repeated cleanup evidence with an explicit ownership gap; maintainability (20%)
favors consuming the existing approved SDK and retaining its failure rather than
adding a parallel audio implementation. Integration effort (15%) awaits an
agreed owner-token/guest-service seam; hardware compatibility (10%) is unknown
for real devices. Missing scores remain unknown. Do not optimize by skipping
ownership checks, adding callback reentrancy, spinning, or claiming an untested
backend is fastest. No architecture/SDK repair is made by this diagnostic task.

## Reproduce and integration handoff

From this isolated checkout, using an already approved native SDK preparation:

```text
python tools/test_sdk_audio.py --root <private-tool-cache> --sdk-report <approved-xma-manifest.json> --output-root <new-private-audio-cache>
python tools/test_sdk_audio.py --root <private-tool-cache> --sdk-report <approved-xma-manifest.json> --output-root <new-private-audio-cache> --sanitizers
python -m unittest discover -s tests/host_platform/sdk_audio -p test_*.py -v
python tools/check.py --config Release
python tools/check.py --config Release --sanitizers
```

The default repeat count is three. The SDK commands currently **exit 1**, with
the retained 23/10 outcome counts in each `manifest.json`; that is not a public
check failure to hide. Profiles/output/temporary/config/user roots and nonces
are fresh for every attempt/process. Builds use two workers; only captured own
processes can be terminated by timeouts. SDK/source/preparation caches are not
modified, and no physical audio endpoint/network service is used. No shared
startup, allocation, controller, runtime storage/audio or root CI/CMake edit.

Local public verification: Windows Python 3.12.14 / CMake 3.31.6 / MSVC 19.44,
`check.py --config Release`: **177 tests, eight explicit skips; parser CTest
1/1 PASS**. Linux Python 3.12.3 / CMake 3.28.3 / GCC 13.3,
`check.py --config Release --sanitizers`: **177 tests, two Windows-only skips;
parser CTest 1/1 PASS**. Eleven of those Python tests cover this diagnostic's
evidence guards without loading an SDK. The private harness uses the separately
pinned Clang compiler and sanitizer profiles above. Public green checks do not
turn a failing private SDK suite into passing ownership/audio compatibility.

Next steps require separate agreed scopes: protect lifetime/profile ownership
before raw stream reuse; decide any SDK interface revision explicitly; then
admit audited guest services only after the supported startup/scene prerequisite.
Real XMA decoding, mixed-output capture/channel/order checks, human listening,
pause/resume, long sessions and physical device loss/recovery remain needed for
MW3-082. The forced-exit control crash remains a retained limitation outside the
normal shutdown contract. Self-review only; no independent review is claimed.
