# Selected SDK user routing (MW3-085)

This investigation loads the actual private `rexhid` input-system module and
`rexhid-sdl3` provider through their exported versioned factories. Original host
code serves application requirements, an owned bounded event dispatcher and
the real SDK settings registry/logger. The SDK selects and initializes its
real SDL3 driver. No input-system/provider implementation, kernel object or
guest code is embedded in the diagnostic executable.

`tools/test_input_users.py` consumes the existing verified `xma-packet-v1`
package read-only and verifies source/package identities before and after each
suite. Each attempt has exclusive staging, temporary/configuration directories,
process handles, executable and logs. Source/compiler/configuration identities
and actual loaded input-system/provider/SDL/base library paths/hashes are
recorded. Physical SDL backends are disabled before initialization and initial
device enumeration must be empty. Only original process-local virtual devices
are attached, stimulated, vibrated or detached.

The SDK-facing adapter uses the established Clang 20/C++23 convention and real
cross-library host allocator forwarding. Maintained public core remains C++20.
The runner/evidence guards use Python's standard library. Original fixture
mechanics from MW3-084 are reused in this task's own `fixture.hpp`; the earlier
diagnostic and its frozen evidence are unchanged. No SDK, runtime model, guest
allowlist or another lane's code/profile/process is modified.

## Contracts exercised

Four original virtual descriptors have distinct identities and input patterns.
The fixture derives each SDK user's device from `GetPadInfo` vendor/product
values, checks all four are distinct owned devices, then compares that user's
readings with the device's actual stimulus. It does not equate user numbers
with device enumeration order, Xbox accounts or the MW3-080 owner reservations.

The normal established-connection cases first let the SDK discover its devices,
then send fresh original input. A separate correctness case deliberately holds
input before the SDK's first discovery; it retains any lost initial state as
a failure rather than weakening the established-connection checks.

| Case | Required observation |
| --- | --- |
| `fallback` | No virtual devices; successful neutral user-0 reading/capabilities, NotFound pad identity, no real connection callback, other users absent |
| `users` | Four owned routes with distinct held buttons/sticks/triggers, unchanged packets on unchanged reads, only the changed user's packet/state changes, capability filtering, motors routed to that user's original virtual device; invalid users rejected |
| `hotplug` | Disconnect SDK user 1, preserve other routes/readings, observe disconnect/reconnect callbacks, refill its hole, and reject a late removed-instance event; callbacks reenter GetState without deadlock |
| `blocking` | Nested UI blocks neutralize all input; one release keeps it blocked; final release restores axes while held buttons remain consumed until released and freshly pressed |
| `shared` | Explicit shared-pad mode merges original buttons into user 0; other users remain absent, so four source devices cannot masquerade as four independent users |
| `orders` | All 24 attachment orders, each with a complete module/driver/SDL lifetime and the independent-user checks; 96 virtual cleanup callbacks per process |
| `held-discovery` | SDL already reports held input before SDK discovery; the SDK must report the same stimulus after discovery and another event pump. A zero cached reading is a correctness failure |
| `wrong-routing` | Deliberately wrong device/button expectation is rejected with exactly the required failure marker and exit 1 |

The fixture balances all UI blocks, stops listeners, detaches only its own
devices and verifies cleanup callbacks, no pending dispatcher work and no
initialized SDL subsystems after teardown. Stopped input must reject even user
0; successful idle fallback is an active-system policy, not a stopped-system
success stub. The callback guard is removed before module destruction.

The default SDK policy supplies an idle user-0 reading and capabilities without
an assigned pad identity or a connection event. That is **zero routed devices**
and one readable fallback, not a connected player. Shared mode is one routed
SDK user with multiple source devices. Normal routing requires four distinct
owned pad identities. None of these policies establishes retail MW3 limits.

## Evidence protocol and known failures

