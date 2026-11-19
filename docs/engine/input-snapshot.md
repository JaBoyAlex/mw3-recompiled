# Initial SDL3 input snapshot (MW3-086)

This isolated provider profile repairs the initial-held-input failure retained
by [MW3-085](input-users.md). The original Windows/Linux virtual-device stimuli,
assertions and compiled contract sources remain unchanged. The original native
executables are also rerun against the new provider to separate the repair from
rebuilding a fixture. This is host SDK evidence, not physical or title input.

## Source and ordering audit

The selected provider queues SDL events and opens gamepads when a later SDK
enumeration drains that queue. `OnGamepadAddedLocked` originally constructs an
empty `PadState`; it never samples already-held controls. The retained baseline
identifies original virtual product 3 at SDK user 0: SDL button=1/X=3072 while
SDK buttons=0/X=0 after discovery and another event pump. All ten original
failures, their actual loaded identities and LIMITATION/exit 1 suites remain
frozen in MW3-085; they are not relabeled successful.

Sampling alone exposed two details. Several SDL buttons alias the same SDK bit,
so replaying released aliases clears a held face button. Initial accumulation
therefore sends only actual held button downs into the existing handler. Also,
pinned SDL's `SDL_PrivateLoadButtonMapping` resets joystick trigger values when
`SDL_OpenGamepad` first loads the mapping. Opening only at delayed discovery
loses a trigger already pressed after device addition. The repair retains a
gamepad reference when the add event arrives, before that interval. Discovery
acquires its own reference to the open handle, samples current axes and held
buttons, and releases the queued reference after processing.

The existing axis/button handlers perform normalization; no new guest mapping,
assignment policy, SDL binding parser, synthesized OS input, input-system
implementation or success stub is added. Local `SDL_Event` values are only
arguments to those handlers, never pushed into SDL's queue. The existing Y-axis
bitwise inversion and trigger shift are preserved, including their quantization.

Pinned SDL headers permit open/read/close calls from any thread. The callback
opens before taking the event mutex. Draining swaps the event queue, releases
that mutex, then takes the state mutex. The repair does not acquire both mutexes
together or call an SDK connection callback from the SDL event watch. The SDK
continues owning user assignment and connection notification. Device revisions
are published after the event/handle is queued under the event mutex, so a
caller observing the new revision can drain that event. This avoids extending
the original pre-enqueue publication window with the early open operation.
During shutdown,
removing the watch synchronizes with SDL's watcher-list mutex before pending
references and controller references are closed, then SDL subsystems are quit.
New live/removed-but-undiscovered cases check this extra handle lifetime.

## Isolated preparation and provenance

`config/toolchains/rexglue-input-snapshot/lock.json` binds SDK base
`ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d`, the reviewed XMA lock, two canonical
provider source identities, original patch and derived source hash. SDL 3.4.14
remains pinned to `147a8ee32dbf9ac02f3794964490687b6bbda1bc`.
The original patch uses BSD-3-Clause with the target's Xenia/Tom Clay provenance;
the preparation recipe, tools and original diagnostics are GPL-3.0-only. See
the profile's `NOTICE.md`. No SDK source package, binary or game material is
committed or offered for redistribution.

`tools/prepare_runtime_input.py` first verifies the complete existing XMA
preparation, reads the two canonical Git blobs, applies the pinned patch with
explicit LF settings and builds only the provider in a fresh private directory.
It copies the parent package and replaces exactly `bin/rexhid-sdl3.dll` or
`lib/librexhid-sdl3.so`. Every other file must match the parent, with no matching
sidecar exception. Existing parent sources/builds/SDKs remain read-only.
The receipt binds the preparation tool, patch, lock, derived source/recipe,
parent receipt/identity, compiler, compile commands and complete package tree.
Before/after verification rejects stale or broadened compositions.

Both completed diagnostic runners admit this profile only with explicit
`--sdk-profile input`; their default remains the original XMA profile. No
runtime/title profile is silently switched. Each run has its own staging,
temporary/configuration directories, process handles, binaries and logs.
Physical backends are disabled and the initial SDL inventory must be empty.

```text
python tools/prepare_runtime_input.py --root PRIVATE_CACHE --baseline-report XMA_RECEIPT
python tools/test_input_users.py --root PRIVATE_CACHE --sdk-report INPUT_RECEIPT --sdk-profile input --output-root PRIVATE_USERS
python tools/test_sdk_input.py --root PRIVATE_CACHE --sdk-report INPUT_RECEIPT --sdk-profile input --output-root PRIVATE_RAW
python tests/host_platform/input_snapshot/run.py --root PRIVATE_CACHE --sdk-report INPUT_RECEIPT --output-root PRIVATE_LIFECYCLE
python -m unittest discover -s tests/host_platform/input_snapshot -p "test_*.py" -v
python tools/check.py --config Release
```

