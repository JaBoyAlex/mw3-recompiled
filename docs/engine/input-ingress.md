# Controller observations and explicit local owners (MW3-087)

`runtime/input/ingress` is an original GPL-3.0-only C++20 component that composes
typed controller observations with the unchanged [MW3-080](input-slots.md)
four-slot router. A separate diagnostic proves this flow through the actual
repaired SDL3 provider using original virtual devices. It does not bind guest
services, integrate title execution or validate physical controllers.

## Caller and ownership contract

One polling thread owns a `ControllerIngress` and every call. Supply a nonzero
session unique among objects whose observations can intermix; never reuse that
session while old input can arrive. Copying/moving is disabled. The component
has sixteen bounded connection records and four owner slots. Those are storage
capacities, not retail mode or physical-device limits. No allocation, locks,
file access, OS polling or SDK dependency occurs in the public component.

The caller validates backend availability and discovers actual connected
device IDs. An ID is opaque and meaningful within that backend lifetime.
Discovery returns a `{session, incarnation, device}` token. Repeated discovery
of an active ID is idempotent; removal/restart followed by ID reuse creates a
fresh incarnation. Exhaustion fails closed without wrapping or evicting another
device. The 64-bit exhaustion branch is reviewed, not reached by forcing private
state. Tokens detect stale input; they are not authentication, account identity,
persistent hardware identity or permission to claim another player's device.

| Operation | Behavior |
| --- | --- |
| `reserve(slot, owner)` | Delegate explicit owner reservation to MW3-080 |
| `join(slot, owner, token)` | Validate the active connection and match the reservation; return its ownership `Binding` |
| `publish(binding, observation)` | Validate source/session/incarnation and matching bound device; normalize a complete typed frame; delegate binding/sequence validation and publication |
| `remove(token)` | Neutralize that connected route and invalidate its source token, retaining its owner reservation |
| `restart()` | Invalidate all connection tokens and neutralize routes while preserving owners and the monotonically increasing incarnation counter |
| `release(slot, owner)` | Explicitly release ownership; a new attachment invalidates old ownership bindings |

There is no automatic join, owner selection from enumeration position or SDK
user number, device-identity guess, shared-user merge or idle user-0 fallback.
State queries inspect slots; a valid slot index always has a state. A zero
frame and retained owner with `device == 0` describe a disconnected reservation,
not a readable physical player. Sixteen observed sources do not become sixteen
players. A fifth owner slot is rejected by the existing four-slot contract.

Capture the `Binding` with each queued observation and keep that association
until publication. Never relabel old observations with a new owner's binding.
Source tokens guard connection lifetime; ownership bindings guard assignment
lifetime. The caller must signal removal when a read becomes unavailable and
call `restart` when the backend stops/restarts, before admitting reused IDs.
The component cannot infer a backend restart that its caller does not report.

Default-constructed discovery/join/results fail closed. Use `result.ok()`;
`routing_status` is present only for `routing_rejected` and preserves the
underlying MW3-080 diagnostic. Source, frame and routing rejections leave all
slots unchanged and do not consume an observation sequence. Sequence numbers
are caller-owned nonzero increasing 64-bit values within a binding, independent
of SDK packet counters; wrap and replay reject. A fresh binding restarts them.

## Control normalization and policy

The original host `Control` bits name south/east/west/north, dpad directions,
start/back, stick presses, shoulders and guide. SDK/Xbox button masks are mapped
explicitly in the SDK-facing adapter, never copied into the host frame or
assumed to be a guest ABI. Unknown host bits reject before publication. The
adapter also diagnoses unknown SDK button bits rather than dropping them.

Four signed 16-bit stick values are already positive right/up at this boundary.
Negative values divide by 32768 and nonnegative values by 32767. Both endpoints
and zero are exact. Two unsigned 8-bit triggers divide by 255. No additional Y
inversion, deadzone, smoothing or clamping is introduced. The selected provider's
bitwise Y inversion and quantization remain observable, including a small
nonzero center if the provider reports -1. A removed route is explicitly fully
neutral regardless of its previous values.

