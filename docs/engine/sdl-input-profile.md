# Preserving sampled SDL trigger state (MW3-090)

The opt-in `sdl-trigger-v1` profile fixes an observed host-input defect in the
pinned SDL 3.4.14 library: opening a gamepad or replacing its mapping overwrote
an already sampled held trigger with its released value. The independent raw
joystick reader was changed too. The repaired profile preserves that sample
and retains the trigger's recentering/default point.

Three isolated profile constructions pass: native Windows, native Linux and
Linux with participating SDL/probe ASan/UBSan. These are actual SDL-library
observations using original virtual devices, **not physical-controller or MW3
title evidence**. Existing SDKs/source checkouts are unchanged. This is a
separate private SDL-only package, not automatic adoption into the shared
runtime, provider, guest services or release.

## Exact source and change

The [SDL source](https://github.com/libsdl-org/SDL/blob/147a8ee32dbf9ac02f3794964490687b6bbda1bc/src/joystick/SDL_gamepad.c)
is commit `147a8ee32dbf9ac02f3794964490687b6bbda1bc`, runtime version
`3004014` (3.4.14). The [lock](../../config/toolchains/sdl-input/lock.json)
binds the implementation, joystick axis structure/initialization, virtual
driver, public declarations, CMake source, license and reviewed patch. All
2,194 canonical tracked files are checked against the pinned Git blobs;
only `src/joystick/SDL_gamepad.c` changes in the derivative.

- Original canonical gamepad source SHA-256: `4f88ce1abfc0f556a2d92e024eaafd765b9843a7c7c9a0c66882350e72d06335`.
- Derived gamepad source SHA-256: `248280818b09b53097565bca1af8aba43d7602cce098ddaf84c63f10cb800d12`.
- Patch SHA-256: `d10f46dca0729d468086015e75ba7e5591afc791056ed7983ccbfe225fb77b44`.
- Unchanged SDL zlib license SHA-256: `1c040b8271b37e5076359f8fd54240e371114112924d2df81ef87c7d6a1dfdfd`.
- Frozen producer SHA-256: `7a3a133ef5c90d5b76a818c9120339b4492ee6e1e83899ee58b1be945b9ead87`.

`SDL_PrivateLoadButtonMapping` previously assigned both the axis `value` and
`zero` to the mapping's input minimum. The SDL axis structure distinguishes
the current value from its recentering point and records `has_initial_value`.
The patch sets `zero` as before, and assigns the default `value` only when no
initial value is known. A known sample survives. No structure, API, mapping
format, generated game code, guest address or input-owner contract changes.

The source review also covers `SDL_SendJoystickAxis`, which seeds unknown
samples and ignores unchanged values, and forced recentering, which uses `zero`.
This explains why ordinary polling did not repair the original reset: the
virtual driver still held the same raw sample and had no new change to emit.
The unknown-initial conditional is source-reviewed; the public virtual fixtures
initialize their axes, so that branch is **not independently reached at runtime**.
Uncalibrated hardware and arbitrary custom/inverted mappings remain unmeasured.

## Matched actual-library experiment

The producer exports canonical source into a new private UUID directory, builds
unpatched SDL, installs `baseline-sdk`, then applies the one-file patch to its
own copy and rebuilds the same build directory. It installs the derivative in
`sdk`. The same original probe executable, compiler, flags and feature settings
execute both library versions. The baseline snapshot remains immutable.
Native third-party/platform libraries are not replaced or instrumented by this
experiment. The standalone profile's detected features are retained in CMake
receipts; equivalence to every existing SDK/platform feature is not claimed.

The probe creates two distinguishable process-local virtual devices and opens
their raw joystick handles. It supplies released baseline values, then held
samples **before the first gamepad open**. It records actual raw samples before
and after each operation, mapped trigger values, a distinguishable stick and
button, actual library path/version and cleanup counters. It never writes an
internal SDL cache or moves the held stimulus past the first open.

| Observed phase | Coverage |
| --- | --- |
| Initial open | Held full/partial triggers survive; unheld trigger stays released; independent stick/button unchanged. |
| Unchanged polls | Three updates without another stimulus retain the sample. |
| Second consumer | Another reference to the open gamepad preserves readings and is balanced on close. |
| Close/reopen | A newly supplied real virtual-device sample survives reopening while the raw reader remains open. |
| Mapping replacement | A public mapping replacement with the same bindings and changed name preserves the sampled state. |
| Rest | Released triggers map to zero without disturbing the other controls. |
| Held detach | The existing recentering behavior yields released triggers and neutral controls; owned references/virtual devices are cleaned. |

The original baseline resets known triggers on initial open, reopen and remap.
Its expected diagnostic exits remain **1**, with the original observations and
cleanup footer retained. They are not repaired successes. The repaired library
retains exact raw state, full trigger endpoints and the observed partial mapping.
An independent second reader uses integer arithmetic for the chosen fixture
values rather than calling the producer's floating-point serialization oracle.

Each profile has nine owned subprocesses: three baseline defect observations,
three ordinary repaired successes and one each wrong-zero, incomplete and
deadline control. Across three profiles: **27 processes**, nine retained baseline
failures, nine repaired ordinary successes and nine rejection controls. There
are 336 serialized observations in 24 complete records; incomplete controls
have no invented rows. Every complete record reports two created/cleaned virtual
devices. These are owned input lifetimes, not proof of all OS resource cleanup.

The wrong-zero control requires an exact counterfactual expectation to fail
after normal cleanup and exits 1. Incomplete controls print only nonce-bound
READY after cleanup and exit 0. Deadline controls print plausible complete
evidence and remain alive for 30 seconds; the owned eight-second timeout rejects
them as `-999`. A valid footer never overrides a late process. Normal exit and
timeout coverage are kept separate; no LeakSanitizer exit scan is claimed for
the three killed controls.

## Platform, instrumentation and immutable identities

- **windows-native**, receipt `fe8911b615cf4c38ae7721a449d1b4fa`: manifest SHA-256 `65373f54c917ba905a52994c6431e24a144203239769996949be426c9d1507bc`; original library `18c694262136face3c3fe53ea1a1135acd46be8136d4eeae3c22fa7bb1ef9ee7`; repaired library `977edfe9afb58d71b0f59cca30cf2f954b2dd8742064eb96212570a203426f1b`; unchanged probe `899f84deab71679ab3f12a1ec6eab741f6bf0d34b637c90ab0984a6ebedad282`.
- **linux-native**, receipt `74a72efb06f34bae80a5b567d9caa718`: manifest SHA-256 `8abde429a2b0e70475e353c978beaf17c1eb8291d05c088b259a569d3471895e`; original library `ba149fabdcd5de3de979901dc6a1a041d473eafe0d0b079c66b56aa4f183119e`; repaired library `7d6c3db645570cf239a8fc88de1beef778dde8ac2a2fbd40314427160747ff27`; unchanged probe `301c0c20fc1c936a999720154b4ad91734b8f8a3a4f0a7e2683713f7982107fb`.
- **linux-sdl-asan**, receipt `486248bb939346e1a76588029383f313`: manifest SHA-256 `3289759e614a7b4287cd54a6629785942623e77994a8a6dcba1552f92c1303d8`; original library `af2738e06f3d2987a08e776058e769079308b12e03712022acbdfe8d8447de39`; repaired library `c91cec8e190ace4d13edf7d26c5250f105b03925c8ec4899e5383ddb18c1cc00`; unchanged probe `902670c21f1ac0bb21634cab9dbf061a5bdb10b5bbeacc4b916f3f65340b3317`.

The Windows compiler is Clang 20.1.2 (verified archive/file-set identities in
the receipts), with MSVC host toolset 14.44.35207, CMake 3.31.6-msvc6 and Ninja
1.12.1. Linux uses Ubuntu Clang 20.1.2, GCC 13 headers/libraries, CMake 3.28.3,
Ninja 1.11.1 and lld 20. Both use Release `-O2 -DNDEBUG`, `-march=x86-64-v2` and
at most two compile workers per profile. Compiler caches are off. Compile
commands contain 269 SDL units on Windows and 309 on Linux, all in the owned SDL
source/build trees; no ReXGlue kernel or game translation unit is compiled.

The participating Linux profile instruments SDL and the original probe with
ASan/UBSan. SDL's executable-oriented `--no-undefined` capability check is
disabled for that DSO only: sanitizer symbols resolve from the instrumented
executable, following the normal shared-library sanitizer model. The original
link failure and the successful isolated link retry remain recorded. Native
profiles retain the ordinary linker check. No sanitizer report appears in the
exercised final ordinary/expected-failure paths. Windows participating SDL
sanitizers are not supplied by this profile; native Windows behavior and later
adapter host instrumentation are distinct coverage. Other platform libraries
remain native, and WSL is not independent Linux hardware.

The second audit rehashes all source/package/probe/helper/tool files, source
Git objects, both compile-command files and CMake cache, re-reads every nonce
and complete record, and checks the exact actual library paths/hashes. The
preparation verifier rechecks the retained source/package/probe/evidence
identities before a consumer can use a profile. Receipts also contain full
commands, per-log hashes, package inventories and compiler/tool versions.
This is owner self-review and a separate analysis pass, **not independent review**.

## Isolation and retained development findings

The input cache and existing sources/SDKs are read-only. Output must be outside
that cache and maintained project paths. Each attempt owns its source, build,
installed packages, process handles, configuration, temporary and user paths.
The probe disables physical backends and rejects an unexpected initial device,
so it exercises no external controller. No GPU/title process is launched.

Git export explicitly disables checkout CRLF conversion and sets LF. Every
exported blob is verified before compilation. Early attempts revealed Windows
checkout/export EOL differences; their rejected outputs are retained. Extraction
rejects traversal, rooted/drive/device paths, symlinks/hardlinks, duplicates and
oversized members before writing source files. The new negative tests caught
and fixed a Windows rooted-path edge during development.

Other retained attempts include the original SDK/adapter held-trigger failure,
an incorrect early Linux SONAME path guard, an intentionally stopped owned
Windows preparation, and development producer/recipe revisions. None is folded
into the 27 final processes or relabeled a sealed current result. Only this
instance's identified preparation process tree was stopped; other lanes were
not changed or terminated. Final profiles use identical frozen maintained
producer/probe/config bytes and pass their post-build checks.

The first hosted Windows jobs exposed an 8.3 TEMP-path alias in a synthetic
receipt fixture. The fixture now resolves its output path just as the producer
does. The production package-path verifier remains strict; this test-only fix
does not change or regenerate the sealed SDL libraries.

## Reproduction and public validation

```text
python tools/prepare_sdl_input.py --root WROOT --output-root PRIVATE_OUT
python3 tools/prepare_sdl_input.py --root LROOT --output-root PRIVATE_OUT
python3 tools/prepare_sdl_input.py --root LROOT --output-root PRIVATE_OUT --sanitizers
python tools/check.py --config Release
python3 tools/check.py --config Release --sanitizers
git diff --check
```

`WROOT`/`LROOT` contain the existing clean pinned SDL submodule at the lock's
source-relative path. `PRIVATE_OUT` must be a separate private cache. A successful
preparation exits 0 with status PASS only when every expected positive/negative
disposition is observed and the final verifier accepts the retained package.
Failures remain diagnostic with preserved attempt paths.

Public Windows Release and Linux Release ASan/UBSan checks pass **288 Python
tests** each (eight existing Windows skips; two Linux Windows-junction skips),
plus parser CTest 1/1. All eleven new game-free evidence guards pass: exact
observations/types, original/repaired distinction, stale/duplicate/partial
records, actual late-child rejection, source/archive bounds, package/probe/tool/
log/receipt mutations, changed patch, invalid receipt and output isolation.
These synthetic guard fixtures do not execute SDL. The 65-task DAG, heuristic
artifact scan and diff/provenance review pass; final-head hosted matrix results
are recorded in the PR. The sanitizer-link option was independently exercised
by the private participating profile, not a mocked public build.

Scope PR 128 precedes implementation; serialized claim run `45094936326` at
`725fa88c38abaa34833437cebb4e0688113b3f2a` assigned issue 129. Only this task's
configuration/patch/helper/probe/report and own JSON change. MW3-089 consumes
the profile separately; physical MW3-083, all guest/title/input/gameplay gates
and the main allocation lane MW3-046 remain open/unchanged.

SDL notices and altered-source attribution are preserved. Public source contains
the small reviewed patch and original tools/tests, not SDK binaries, raw logs,
full private source/build trees, game bytes, keys or generated game code. No
game-linked release permission, physical compatibility, performance gain or
architecture score is inferred from this fix.