Every process reports a nonce-bound loaded-library record before executing its
case. A successful correctness case additionally requires one complete record
with exact case/cycle/create/cleanup/user counts, quiescent state, SDL version
and matching library identities. Duplicate keys/records, stale nonces, coercions,
missing identities, wrong libraries, partial/late children and sanitizer output
cannot pass. Wrong-routing rejection is checked separately by exact exit and
diagnostic, without converting arbitrary crashes into accepted controls.

The runner preserves initial-held-state failures with `status: FAIL` in their
case records. It recognizes a narrowly defined observation only when the actual
SDL button/axis are held, the SDK returns zero for that assigned user, and the
exact correctness diagnostic occurs without a completion or sanitizer error.
The overall suite then reports **LIMITATION and exit 1**. This is retained SDK
failure evidence, not a correctness PASS. An unrelated failure makes the suite
FAIL/ERROR. A future SDK repair must make the original `held-discovery` case
pass; deleting the case or labeling neutral state successful is not a repair.

## Reproduction and limits

Use a dedicated private output root separate from SDK/content/profile trees:

```text
python tools/test_input_users.py --root PRIVATE_CACHE --sdk-report XMA_RECEIPT --output-root PRIVATE_USER_INPUT_OUTPUT
python tools/test_input_users.py --root PRIVATE_CACHE --sdk-report XMA_RECEIPT --output-root PRIVATE_USER_INPUT_OUTPUT --sanitizers
python -m unittest discover -s tests/host_platform/input_users -p "test_*.py" -v
python tools/check.py --config Release
```

Each suite executes seven cases forward/reverse plus one wrong-routing control
per round: sixteen processes. The core-profile run changes instrumentation of
the participating base library; input-system/provider/SDL remain native. Host
ASan/UBSan covers the Linux adapter; Windows uses calibrated host UBSan traps.
Vptr instrumentation is disabled and Windows core ASan remains unavailable.
This is not full external-module sanitizer coverage. Public CI executes the
synthetic evidence guards without requiring an SDK or controller.

Four physical controllers, independent physical Linux hardware, guest input
ABI/services, title input, original console split-screen and four-player
Survival are NOT RUN. WSL is one host observation. The SDK's automatic user
assignment remains separate from MW3-080's explicit owner/session contract.
Actual routing admission or a demonstrated SDK repair requires its own agreed
scope; this task does not silently replace the assignment system.

All maintained fixtures/runner code are original GPL-3.0-only. The private
SDK's reviewed BSD/Xenia provenance and SDL's zlib license remain unchanged.
No SDK, binary, game bytes or private log enters Git. There is no title benchmark,
runtime performance change, distribution clearance or independent review claim.

## Recorded evidence, 2026-11-19

**SDK correctness remains LIMITATION.** Five profiles execute sixteen processes
each: 60 established/fallback/blocking/shared/order positives and ten exact
wrong-routing controls are accepted; **ten initial-held cases fail**. Every
suite returns LIMITATION/exit 1. The failed SDK assertion remains enabled.
No sanitizer finding occurred in the exercised coverage.

| Profile | Result | Private receipt SHA-256 | Executed binary SHA-256 |
| --- | --- | --- | --- |
| windows-native | 12 positives, 2 controls, 2 retained failures | `f603e67a972fe5b60aa0ff5997513af432a889240697500da4e4fe5cd15f37d3` | `fdc1c59c6f178e93cf0485a8cfab601dbc465510dc59aeeb64ca60598eeb88f1` |
| windows-host-ubsan | 12 positives, 2 controls, 2 retained failures | `98963344f0ae574c44c5c590b36faccc2428aea711fa90ae1d9887af0feb282d` | `98b16f6eb500aadafde48ae66ebbd4dbd57b1133dd1433fb1f0109df6aab5481` |
| linux-native | 12 positives, 2 controls, 2 retained failures | `8a7793294e16efa273b239125e760ac96b0254e8ba8d85466c56cb959121ed6c` | `78d77eeb4a3f3c4111097f1a2f6048c2f3e04a696238c1ef90e8c49f5d420533` |
| linux-host-asan-ubsan | 12 positives, 2 controls, 2 retained failures | `3775ba563e0a8c6a1c2fd64df90af999a5b74ac72ebbfcafeaef998ed08dd79f` | `796a181da3a0b2783ff578f3230f4c5e4a7277e811427e86f7f1ca6f05cc9560` |
| linux-core-asan-ubsan | 12 positives, 2 controls, 2 retained failures | `ae9b7a9dc6187ed39aff8aafc218eb71b71faa5e01f5f1f6b4ae095511d11514` | `38b84d9982bf0f3bd31a6bdd56e02cc91fe2736404e2d01fba477685b6e15902` |

