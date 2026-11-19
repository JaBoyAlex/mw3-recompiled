# Original host input ownership (MW3-080)

`runtime/input/slot_router.*` is an original GPL-3.0-only C++20 component.
It has four host routing slots and no platform/SDK dependency, allocation,
file access, guest addresses or button mapping. Four is its capacity, not
evidence of a retail mode's player limit. MW3-083 owns the future physical
backend; MW3-012 still requires actual title input evidence.

## Caller contract

One polling thread owns a router and all calls. There is no synchronization.
Construct it with a nonzero session ID unique among routers whose events may
intermix, including destroyed/recreated routers. The caller must not reuse
that identity while old events can arrive. Zero disables all mutations with
`invalid_session`; copying/moving a router is prohibited. Tokens are ephemeral
stale-event guards, not an authentication boundary or save/profile format.

Owner and device IDs are nonzero opaque host values. The backend must retain
device identity during a connection and explicitly distinguish new device
incarnations; enumeration order cannot select a player. No Xbox account,
guest controller, SDL or XInput identity is inferred.

| Call | Successful behavior | Rejections |
| --- | --- | --- |
| `reserve(slot, owner)` | Explicitly reserve a vacant slot; same owner is idempotent | Invalid slot/zero ID, another owner, owner reserved elsewhere |
| `attach(slot, owner, device)` | Match the reservation and return a session/slot/generation/owner/device binding | Wrong owner, occupied device, duplicate connected device, zero ID, exhausted generation |
| `apply(binding, sequence, frame)` | Replace the complete normalized frame and sequence | Stale/mismatched binding, zero/nonincreasing sequence, invalid frame |
| `disconnect(binding)` | Neutralize all input and sequence; keep owner reserved | Stale/mismatched binding |
| `release(slot, owner)` | Explicitly neutralize and release an owner's reservation | Wrong/zero owner |
| `state(slot)` / `slots()` | Copy one state or inspect a const view of all four | Invalid single-slot query returns no value |

Successful repeated attach returns the existing token without clearing input
or its sequence. Disconnect frees the physical device ID for an explicit
assignment elsewhere, while its local player's reservation stays intact.
Disconnecting an already disconnected binding is a diagnosed stale event.
Release retains the generation counter even if the same owner/device returns.
Only a new attachment increments it; disconnected bindings are already invalid.
At its unsigned 64-bit maximum, a new attachment fails closed rather than
wrapping. That practically unreachable generation-exhaustion branch is reviewed,
not reached by forcing private state in the tests.

Every binding check precedes input changes. Sequence numbers are nonzero
unsigned 64-bit values, strictly increasing within a binding. Gaps are allowed;
wraparound is rejected. A fresh binding restarts the sequence. Rejected samples
do not consume a sequence number. Buttons are opaque bits; four axes must each
be finite and in [-1, 1], and two triggers finite and in [0, 1]. A frame is
validated completely before publication. No clamping, partial frame update,
button remapping or guessed guest memory write occurs. All rejected operations
leave every slot unchanged. Local owner IDs do not provide account security.

## Verification

The standalone native test project is `tests/host_platform/input_slots`.
Root Python discovery builds it with at most two workers and runs seven CTest
cases plus exact wrong-result and missing/unknown-case rejection controls.
Linux discovery enables ASan/UBSan; Windows discovery uses MSVC Release.
Unavailable CMake/CTest is an explicit class skip, not a passing native suite.
The normal CI environment supplies both tools.

| Case | Observable check |
| --- | --- |
| `four-slots` | Four distinct held input patterns; idempotent attach/reserve leaves states intact |
| `assignment-guards` | Duplicate owners/devices, takeover, unreserved attach, invalid IDs/indices; every rejected operation preserves all slots |
| `disconnect-reconnect` | Neutral input, retained reservation, late disconnect/sample rejection, explicit release/reassignment |
| `stale-sessions` | Identical local generations in different sessions; malformed tokens and disabled router |
| `frame-validation` | Each axis/trigger with NaN, infinities and out-of-range values; valid edges and unchanged sequence after rejection |
| `sequence-limits` | Zero, duplicates, reverse order, UINT64_MAX and rejected wrap, restart only after reconnect |
| `event-orders` | All 24 slot orders, 32 repetitions each: 768 original scenarios with reverse disconnects, late events and independent input |