The raw-driver seam supplies raw input and does not implement the separate SDK
input-system's UI-blocking, consumed-held-button, shared-pad or idle policies.
Physical integration MW3-083 must select and validate those policies alongside
ownership. Controls held before SDL's first open, mapping reloads and physical
reconnect identity remain outside the demonstrated guarantee. See the
[snapshot repair limits](input-snapshot.md).

Pinned SDL deliberately stretches guide-button events to a minimum 250 ms.
The control-map test verifies that its original virtual joystick guide source
is released, then pumps and reads the actual SDK until the guide event releases,
with a one-second deadline. Only the guide can remain pending in that interval;
the other fourteen named buttons retain immediate-release assertions. No SDK
state is forced or treated as neutral prematurely. Each guide observation is
recorded and required by the result protocol. These timings describe this
controlled SDK policy observation, not physical or title input latency.

## Verification and reproduction

Public C++20 contracts cover normalization, four explicit nonordinal joins,
unchanged/changed routes, wrong sources/owners, malformed/default results,
removal/reused IDs, backend restart, sequence limits and the sixteen-source
budget while four owners hold input. All 24 discovery orders are repeated
32 times: 768 synthetic scenarios, including reverse removal and late input.
Eight CTest cases, an exact deliberate wrong-route failure and missing/unknown
argument controls run from Python discovery. Thirteen additional Python guards
exercise strict schemas/nonces/counts, rejected-output cleanup, guide deadlines,
wrong libraries, protected SDK output roots and actual incomplete/late owned
children. These guards do not load a controller or SDK.

The private SDK-facing C++23/Clang 20 adapter reuses only the unchanged original
MW3-084 host helpers, not provider implementation code. It loads the real
versioned provider factory/driver and serves its actual settings/logger/UI
dispatcher and allocator interfaces. Physical backends are disabled before SDL
initialization and the initial inventory must be empty. All devices, callback
storage, process handles, temporary/configuration directories and outputs belong
to this diagnostic. Existing SDK sources, builds, packages and other lanes are
read-only. The maintained public component is independently compiled as C++20.

Six positive cases run forward/reverse, plus one exact wrong-route control per
round: held input before first SDK discovery, all 24 attachment orders, hotplug
and late SDK/host events, actual SDK device-ID reuse across complete driver
restart, explicit rejection behavior, and all fifteen named button mappings
plus opposite stick endpoints/intermediate trigger quantization. Every device's
destination is an explicit test-owner choice unrelated to enumeration order.
The native SDK guide/axis/trigger values are compared with original stimuli
before inspecting the normalized owner frame.

Every process emits one nonce-bound actual loaded-library record and one
complete cleanup footer. Wrong-route controls validate normal cleanup, emit a
separate rejection footer and fail with exactly the required diagnostic/exit 1.
Arbitrary errors, crashes, timeouts, duplicate/stale/partial records, mismatched
libraries and sanitizer findings cannot count as accepted controls. The runner
binds sources, itself and its helper, compiler, CMake cache/compile commands,
executable, preparation and complete SDK tree before/after the suite. Output
roots overlapping SDK preparations or source inputs are rejected before writes.

```text
python tools/check.py --config Release
python3 tools/check.py --config Release --sanitizers
cmake -S tests/host_platform/input_ingress -B out/ingress -DCMAKE_BUILD_TYPE=Release
cmake --build out/ingress --config Release --parallel 2
ctest --test-dir out/ingress -C Release --output-on-failure
python tools/test_input_ingress.py --root PRIVATE_CACHE --sdk-report INPUT_SNAPSHOT_RECEIPT --output-root EXCLUSIVE_OUTPUT
python tools/test_input_ingress.py --root PRIVATE_CACHE --sdk-report INPUT_SNAPSHOT_RECEIPT --output-root EXCLUSIVE_OUTPUT --sanitizers
```

