# Selected SDL3 input provider investigation (MW3-084)

The original fixture in `tests/host_platform/sdk_input` loads the actual private
`rexhid-sdl3` provider through its exported versioned factory. It obtains the
registered `IInputDriver` and calls its real enumeration, state, capabilities,
vibration and shutdown methods. It links the selected base library and SDL3;
no provider, kernel or guest object implementation is embedded in the test.
`tools/test_sdk_input.py` verifies the frozen XMA-profile SDK and its parent
identities before and after each suite, preserving every attempt privately.

The existing SDK-facing adapter convention requires Clang 20 / C++23 for
`rex::Result` and the SDK headers, as in the memory/thread diagnostics.
Maintained public core remains C++20 and the Python driver uses only the
standard library. The executable must use the SDK's real host allocator
forwarders (`rexglue_link_host_allocator`) for cross-library C++ ownership.
Those upstream source files remain private SDK inputs, bound by its receipt.

## Fixtures and boundaries

Each process starts with private SDL state and creates four SDL virtual
joysticks. Physical HIDAPI, RawInput, DirectInput, WGI, XInput, IOKit and Linux
classic backends are disabled before joystick initialization. Initial device
enumeration must be empty. No physical controller is assigned, vibrated,
detached or reconfigured; every subsequent action targets fixture-owned IDs
and handles. Unexpected devices fail the fixture. SDL virtual devices belong
to this process and do not create OS-wide gamepads for another lane.

Original names and distinct virtual descriptors (`vendor=0xffff`, products
1–4, synthetic values only) distinguish the pads without relying on enumeration
order. Names alone are insufficient because otherwise identical virtual
devices can share an SDL mapping/name. Stable names identify the fixture's
devices; the real provider supplies their opaque raw IDs. They are not Xbox
accounts, persisted profiles, MW3 guest addresses or model owner reservations.

The owned dispatcher actually executes callbacks on its polling thread and
drains queued work with a fixed budget. It rejects a foreign thread rather
than returning success without execution. It provides the real SDK settings
registry/logger; mappings-file loading is explicitly empty. Child temporary
and configuration directories are private, external SDL/runtime environment
overrides are removed, and the driver uses isolated output directories and at
most two build workers. It changes no SDK source, preparation or shared model.

| Case | Required observation |
| --- | --- |
| `four-devices` | Exactly four distinguishable unique raw IDs; capabilities and original virtual rumble callbacks; zero/UINT64_MAX state, capability and vibration IDs return NotFound |
| `state` | Four different held face buttons and stick positions; full-range Y inversion and trigger endpoints observed through the real driver |
| `reconnect` | Detach one pad without changing the other three, revision changes, old raw ID returns NotFound, replacement gets a new ID, late removed-instance event cannot reach it; five cleanup callbacks |
| `lifetime` | Four complete provider/driver/SDL lifetimes in one process, sixteen virtual cleanup callbacks, no pending owned callbacks or initialized SDL subsystems afterward |
| `wrong-result` | Actual state deliberately compared with the wrong button expectation; exact diagnostic and exit 1, no success completion or sanitizer error |

Each suite runs the four positive cases in forward then reverse order in fresh
processes, with a negative control in each round (eight positive processes and
two negative controls). A successful process reports one
versioned JSON completion with matching case/nonce, exact cycle/device/cleanup
counts, quiescent state, check count, SDL version and actual loaded provider,
SDL and base-library paths. The driver resolves and hashes those paths and
requires the verified package locations. Windows resolves SDL's loaded export
explicitly because the import-library thunk can point into the executable.
Negative controls allow ordinary SDK log messages, but require their one exact
failure marker and exit. A crash, timeout, duplicate/stale/partial record,
coerced metric, wrong library path or sanitizer finding cannot pass.

Twelve original public Python tests exercise those evidence rules, including
duplicate JSON keys, missing/unknown fields, changed library paths, wrong
results, incomplete children and a child that prints completion but exceeds
its deadline. They also verify that an invalid SDK receipt stops before output
creation or building. These are synthetic evidence-guard tests and do not load
an SDK or establish controller support by themselves.

## Reproduction