All ten failures report this controlled contrast: assigned SDK user 0 identifies
original virtual product 3, SDL button=1 and X=3072, but SDK buttons=0 and X=0
(expected SDK button bit 16384). The fixture checks the actual SDL stimulus
before asserting SDK results, and services another event pump. The assertion
stops at the first mismatched user; this is not a measurement of every user
or physical hardware. Established connections receive new stimuli after
discovery and pass their separate cases.

The independent artifact audit reconciles all 80 log hashes and nonce-bound
loaded-library records, five executable/compile-command records, identical
staged sources and exact SDK trees. It reports evidence-integrity PASS and
SDK-correctness LIMITATION as separate values. All five profiles use the same
runner SHA-256 `88a51dc4ef40bba7e0d181895fb73e205a2f1a78edadb827bc7198f4a84665d7`.

Compiled original source identities:

- `contracts.cpp`: SHA-256 `893a2d61e3cb7db012bc7409d1ce345105d81d6106fe3df9dc647f621e6b88d2`.
- `fixture.hpp`: SHA-256 `d01dd001bfaa1e30371dbd3d600c13a31b92ad45bdcc6891ae28d1d3b1b6eb69`.
- `CMakeLists.txt`: SHA-256 `7a1b427de3d9872fe115dd0e7bc129536ab3cd31c116845cf2077f2f747aef4d`.

The actual input-system library SHA-256 is
`38afae273bf05002fe452f5af6294b7c51c53ee762f8e7de28180849f973421e` on Windows and
`7a2dbfd95abd530e7d766cf6697cebfaec79c93256886f6afa9987fe058b3f70` on Linux, including the
participating-base sanitizer profile. Provider/SDL/base identities and full
SDK trees are bound by each receipt; the inherited preparation limits remain.
SDK base commit is `ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d`, with reviewed
memory/stop/XMA compositions. SDL 3.4.14 remains pinned to
`147a8ee32dbf9ac02f3794964490687b6bbda1bc`. Clang 20.1.2 builds all adapters.

Public checks pass: Windows Release runs 181 Python tests with eight explicit
skips and parser CTest 1/1; Linux Release ASan/UBSan runs 181 tests with two
Windows-junction skips and parser CTest 1/1. Windows skips are six unavailable
link/symlink privilege cases, one POSIX FIFO case and missing LLVM
assembler/objcopy in existing suites. All fifteen new synthetic evidence guards
run without an SDK. These checks do not erase the private SDK failure.

The first fixture incorrectly expected identity metadata for idle fallback; the
actual SDK intentionally returns NotFound. That harness failure is retained and
corrected against the interface/source behavior. Earlier zero-state failures
were preserved as the explicit held-discovery regression rather than hidden by
the established-connection initialization sequence. No SDK patch is included.

## Repair handoff

[MW3-086 planning](input-snapshot-plan.md) scopes a separate provider snapshot
repair and gates physical backend 083 on its validation. It must initialize
from actual current SDL state, preserve existing normalization/threading, and
make the unchanged held-discovery case pass. It uses a new derived source/build/
package, preserves all current SDKs, and serializes shared runner changes after
084/085. The allocation and audio lanes remain separate. A completed bounded
investigation does not certify the failing SDK or pass a gameplay gate.

Owner self-review is recorded; no independent review is claimed.