Use `-DMW3_INPUT_SANITIZERS=ON` in a separate native build directory for GCC/Clang
ASan/UBSan or MSVC Release ASan. The MSVC ASan runtime directory must be on PATH.
SDK diagnostics require the existing verified input-snapshot preparation; they
create no new SDK profile and do not admit an unpatched XMA package by default.

## Performance, provenance and limits

The component performs bounded scans of at most sixteen source records and
four owner slots and normalizes six integer channels per accepted observation.
It adds no polling, allocation, locks or I/O to the ownership model. SDK reads
remain in the adapter/caller. No title runtime is integrated and no gameplay
performance benchmark, comparative speed ranking or general race-freedom claim
is made. Diagnostic durations include compilation and full artifact hashing.

All maintained component, adapter and runner code is original GPL-3.0-only.
The selected private SDK retains its reviewed BSD/Xenia provenance and SDL zlib
license. No SDK implementation, binary, game bytes, guest address or private
trace enters Git; no game-linked distribution permission is asserted.

Linux host and participating base/provider ASan/UBSan are exercised; SDL remains
native and the SDK input-system is not loaded. Windows SDK libraries remain
native with calibrated host UBSan traps; the public C++20 component also has a
separate MSVC ASan run. Vptr and Windows SDK/core ASan coverage are unavailable.
WSL is the same physical computer, not independent Linux hardware. Four
physical controllers, title input, guest ABI/services, rendered frames, mode
parity, console split-screen and four-player Survival are not verified.
MW3-083 and MW3-012 remain open. Owner self-review is recorded; no independent
review is claimed. The main allocation/PPC instance's work remains untouched.

## Recorded evidence, 2026-11-19

All five final suites report PASS/exit 0: **70 processes, 60 positive cases and
10 exact wrong-route rejection controls**. All 70 actual loaded-library records
and cleanup footers reconcile, including controls. The counters total **1,250
original virtual-device cleanup callbacks across 310 complete driver/SDL
lifetimes**. The 24-order cases include 240 complete lifetimes. No sanitizer
finding occurred in the exercised coverage.

| Profile | Private result receipt SHA-256 | Executed binary SHA-256 |
| --- | --- | --- |
| windows-native | `3951a46a7997113a26581837cda843f9f71768073a6d43cd2ce811907d84fefa` | `b24ac58c822a0b770c27dd4b38e28bfefe27eb596a4b1f5936f2ae30c731a80d` |
| windows-host-ubsan | `c333953800b69e6a6d8f7dc65fcc44c2f2dd302f962021e02cfdb1fdd976517f` | `776201e992ee5626cb4f3e7f3e9391155e11a43dba7631eca26ec415fea04a69` |
| linux-native | `43ab52899a6361c55a3624bd426c30b1a7bf76a57f21792da5157cc99d7aac9c` | `fd336830f09fef98e1a2710b961f6fe036144143f084dee5235f7d2a9de6e458` |
| linux-host-asan-ubsan | `3d3df57b870e837fe3a825669f4290133b8ce031cadb1061c2f198e0a25393bd` | `2a2f21d60b3736a3c6b81dedcfd4de61a6030218cea75fe59d1346e9514aaa02` |
| linux-core-provider-asan-ubsan | `0fbb0dfefcd42b6d2093785144fc85e2d61ff053b30d144a695231a30fb77902` | `c8fce060ea3ee5ba11291e6d2f6b1bd276516bac2e6743a41153d7bb04766ef0` |

All profiles execute the same original staged source bytes:

| Compiled input | SHA-256 |
| --- | --- |
| `baseline-contracts.cpp` | `52c59cf00517a5367046fcbfadeab011aad293314d08582575a031751fb207e4` |
| `CMakeLists.txt` | `272630f2bf68df092eca98ced403e1ad4fdcb507e10e5031ee860f6fb6f5e86a` |
| `sdk_contracts.cpp` | `7f715013918bc0296686a6cfb1870a77ec30350a6dcff1c6ce8092194915ec68` |
| `runtime/input/slot_router.cpp` | `bb4972d2fd04c15f1d2f6b58d35009d8602f103cb2c4a2c292b35bcbe74c1fd4` |
| `runtime/input/slot_router.hpp` | `0d417ca944521c64b0cd3734f08574411aecd2b8c0e3f78f895008c7dec062e4` |
| `runtime/input/ingress/ingress.cpp` | `0b1c31c4d586eef2e43b21b4b6a6794c7f38cdb30510d5670929aa3e38a02104` |
| `runtime/input/ingress/ingress.hpp` | `b92374b21002d03de82d35d509703ceabfa085ee981aab4a5608a458c85cb01f` |

Runner SHA-256 `a83ca8fdd5e75504636919481bb567748de4722fc0baf85b9a3d9a6206cbd39e`; unchanged helper SHA-256
`6c7a9073f09e5a9ef95c159d6d600b80548b46bcf4ac9be1655d8a4c5e605c3d`.

Provider/SDL/base files are the unchanged verified [MW3-086 preparations](input-snapshot.md):
Windows receipt `64e2044b8cf0c02cc388d089eb62b1663b474477dba595ca7071c4088f5bf9f0`,
Linux native receipt `750fbccc3cd9bdf912eb9d84a1118aae8f2ed05a6f487e9e54c082ac2ea13b9b`,
and Linux base/provider-instrumented receipt
`de304e2f876260d35ac41137f1d9e7b7533484d01a86eb61c505d461a52c41b6`.
SDK base is `ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d`; SDL 3.4.14 is pinned to
`147a8ee32dbf9ac02f3794964490687b6bbda1bc`. Adapters use Clang 20.1.2. Their
actual CMake caches/tool hashes bind Windows CMake 3.31.6-msvc6/Ninja 1.12.1
and Linux CMake 3.28.3/Ninja 1.11.1, with no fast-math flags. Complete compiler,
cache, command, SDK tree, loaded-file and source identities remain in each
private receipt and the separate artifact audit.

The ten guide-policy observations all record the source released while the SDK
guide event initially remains pending; actual SDK release is observed after
250-251 ms in this controlled run. An earlier expanded matrix retained six
incorrect immediate-guide-release assertions across three profiles (42 process
observations). Inspection of pinned SDL's explicit 250 ms policy corrected the
fixture, with a guide-only one-second deadline and observed release. That
failed matrix and the first basic Windows flow probe are retained separately
and are not final acceptance evidence. No provider/runtime behavior was altered
to make the guide assertion pass.

Final public checks PASS on both hosts: **231 Python tests**, eight existing
Windows skips and two Linux Windows-junction skips, plus parser CTest 1/1.
All sixteen new Python/native checks run. Windows skips cover six existing
link/symlink privilege cases, a POSIX FIFO case and unavailable LLVM assembler/
objcopy. Native ingress CTest 8/8, exact wrong-route and argument controls pass;
Linux discovery instruments the public component with ASan/UBSan. Separate
Windows MSVC 19.44.35229.0 Release ASan also passes 8/8 and the exact negative
control with no PASS or sanitizer marker. Its executable SHA-256 is
`e8aba07beae9c2b6af6ffe3807061991a03d2a69b04ffc92299b1dced44b5726`.
An early MSVC fixture shift-width warning and a missing-Git-PATH subset command
were corrected before the final checks.

Private `.local/087-matrix-ledger.json` retains every exact command and output
path; `.local/087-audit.json` independently reconciles all results, source
bytes, actual libraries, compilers/tools/configurations and cleanup. SDK runs
use at most two host profiles/four compile workers, with no GPU/title suite.
All parent SDKs and the main instance's files/profiles/processes are unchanged.

Artifact audit SHA-256 `c829400aeaf15abcd7e1e72875283a399de757c87a49a6a92ba74fdbb0981bc1`.