Use `--sanitizers` for diagnostic host instrumentation. The separate Linux
preparation uses `--core-sanitizers` with the instrumented XMA parent and also
instruments the repaired provider. The isolated adapters use the established
C++23/Clang 20 SDK convention; the maintained public core remains C++20.

## Validation boundaries and performance

User routing covers all 24 attachment permutations, four distinct SDK user
identities, unchanged/changed packets, capability and virtual-rumble routing,
hotplug/stale events, reentrant callbacks, nested UI blocking, held-button
consumption and explicit shared/no-device fallback policies. The original raw
provider suite covers four devices, full-range axes/triggers, capabilities,
virtual rumble, reconnect and repeated complete lifetimes. Deliberate wrong
expectations must fail with their exact diagnostics/exit 1. The new lifecycle
suite stops with an undiscovered add, both while live and after removal, and
requires all five original virtual-device cleanup callbacks and quiescent SDL.

The public receipt guards are synthetic and game-free. They exercise stale
parent/tool/patch/compiler/configuration identities, changed provider and
unaffected artifacts, replacement-allowlist expansion, unpatched provider
substitution, instrumentation admission, incomplete/stale lifecycle records
and explicit/default runner selection. Existing runner guards retain rejection
of duplicate/partial/wrong-library records and actual late/incomplete children.

Linux host and participating base/provider ASan/UBSan are supported; the input
system and SDL libraries remain native. Windows uses calibrated host UBSan
traps with native SDK libraries. Windows core/provider ASan and vptr coverage
are unavailable. WSL is the same physical computer, not independent hardware.

The repair adds current-state queries at controller creation, one shared handle
allocation per add, and a shared-pointer field/move in pending event records.
It adds no recurring SDL state polling to unchanged reads. No title performance
benchmark or speed ranking is claimed; diagnostic suite wall times include
builds and full artifact hashing and are not input latency measurements.

Four physical controllers, controls held before SDL's first open, mapping
reloads, independent Linux hardware, guest input ABI/services and actual MW3
input remain unverified. SDL's first-open trigger reset still limits any wider
guarantee about pre-existing physical devices. Physical task MW3-083 must
validate that lifecycle and explicitly integrate ownership/profile admission.
This bounded repair does not complete MW3-083/MW3-012, verify a playable boot,
console split-screen or four-player Survival, or clear game-linked distribution.

Owner self-review is recorded; no independent reviewer is claimed. The main
allocation/audio instance's paths, SDKs, profiles and processes are untouched.

## Prepared identities, 2026-11-19

All three preparations report PASS and preserve every unaffected parent file.
The parent commit and canonical provider/header hashes are in the lock. Exact
SHA-256 identities of the new configuration are:

| Artifact | SHA-256 |
| --- | --- |
| Preparation tool | `2b3ca81df7706d3f756e9dc284a08ef58ceff5bb3ef17a8c48ac28f5d0816c3b` |
| Profile lock | `00a31f3ab981f47284a47f980d4afdfcad4d3e41998ec28188eb1cb97e0b4b43` |
| Original patch | `4d98804ce6667f7a06295b1610a9cbbe9a89f0b70a296279b60b2792f7a0453c` |
| Derived provider source | `a1f62327c578c9ee95e7fc796a33d7109f6fa7d2cdbaed97d73cf6254bf063c7` |
| Provider build recipe | `44d2f13ba4794d8236652d0233925c0c77c23d7d7d56e551afb82160524c9a2c` |

| Preparation | Private receipt SHA-256 | Replaced provider SHA-256 |
| --- | --- | --- |
| Windows native | `64e2044b8cf0c02cc388d089eb62b1663b474477dba595ca7071c4088f5bf9f0` | `7ea0e9664086da2d16824552be30974659803ff577df65f3615ac44637601b95` |
| Linux native | `750fbccc3cd9bdf912eb9d84a1118aae8f2ed05a6f487e9e54c082ac2ea13b9b` | `76954a3bc56363172023bda90b6440048e92bf92377ec9889e97f6d2e5a64021` |
| Linux base/provider ASan/UBSan | `de304e2f876260d35ac41137f1d9e7b7533484d01a86eb61c505d461a52c41b6` | `2b50bb0e79807521867c7e914b0dceadd7fe96434d25ce1d7389023629dde36b` |

