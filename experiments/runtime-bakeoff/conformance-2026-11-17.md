# Runtime-service comparison and selection — 2026-11-17

ReXGlue is selected for **private development**. The MW2 runtime adaptation is
stopped. No playable boot, Windows title execution or comparative gameplay
performance is established. See [the ADR](../../docs/adr/0002-runtime-selection.md)
for the explicit change from the original two-title-execution experiment.

## Comparable original workload

The [harness](conformance/) contains original synthetic native callbacks, not
game instructions. Both adapters use the actual pinned allocator, memory and
thread implementations on the same Linux/WSL machine and compiler profile
listed in [the startup evidence](validation-2026-11-17.md). Address layouts
come from independently verified SP/MP inventory. A callback's guest context
is tested; translated PPC arithmetic/control-flow equivalence is **not**.

| Native case, three independent processes each | MW2 runtime | ReXGlue derivative |
| --- | --- | --- |
| Synthetic memory, A/C aliases, byte order and nonoverlapping allocation | 3 pass | 3 pass |
| SP geometry, same memory contract | 3 fail: allocation overlaps function table | 3 pass |
| MP geometry, same memory contract | 3 fail: allocation overlaps function table | 3 pass |
| Thread callback return; r3 cookie, r13, stack alignment | 3 pass | 3 pass |
| Suspended start, timeout, resume and completion | 3 pass | 3 pass |
| Actual ExTerminateThread must not return to callback | 3 fail: returns | 3 pass |
| Occupied host mapping must survive runtime initialization | 3 pass | 3 pass after repair; baseline fails |
| ReXGlue-only: nine mapping-failure positions | Not applicable | 27 pass |
| ReXGlue-only: 16 synthetic load/unload cycles, memory and all thread cases per cycle | Not applicable | 3 pass |

Native totals: MW2 **12 pass / 9 fail**; ReXGlue **51 pass**. The command exits
1 because the candidate failures are real, retained failures. This is not an
overall passing bakeoff. Native callback timings are not title benchmarks.
Suspended-start timing covers an observed bounded interval; it is not a proof
against every scheduling race. The lifecycle test is synthetic, not game exit.

The upstream memory implementation could overwrite an existing Linux host
mapping while probing a fixed base. An independently owned canary page proves
that failure in an ordinary, nonsanitized process. ASan also exposes shadow
mapping conflict; upstream already documents a custom-mapping ASan limitation.
The reviewed [BSD patch](patches/rexglue-linux-reservation.patch) reserves the
whole 4.5 GiB span with MAP_FIXED_NOREPLACE before mapping views, rejects kernels
that ignore the requested address, and releases the entire reservation on any
partial failure. The test preload shim injects exactly one failure at each of
nine view positions, then verifies retry and reclaimability of released space.
Windows mapping semantics remain unchanged apart from clearing released pointers.
An optional CMake output directory prevents native/sanitizer profiles from
overwriting each other's artifacts.

The patched SDK's 261 selected upstream host cases pass in separate processes.
An initial rerun failed five cases because the separately built test-module
fixture was absent; building that target resolves those setup failures. The
baseline aggregate suite's order/shared-state failures remain unresolved.
Isolation is a diagnostic strategy, not a fix for aggregate reliability.

The final ASan/UBSan profile instruments the changed memory implementation and
the base/PPC/kernel shared libraries, as confirmed by the compiler command and
ASan symbols in all three. ReXGlue: **21 pass / 3 explicit collision-fixture
skips**; MW2: **9 pass / 9 fail / 3 matching skips**. No reported sanitizer
errors occur in those cases. Unchanged packaged platform/driver libraries are
not instrumented. Nine-position fault injection runs only in the native
profile. Earlier wrapper-only sanitizer and baseline shadow-collision failures
remain recorded; neither is relabeled as this stronger core check.

## Title execution and remaining service gaps

Both cached private title programs were rechecked with fresh staged derivative
core libraries: 3/3 SP and 3/3 MP stop at RtlImageXexHeaderField, exit 86. Loader
diagnostics verify the three replaced core libraries actually loaded. The
unchanged owner inputs verify before and after. All 258/262 function bindings
remain traps; no service succeeds through a placeholder. The original startup
evidence independently binds the LR return sites to each module's direct call.