The negative control publishes a valid input then compares it with deliberately
wrong buttons. It must exit 1 with exactly `FAIL: deliberate wrong-result rejected`
and no PASS marker. Missing/unknown cases must exit 2 with their exact diagnostic.
Neither a crash nor an arbitrary nonzero result satisfies those controls.

Reproduce the public check with `python tools/check.py --config Release` on
Windows and `python3 tools/check.py --config Release --sanitizers` on Linux.
For a standalone build, run:

```text
cmake -S tests/host_platform/input_slots -B out/input -DCMAKE_BUILD_TYPE=Release
cmake --build out/input --config Release --parallel 2
ctest --test-dir out/input -C Release --output-on-failure
```

Use `-DMW3_INPUT_SANITIZERS=ON` in a separate build directory for instrumented
contracts. MSVC supports address instrumentation here (use Release without
`/RTC`); this project does not claim Windows undefined-behavior instrumentation.
GCC/Clang builds enable address and undefined instrumentation together. Keep
the MSVC ASan runtime directory on PATH when running its standalone binary.

### Recorded local matrix, 2026-11-19

| Platform/configuration | Result |
| --- | --- |
| Native Windows x64, MSVC 19.44.35229.0 Release, Python 3.14.10, CMake 3.31.6-msvc6 | Public checks PASS: 141 Python tests, seven explicit skips, parser CTest 1/1; nested input CTest 7/7 and exact failure controls PASS |
| Linux x64 / WSL Ubuntu 24.04, GCC 13.3.0 Release ASan/UBSan, Python 3.12.3, CMake 3.28.3 | Public checks PASS: 141 Python tests, one explicit skip, parser CTest 1/1; nested input CTest 7/7 and exact failure controls PASS |
| Native Windows x64, same MSVC, standalone Release ASan | Input CTest 7/7 and exact wrong-result control PASS; no sanitizer findings |

Windows skips are one POSIX FIFO case, one unavailable LLVM assembler/objcopy
case and five unavailable symlink-privilege cases in pre-existing suites.
Linux skips only the Windows junction case. No input test is skipped. Windows
undefined instrumentation is NOT RUN with this MSVC toolchain. Linux is one
WSL host, not evidence from an independent physical Linux machine.

The separate Windows ASan build uses these exact commands (with its compiler
runtime directory on PATH):

```text
cmake -S tests/host_platform/input_slots -B out/input-windows-asan -G "Visual Studio 17 2022" -A x64 -DMW3_INPUT_SANITIZERS=ON
cmake --build out/input-windows-asan --config Release --parallel 2
ctest --test-dir out/input-windows-asan -C Release --output-on-failure
out/input-windows-asan/Release/slot-router-tests.exe negative-control
```

The last command has the expected exit 1 and exact diagnostic above. Its
executed binary SHA-256 is
`b030b812791175ee1f7aece690e2e1e4a21e912cf183541356aaab84c65b56f3`.
Both platforms executed these same original source bytes (SHA-256):

| File | SHA-256 |
| --- | --- |
| `runtime/input/slot_router.hpp` | `0d417ca944521c64b0cd3734f08574411aecd2b8c0e3f78f895008c7dec062e4` |
| `runtime/input/slot_router.cpp` | `bb4972d2fd04c15f1d2f6b58d35009d8602f103cb2c4a2c292b35bcbe74c1fd4` |
| `tests/host_platform/input_slots/contracts.cpp` | `d3e7d951b067b2faf67359008d8bb1e5a4119204edbcc0f1ac4c3311dcfb1f7e` |
| `tests/host_platform/input_slots/CMakeLists.txt` | `b11058aeab734483a9017c22f93f17000250f7cabd94fd7dd3304d0c634b539b` |
| `tests/host_platform/input_slots/test_native.py` | `a09ea30a8e933cd917539fea7293d45960556332c80db409683e27ec5172c8fc` |

## Scope and performance

All fixtures are original synthetic host data. No controller hardware or
actual MW3 input path was exercised; no guest mapping, rendered frame, console
split-screen, mode parity or four-player Survival result is established.
The backend must provide assignment UI/policy, normalized values, unique session
and device IDs, event serialization and any needed synchronization. Guest
integration or a shared model API change requires its own agreed task.

State is bounded to four slots. Reserve/attach inspect at most four entries;
other mutations and queries are constant bounded work with no I/O, locks or
heap allocation. This component is not integrated into title execution and
has no measured title performance impact or claim to be the fastest approach.
Compiler flags must preserve finite-value checks; fast-math is not supported.
Owner self-review is recorded; no independent review is claimed.