Use a verified private `xma-packet-v1` SDK receipt and a fresh dedicated output
root separate from SDK sources/packages, owned content, profiles and other
lanes. These commands execute no guest or title code:

```text
python tools/test_sdk_input.py --root PRIVATE_CACHE --sdk-report XMA_RECEIPT --output-root PRIVATE_INPUT_OUTPUT
python tools/test_sdk_input.py --root PRIVATE_CACHE --sdk-report XMA_RECEIPT --output-root PRIVATE_INPUT_OUTPUT --sanitizers
python -m unittest discover -s tests/host_platform/sdk_input -p "test_*.py" -v
python tools/check.py --config Release
```

Linux native+host instrumentation and an instrumented-core receipt are distinct
profiles. Windows uses the pinned native SDK plus supported host UBSan traps;
its SDK core ASan profile remains unavailable. Sanitizer calibration is checked
on Windows. Vptr instrumentation remains disabled at this external SDK boundary,
as in existing diagnostics. The driver records compile commands, compiler/tool
identities, staged source and driver hashes, exact SDK tree/library hashes,
per-process logs, and its own executable hash. Failed attempts are retained.
The existing Linux core profile instruments the participating base library;
the input provider and SDL retain their native hashes. This is not full
provider/SDL sanitizer coverage. The SDK's native XAM and disabled-vptr limits
also remain; no XAM or guest code is exercised here.

## Meaning of the result

This tests raw provider devices and the selected SDK's `PadState`
representation. The fixture checks SDL south/east/west/north against the SDK's
A/B/X/Y labels, distinct X values, extreme inverted Y values and trigger 0/255
endpoints. It does not establish physical deadzones, center quantization,
controller-family compatibility, input latency, display capture or MW3 guest
input ABI correctness. Motor callbacks represent virtual devices only.

Source inspection of `IInputSystem` separately documents four SDK user slots,
automatic device assignment, a neutral user-0 fallback and optional shared-pad
routing. This probe does not instantiate or verify that assignment system.
The reviewed MW3-080 model's explicit owners/session tokens are also separate;
no bridge between them is enabled here. A driver ID can restart with a new
driver lifetime and must not be treated as a persisted player identity.

MW3-083 still requires four real controllers and actual backend integration.
MW3-012 requires title input evidence. No physical controller, guest mapping,
retail player limit, console split-screen, gameplay parity or four-player
Survival result is established. WSL is not a second independent physical Linux
machine. No title benchmark or fastest-backend claim is made. Runtime code and
performance are unchanged by these diagnostics.

All maintained fixtures/driver code are original GPL-3.0-only. The private
selected SDK/provider retains its reviewed BSD/Xenia provenance, and SDL its
zlib license and pinned submodule identity. No upstream implementation, SDK,
binary, game content or private log is added to Git. This is not new binary
distribution clearance. Owner self-review only; no independent review claimed.

## Recorded matrix, 2026-11-19

All five profiles pass ten processes each: **40 positive processes and ten
exact wrong-result rejections**, with no sanitizer findings in the exercised
coverage. Native Windows and Linux/WSL use Clang 20.1.2. The Linux core-profile
run changes the participating base-library instrumentation, not the native
SDL/provider bytes. Public evidence guards and the existing public parser/input
model are tested separately from this private SDK suite.

| Profile | Private receipt SHA-256 | Executed binary SHA-256 |
| --- | --- | --- |
| windows-native | `d3004ab036966113e3e5ade0cce83e252163e02eaa71ddefa6e6776fa3c4cc7a` | `b943ec77f0f6a1b79a1bc63eeea751fe1d90b9f93ced72aeaaee8766d83266fc` |
| windows-host-ubsan | `f77f6eb55bf29d7c156b08f44453227020570febb54ddc37c77baff14529c4fb` | `b4441001013a8f2a682f765e774a43779e17e7de2848782cbde92f576a8be61c` |
| linux-native | `173528c0764b18beef7d7da1e56033b30660763e12f9a60e400c7ec4e2c51127` | `d363bf81b7aea49170364a0184e75940068afd2ff517302a608319063a48a8e1` |
| linux-host-asan-ubsan | `9c7cb7763c3c1d266427d93b789fb0f40534ea7937b2aed578f4d39c081c9328` | `51072983796c0a7514d3e207a36ae218c5106db4e7778fdace0d9e15164f7304` |
| linux-core-asan-ubsan | `600eec5a5eb37237312f98c72e333703c360da63049ce68b2837750f57e33635` | `54f81e5a5e7bcae50f0d0aeed4fb37cd884e08b8b3d4f3cf9354e8b48ff3f65e` |