Clang is 20.1.2: Windows archive SHA-256
`8e771a685cd718303ea0d632a8a95ad7b3cb17068f3952fbefa64a77290324d8`, installed
compiler-tree digest `300ca7cd9b2d224ef1e57b70fa3351166047bb313de6b49ae2fbc7becbaef3d7`;
Linux compiler SHA-256
`b15e7640bf3082f36ef14321711706b265df3058721e3c2caef3a4b83895d07d`.
The provider uses Release `-O2 -DNDEBUG`, x86-64-v2 and the inherited host
allocator interface. Actual CMake caches bind Windows CMake 3.31.6-msvc6/Ninja
1.12.1 and Linux CMake 3.28.3/Ninja 1.11.1. Windows host tools additionally bind
MSVC 14.44.35207 and Windows SDK 10.0.26100.0. CMake/Ninja executable and cache
hashes, complete compile commands and compiler identities are retained privately.

The pinned SDL audit additionally binds `SDL_gamepad.c` SHA-256
`9a300d2f289cdaefd3d6c5d0d34d28db20362e77459ebe5780e28b93f007d82b`,
`SDL_eventwatch.c` SHA-256
`349f4ae6ee765b46e9a142249881d578e2296065e6f50d6a0efd900548bf9a3c`, and
`SDL_gamepad.h` SHA-256
`9ca462e243228aa59c24200f85b52a2aba9ca40ad4ba1b0ba8b01dd5111fec72`.

## Recorded validation, 2026-11-19

All fifteen final suites report PASS/exit 0: **150 processes, 130 positives and
20 exact deliberate rejection controls**. All ten previously failing
`held-discovery` cases now pass without changing their assertions. Each profile
runs 16 user cases, ten raw-provider cases and four queued-handle lifetime cases.
The two original native Windows/Linux executables also pass the same held-input
case against the repaired provider, retaining binary SHA-256 identities
`fdc1c59c6f178e93cf0485a8cfab601dbc465510dc59aeeb64ca60598eeb88f1` and
`78d77eeb4a3f3c4111097f1a2f6048c2f3e04a696238c1ef90e8c49f5d420533`.
The maintained contract/fixture/build-recipe bytes match their 084/085 baselines.

| Profile / suite | Private result receipt SHA-256 | Executed binary SHA-256 |
| --- | --- | --- |
| windows-native / users | `e405e5ece139aa372ce188ab8909fc2379404a09ca8ed2a14bd275bc708150c4` | `28e63392a97c0e30ddd588cbf37293ac251972e71a97d850f8813170c672c880` |
| windows-native / raw | `c1d26aedcbb517eea1c6b1176c1618cb8fdd0277f4415856899bce20b99e63a3` | `3fa7f6755bd7ed485100995f0073f2700a3a0510230635890750cf05247ab9db` |
| windows-native / lifecycle | `ca16fbcddc6adb8c7abcab3b91c12d1bf833d410d10c92323bdf5d8a140ebb99` | `eb13aa42ca5d9b17ddb3da1165788808ccac9474afc72d525ce49037e51c7055` |
| windows-host-ubsan / users | `7a8d79f7a162b9cb23626db1c27ba8bce5325fc3aad987fc8415b8a536ac448d` | `a81cff543a54ed9b87b94f527aff941369a10f1067c00b4313838ee172662739` |
| windows-host-ubsan / raw | `f2e087471ef9384c47612d61df7ec4f2de4e9b04b98ff17adb9de323f6747110` | `8704a63d1919f9a6e294482b3136a39262f497528cd243aff0f399cb3d9597ce` |
| windows-host-ubsan / lifecycle | `54ff4398530aaea5d8594364107ca3fd6decd8612af730e8a5b36462021b3a8f` | `b504d39196b8360e391b47ed9daa7c7ac9a21f618f4705d34e4482f276db6482` |
| linux-native / users | `5515d5bd722e55669fe0431347f8988626d07a15ed6e22aba1cc7beea5431a47` | `3e8934a586a284d5507389bbc19f2f9bced0ae161a218362281dfdf37cb6ce31` |
| linux-native / raw | `4fe6bec02b5ca38520b117faf1f6d3939ba9a108668d81d236defa4a47dfbcc4` | `517c325670bd723081f527061a039abb2f6b4e15366f1946c35ae3081a038a59` |
| linux-native / lifecycle | `28c4b7a581da7f2515e487aef7169294094c92eccb369487e535cf31dea7ab22` | `716a26707b897613db5bd3ed22343f1cfe6e45c103ca4d3ebfa7ebf04e5353b2` |
| linux-host-asan-ubsan / users | `68a59543e4a597bad023ba00ccd84facea63e11b6c834ad2a95dd455eac87a96` | `dd92b5f700f587be7df661dcb458d9a724a711d3b78a29fcaf494c8796983e99` |
| linux-host-asan-ubsan / raw | `3185db2431dbd03b2b1ac04be183d7c5db3dd6f254a22916dde635c7f31addf2` | `f3edfa0a917f958e5f747e268dfce75ca292c5f91247c9bfe566bb337e3adb7a` |
| linux-host-asan-ubsan / lifecycle | `23a19bed78d05916bc7387174ac156283c6709b7ae20cf904c77909f83a7e0ed` | `c5e0f3ca0ee2e6db3ce8d12efd682b32624ecbe30f44b712320be975d47b1598` |
| linux-core-provider-asan-ubsan / users | `dfaca80bc58d4dd6f324968da8987f4995a32bf81e6b0dc64f35cb6f9a7a591e` | `1d508677a47179a79115bd579ea3438ea989c228311ff3437489ddd266114072` |
| linux-core-provider-asan-ubsan / raw | `d572d8f0adf8d37c2b5242844b41ab9aa2d2394acc4156994f0545fde15168f4` | `a0eb7492b38db4c25764e76d8541b5c70663d28e3f36dab8b3410a96d14d1e80` |
| linux-core-provider-asan-ubsan / lifecycle | `c50dc88985ad40c69700f0d7c5a9cf1ff04073d79a650e7af310bced1d929026` | `c704a378b4477997b8209a67d3b61e25318541f1c3dac43116338a7f240421fa` |

