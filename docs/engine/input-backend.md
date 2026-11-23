# Explicit-owner SDL controller adapter

MW3-089 implements the C++20 host adapter in `runtime/input/backend` using the
unchanged MW3-080 slot router and MW3-087 ingress. It adapts suitable MW2 C++
input handling to actual SDL3, with explicit owner joins, stable reservation
semantics and diagnostic failure cleanup. This completes the host-adapter task;
physical-controller MW3-083 and translated-title input remain unverified.

## Reused source and boundaries

Adapted source: [PaulCombal/mw2-recompiled input.cpp](https://github.com/PaulCombal/mw2-recompiled/blob/b3aa7d8ef184de8ec1f0d2fe7fa0e19a4c92b68b/runtime/kernel/input.cpp),
commit `b3aa7d8ef184de8ec1f0d2fe7fa0e19a4c92b68b`, source SHA-256
`89ed00f59eac2eae4b644ca8882d1c4b7382b854821ae94b5f43c286a8c07fc9`.
Its root GPL-3.0-only LICENSE SHA-256 is
`230184f60bae2feaf244f10a8bac053c8ff33a183bcc365b4d8b876d2b7f4809`.
`NOTICE.md` records attribution and modifications; the project's root LICENSE
preserves the full GPL text. Only suitable enumeration/open/connected/close,
named control reads, trigger quantization, Y complement and rumble usage are
adapted. No MW2 guest addresses, translated code, kernel/PPC types, UI/online
hooks, keyboard/scripts, global user-zero fallback or runtime are adopted.
This source-only contribution combines project GPL code with SDL's separately
preserved zlib notice; it supplies no game-linked binary distribution decision.

The adapter requires headers/runtime SDL 3.4.14, exact integer version 3004014.
The tested composition is the separate [MW3-090 repaired SDL profile](sdl-input-profile.md),
SDL commit `147a8ee32dbf9ac02f3794964490687b6bbda1bc`, patch SHA-256
`d10f46dca0729d468086015e75ba7e5591afc791056ed7983ccbfe225fb77b44`.
It preserves already sampled held triggers when opening a mapping. A version
number alone cannot authenticate this derivative: the private runner verifies
the selected profile, all package bytes and the actual loaded module path/hash
before accepting results. Existing runtime/provider SDKs are read-only and are
neither linked nor copied into this adapter's standalone SDL probe.

## Ownership, lifecycle and controls

One creator/main thread owns calls and destruction. The caller owns outer SDL
initialization/quit, ingress lifetime and player reservations. `start()` accepts
an empty ingress source domain, acquires one GAMEPAD subsystem reference and
rejects repeated starts. `stop()` balances that reference and only its own
handles/tokens, neutralizes disconnected sources and retains owner reservations.
Destruction of a running adapter on another thread violates its explicit
contract and terminates; ordinary wrong-thread operations return diagnostics.
The caller must not attach or publish these SDL sources through a second path.

Sixteen fixed entries retain handles and ephemeral device tokens. Discovery
does not assign players. The caller explicitly joins a token to an existing
slot/owner. Each joined sample carries its source incarnation and increasing
sequence. An idempotent join preserves sequence; stale/wrong-owner joins or
motor commands cannot steal a slot. Backend restarts issue fresh incarnations
even when SDL IDs survive. Tokens are stale-state guards, not authentication
or persistent physical device identities.

Polling pumps events without dequeuing the caller's event queue, enumerates at
most sixteen IDs, opens owned handles and obtains a complete sample under the
SDL joystick lock. Fifteen named buttons map to the existing host bits. X axes
remain signed 16-bit; Y uses complement inversion with an exact-zero special
case: 0 and -1 map to 0, and full endpoints remain full endpoints. Triggers
must be nonnegative SDL values and quantize by `value >> 7`. Unknown control
bits and negative triggers reject. An invalid sample, disconnect, sequence
exhaustion or ingress rejection drops that source instead of preserving stale
held input. Other sources continue, and the first diagnostic is returned.

Rumble checks the current slot/owner/generation/device binding before calling
SDL, rejects durations above 5000 ms and nonzero amplitudes with zero duration,
and explicitly stops owned active motors during connected-handle cleanup.
Capacity overflow reports a diagnostic without evicting held owners. These
bounds cover owned storage, opens and command duration. SDL's enumeration can
allocate internally; no fixed latency, allocation-free poll or performance
improvement has been measured.

## Actual-library evidence

Each of five profiles runs eight original virtual-device cases three times,
plus three negative controls: **135 owned processes**, comprising **120 ordinary
successes and 15 expected control rejections**. All profile drivers exit 0.
Windows/Linux are on one Windows host with WSL2, not independent machines.

Cases exercise four distinguishable devices held before the first gamepad open,
all fifteen button mappings and exact neutral, all 24 discovery orders with
nonordinal slots, hot unplug/reconnect, restart with surviving raw SDL IDs,
stale/wrong-owner routes, actual virtual rumble callbacks, seventeen-device
capacity pressure, wrong-thread rejection, caller event retention, double-start
and an existing caller SDL lifetime. Every completed record verifies four
retained owners, zero ingress sources/owned handles/SDL subsystem state after
cleanup, and exact created/cleaned callback counts. Each profile serializes
26 complete records, 422 matching created/cleaned callbacks, 826 checked slot
reads, 46 stale/wrong-owner rejections, 24 rumble callbacks and 12 stop callbacks.
The incomplete control intentionally has no completion record; no cleanup
counts are invented for it. The deadline child prints valid completion after
fixture cleanup, remains alive and is killed after eight seconds. Its valid
bytes alone cannot pass ordinary acceptance. Post-timeout process-exit leak
checking is not claimed.

Wrong-route deliberately asserts a distinguishable other device and must
produce the exact rejection and exit 1. Incomplete emits readiness but no
completion and exits 0; timeout returns the runner's -999 sentinel. Public
synthetic protocol guards reject stale/duplicate/partial records, wrong types,
resource/count mutations, sanitizer findings, wrong modules, overlapping output
and invalid preparations. They supplement actual SDL tests, not physical input.

| Profile | Receipt SHA-256 | Probe executable SHA-256 |
| --- | --- | --- |
| Windows native | `c6ccb0a14a02772f2b963e259b3685fa9898b6743b41281143a5ee694481cc76` | `9865c4455d4f8e3b39ca2829e7896a89f2c1fc107d92d2f48750cd166ab93a0b` |
| Windows host UBSan trap / native SDL | `9833fe3553e6562256f7e31e903f41c9cb92d498a362bc01ea2917cfd26951db` | `868113a686a6cb8df68d0de1afa295df4ebce5bc5b7c765cbc4a14d64627c955` |
| Linux native (WSL2) | `8530d8618b73b19fd7d614f695e0b69ff9aea3dd2e7bbb7543d7b1fd830e664c` | `b95462f505be1d97d978454f950a35d47d76165589980a6db7065ffef8f43f3a` |
| Linux host ASan/UBSan / native SDL | `2794a784399ae47deb66b45bc6579e631edd91bfa05b632897f983855e656654` | `6f33e17e04d4e293c6116613bd8565768e8ab6080a941e9f35bd627716979d1a` |
| Linux host + SDL ASan/UBSan | `4af6735761e22d44f804014afd9391e0c4bbacbabc5cc36cb5e2d444f41a355b` | `0b60cda256890b9217a5d81570ac4a4028245d27f6fc9acc14d77d174e1aec1e` |

| SDL composition | Loaded library SHA-256 | Preparation receipt SHA-256 |
| --- | --- | --- |
| Windows native SDL | `977edfe9afb58d71b0f59cca30cf2f954b2dd8742064eb96212570a203426f1b` | `65373f54c917ba905a52994c6431e24a144203239769996949be426c9d1507bc` |
| Linux native SDL | `7d6c3db645570cf239a8fc88de1beef778dde8ac2a2fbd40314427160747ff27` | `8abde429a2b0e70475e353c978beaf17c1eb8291d05c088b259a569d3471895e` |
| Linux instrumented SDL | `c91cec8e190ace4d13edf7d26c5250f105b03925c8ec4899e5383ddb18c1cc00` | `3289759e614a7b4287cd54a6629785942623e77994a8a6dcba1552f92c1303d8` |

Host compiler is Clang 20.1.2 (`-O2 -DNDEBUG -march=x86-64-v2`, C++20, no
fast-math). Windows uses MSVC environment 14.44.35207 / Windows SDK 10.0.26100.0,
CMake 3.31.6-msvc6, Ninja 1.12.1 and lld. Linux uses CMake 3.28.3, Ninja 1.11.1,
GCC 13 headers/runtime and lld 20. Windows's instrumented adapter has UBSan trap
coverage with native SDL. Linux has both adapter-only and participating-SDL
ASan/UBSan profiles with leak checking on normally exiting processes. Windows
participating-SDL instrumentation and native OS/hardware libraries are not
covered by those Linux profiles. Exactly four owned C++ translation units
(probe, backend, ingress, router) compile; no selected SDK/provider/kernel TU
is present. Full compiler/tool hashes, flags, caches, compile commands, source
trees, actual modules, per-process nonces and raw logs remain private receipts.

## Reproduction and source identity

From this task's worktree, the exact local driver form is:

```text
python tools/test_input_backend.py --root <runtime-root> --sdk-report <sealed-090-output>/manifest.json --output-root <private-cache>/input-backend-089 [--sanitizers]
```

Default repeat count is three. Windows root was
`C:/Users/alexb/.cache/mw3-recompiled/windows`; Linux root was
`/home/mojo/.cache/mw3-recompiled/runtime-bakeoff`. The sealed 090 output IDs
were `fe8911b615cf4c38ae7721a449d1b4fa` (Windows),
`74a72efb06f34bae80a5b567d9caa718` (Linux native SDL) and
`486248bb939346e1a76588029383f313` (Linux instrumented SDL), under each host's
private `sdl-input-090` cache. Both native SDL outputs run with and without
`--sanitizers`; the instrumented SDL output requires it. Exact expanded build
and child commands are retained in each sealed receipt. All writable profiles,
temporary directories and subprocess handles belong to that invocation.

Runner SHA-256 `5b452e0f9f39113dcc879a181313d13b6f86d2c1fe572ae9c396ab47461fb24e`.

| Maintained input | SHA-256 |
| --- | --- |
| `CMakeLists.txt` | `2b1f355083b0c366002ac1812534f0e7dee5855264ddd2e4a5fb51086ba368e3` |
| `contracts.cpp` | `8483a80919dd6074789fa8999b4d87c21e767cd217d12c86c0b21716dd41ecf2` |
| `runtime/input/slot_router.hpp` | `0d417ca944521c64b0cd3734f08574411aecd2b8c0e3f78f895008c7dec062e4` |
| `runtime/input/slot_router.cpp` | `bb4972d2fd04c15f1d2f6b58d35009d8602f103cb2c4a2c292b35bcbe74c1fd4` |
| `runtime/input/ingress/ingress.hpp` | `b92374b21002d03de82d35d509703ceabfa085ee981aab4a5608a458c85cb01f` |
| `runtime/input/ingress/ingress.cpp` | `0b1c31c4d586eef2e43b21b4b6a6794c7f38cdb30510d5670929aa3e38a02104` |
| `runtime/input/backend/backend.hpp` | `bcee1db42d71b645a07040a5d35af453cbdeccf216512ae680938e11555f1a81` |
| `runtime/input/backend/backend.cpp` | `a64c61c2cace5887538e9ed3c900849f3a1e3a61f9122a192b507e58c84fd067` |
| `runtime/input/backend/NOTICE.md` | `09d8f3ec67d5a71277302fd9d18aae7ad814d540761fba9bab7c91402dbc3417` |

A separate standard-library audit rehashes staged/current sources, producer and
helpers, tools/versions, all recorded artifacts, exact compiled file set/flags,
binary/cache/compile commands, prepared source/package/library/receipt and all
135 logs/nonces/results. It separately checks expected case geometry, typed
resource counts and control exits. This is a second evidence reconciliation by
the same owner, **not independent human review**. Source/contract/lifecycle and
license review are likewise transparent owner self-review.

Public checks: `python tools/check.py --config Release` on Windows and
`python3 tools/check.py --config Release --sanitizers` on Linux both PASS:
**298 Python tests**, eight/two existing skips, parser CTest 1/1. The ten new
Python checks include the four native conversion CTest cases, exhaustive
65,536-value Y inversion and 32,768-value trigger quantization, exact wrong
neutral and argument controls, and seven protocol-driver tests. Windows skips
are existing link/symlink privilege, POSIX FIFO and LLVM utility availability
cases; Linux skips are the two Windows junction cases.

## Retained failures and remaining gates

Initial probes against unchanged 086 SDL exposed lost first-open held triggers,
retained as failures. They led to separately reviewed MW3-090, not weakened
input expectations. Development also corrected an expected Linux loader path
from the unversioned link to the actual `.so.0` SONAME and retained an initial
Windows run invalidated by source edits during development. None is final
acceptance evidence. Final five-profile sources were frozen and match the
published implementation bytes.

Guide release is observed with at most a one-second guide-only wait if SDL
still reports it; direct gamepad polling can release immediately. This is not
proof of identical timing to the SDK event-based guide pulse policy.
No four physical controllers are available in this session. MW3-083 stays open.
This component has not been installed into the SDK UI/input provider, admitted
to translated guest input, or exercised in an MW3 menu/frame/mode. It changes
no guest service allowlist, selected runtime/renderer, GPU/title acceptance or
playable-boot status. Physical mappings/rumble, independent Linux hardware,
console split-screen, four-player Survival, gameplay and performance remain
separate evidence requirements.