Thirteen data imports per image remain semantically unapproved. The first
header query, nonlocal exits, exception/context semantics, detailed thread
suspension/cancellation, timers, synchronization races, stack guards, title
teardown, devices and every gameplay service still need scoped validation.
ReXGlue's service implementation count is not a supported-import count.
The MW2 source additionally has unverified/no-op service paths; only the
termination behavior and layout incompatibility above were actually exercised.

No GPU, audio, controller, asset-loading or network service is validated.
The first-import probe's process exit does not demonstrate graceful teardown.
Canonical 547 PPC checks, upstream CPU tests, common native callbacks and title
startup are distinct evidence classes. No claim of fastest runtime is justified.
Source/provenance and game-linked release holds remain in force.

## Private evidence index

Paths are relative to `~/.cache/mw3-recompiled/runtime-bakeoff/`. These are local
locators with SHA-256, not published logs or game artifacts. Earlier failure
reports are retained. Reproduce using [the commands](README.md).

| Manifest | SHA-256 |
| --- | --- |
| `runs/7c3593b7168244f681231004641ef970/manifest.json`, final native contracts including ninth view | `eb408f905e469f6b21e2a152c15b800d415edf33029c51556f513fac12a0e1d1` |
| `runs/b938f93b72e343c3b49ed44ad7a51f17/manifest.json`, final native SDK preparation | `36d6921c25cf65d5459130437c4d7ece32f4b98acfa616547332ac67d88b1e74` |
| `runs/dbb5642852e74ff4a761ea19d2c03047/manifest.json`, final native contracts | `fb938260f5692a410c6d2cb7a559f384fbb9be80614c0a91deac64cbdcb7f6b7` |
| `runs/6aacfa9e39b34ef6b0458bac678628f0/manifest.json`, instrumented core preparation | `3b6e3070e481eb050336c4c55e5bb5833531fd3cd8f9b17a4f0065a518fd748c` |
| `runs/0c1cb9c1a9d84619b4cb851f932d604b/manifest.json`, instrumented core contracts | `a54970948d7ad36086369563b960508268c96076c02c38df559d324917036477` |
| `runs/6a343e680ea84f489c267366a510d292/manifest.json`, memory-only derivative native contracts | `21ebe46f4006a403593f79b7e5e6ab2d604d8925abb2dedab944486c2832f6a2` |
| `runs/74008c27745b44898aec6c8204b00519/manifest.json`, harness/MW2 ASan/UBSan; ReXGlue core uninstrumented | `22408eac5be733ea32fb63d0f1398ffbee859f2e2e31675c4e203b1dd7a42bd6` |
| `runs/ba96e98c3c7f48ed8f2f643ea9e9b29e/manifest.json`, patched SDK isolated 261 cases | `3134b3f3331a1fe9ce4a2f743b5826e260f1e0581352dd8a14a1c291e2222823` |
| `runs/63050616424d4cdd8a6678fc547b13ba/manifest.json`, owned startup recheck with repaired core | `fdfe08a9d87de4d3df17ec1fddaa8f6a4fb97260f3f994be70e4104024817725` |

The memory-only derivative tree was `077b23af33f646340517d77dc64cea053ff93d6e`.
Self-review caught that the initial fault matrix covered eight of the nine
views. The final native rerun adds the ninth, passes all 27 injected cases,
and raises the ReXGlue total from 48 to 51. Older reports retain their actual
eight-position scope. The runtime patch itself did not change.
The final patch additionally changes only the build-output setting; current
pins bind that exact derivative. SDK build timestamps prevent a claim of
byte-reproducible SDK binaries; actual library hashes are retained. No public
game-linked package or release approval results from these experiments.

The final derivative tree is `23801a7d89028b3878ad7964d225a5073e69c234`;
patch SHA-256 is `800c6a6a28e1d567d442956a352a84d9eabd136202f54531c72876e3e4af56a9`.
The original baseline SDK is unchanged. The patched upstream source passes
`git diff --check`; unified-patch context markers are not trailing whitespace
in that source. Game-free checks include 70 Python cases and native CTest on
Windows Release (three explicit unavailable-tool/symlink skips) and Linux
Release ASan/UBSan. CI evidence accompanies the merged task PR. Self-review is
disclosed; no independent review is claimed.