The separate artifact reconciliation verifies all 150 log hashes, 15 executable/
compile-command records, the frozen sources/runners and identical SDK identities
across each profile's suites. **140 processes have actual nonce-bound loaded
library records**, including all 130 positives and ten user-routing controls.
The ten unchanged raw-provider negative controls fail before their original
completion-only library record; they retain the exact absolute provider argument,
verified package, same executable and required failure marker, but do not claim
an observed pre-failure module list. No sanitizer finding occurred in the
exercised instrumentation.

Five actual invalid-composition controls in a separate private Linux package
reject a wrong patch identity, stale parent receipt, changed provider, changed
input-system library and widened replacement list. Mutated hardlink entries are
unlinked before replacement; originals and parents are verified unchanged.
Twelve new public synthetic guards pass on both hosts. Full public checks pass:
Windows Release **193 Python tests/eight existing skips plus CTest 1/1**; Linux
Release ASan/UBSan **193 tests/two Windows-junction skips plus CTest 1/1**. Windows
skips cover six unavailable link/symlink privilege cases, a POSIX FIFO case and
missing LLVM assembler/objcopy in an existing suite. An initial Windows check
lacked CMake on PATH for nested suites (182 tests/ten skips); the corrected full
check reran all 193. The additional profile attributes preserve the exact tested
lock bytes across Git checkouts; staged tool/lock/patch/recipe bytes were compared
with the tested files.

Early iteration evidence is retained: Git's initial CRLF conversion was rejected
before compilation; sampling released button aliases cleared a held face bit;
late gamepad opening still reset the trigger. The first repaired matrix passed
before final source review moved revision publication after queueing. That matrix
and the first native lifecycle attempt are superseded by the complete final
matrix above, which includes stronger failure-path callback-storage lifetime.
None of these iterations is substituted for final artifact evidence.

Private command/output ledger `.local/086-matrix-ledger.json`, complete process
receipts/logs, same-binary comparisons, package rejections and
`.local/086-build-metadata.json` retain exact compiler/configuration/tool/cache
identities. The final matrix uses at most two independent host profiles/four
compile workers and no GPU/title suite. The main allocation/audio instance's
files, profiles, SDKs and processes are unchanged. This evidence admits only
the bounded opt-in host profile, with the physical/guest/title limits above.

Artifact audit SHA-256 `faf8b66e8b96f2c03ec4070f6412885764e9914c5a49ffa20f708feecb50849c`; build-metadata SHA-256
`9fc4490621d57d2093663fc783b5b903227e819cfd038f4fd8834b003126bcc4`.