The audit reconciles all 50 per-process log hashes, executed binary hashes,
compile-command hashes, staged sources and each positive process's reported
loaded-library identities. These receipts bind full SDK trees and compiler/tool
configurations. All profiles compile the same original sources:

- `contracts.cpp`: SHA-256 `52c59cf00517a5367046fcbfadeab011aad293314d08582575a031751fb207e4`.
- `CMakeLists.txt`: SHA-256 `a23b9bb1ad3b09e4fee6f802ddd3ecad79973d3d55020744699f85eb8b962da0`.

Windows executed driver SHA-256
`3c1135ba8296b8237685e4ca3da9a79c972a7391e9b2234fa8cd8aa016847ec2`.
Linux and the current driver use
`5aeef28e54ea67f7beb29fa1550fa8274639d53b2095ffb1f6068bbd4dd5c0b9`.
The only driver change between them is the Linux SDL expected filename from
`libSDL3.so` to its loaded SONAME `libSDL3.so.0`; the Windows branch is unchanged.
The audit compares the exact scripts to establish that single-line delta.
The original Linux filename-rejection attempt remains retained, and successful
Windows observations are reused without rerunning unchanged behavior.

| Loaded platform/profile | Provider SHA-256 | SDL SHA-256 | Base SHA-256 |
| --- | --- | --- | --- |
| windows-native | `df7bfa9fa0274d429c3e29d70c153673e932b21460942ccbb89d0a9d2b338f9e` | `34a0c251b281bc58060ab1c271e9c59227b51347b1ab1e9c7ac2e2a1c218b61d` | `3149476e16d580859e8a953df2890e7cd3cf5e225dc37402ccf57817eca46faa` |
| linux-native | `1f2049520defebfc6d76e67aeead40892b8c4f5813911f765c106d21382dc579` | `9c83b5d1a533825354dc64a7153f3722840fcf4abac894e2c277bbff15e161d4` | `83e249a8d25fb605168876e0fc68bf10bb978425084c314962292dfcb49f1c4f` |
| linux-core-asan-ubsan | `1f2049520defebfc6d76e67aeead40892b8c4f5813911f765c106d21382dc579` | `9c83b5d1a533825354dc64a7153f3722840fcf4abac894e2c277bbff15e161d4` | `a9b7ecb6e2d453f353d32a08ae906a92676a8bdcd7c94d6c5e78997702ee7457` |

Host sanitizer profiles retain their platform's same provider/SDL/base hashes.
SDK base identity is `ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d`, with the
reviewed memory/stop/XMA compositions bound by the receipts. SDL headers/runtime
report 3.4.14 at submodule commit
`147a8ee32dbf9ac02f3794964490687b6bbda1bc`. No new SDK patch was needed.

Earlier harness failures remain private and are excluded from the 50 final
observations: missing cross-library allocator forwarders (Windows heap failure),
non-distinct virtual descriptors (identity precondition failure), executable
import-thunk reporting, and the Linux SDL link-name/SONAME mismatch. Correcting
the harness and identity checks did not change the SDK, lower expected input
results or turn those failed attempts into successes.

Public checks on this implementation also pass: Windows Release runs 160 Python
tests with eight explicit skips and parser CTest 1/1; Linux Release ASan/UBSan
runs 160 Python tests with one Windows-junction skip and parser CTest 1/1.
Windows skips are six unavailable link/symlink-privilege cases, one POSIX FIFO
case and missing LLVM assembler/objcopy in existing suites. No MW3-084 evidence
guard is skipped. The private SDL/provider suite is deliberately opt-in and
does not require an SDK in public CI.
