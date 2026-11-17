# MW3-008 private runtime experiments

These are research tools, not an installer or playable release. Read the
[current evidence](validation-2026-11-17.md) and
[runtime decision](../../docs/adr/0002-runtime-selection.md) and
[common service tests](conformance-2026-11-17.md). Game bytes, generated C++,
binaries and logs stay outside Git.

## Reproduction

Use Linux x86-64 with Clang **20.1.2**, GCC 13 development headers, CMake/Ninja,
lld 20 and the upstream Linux platform development packages. The scripts do
not install system packages or weaken Windows security settings. The existing
canonical Clang 18 analysis toolchain is separate. Two build workers are the
limit. The baseline SDK places output in its source tree regardless of `-B`;
the reviewed derivative adds `REX_OUTPUT_DIR` so native/sanitizer builds have
separate outputs. Never let different profiles overwrite shared artifacts.

Choose a private Linux cache as `BAKEOFF_CACHE`, an unchanged verified SP/MP
directory as `OWNED_PAIR`, and a canonical schema-4 analysis directory as
`TITLE_METADATA`. The latter is produced by the existing
[analysis workflow](../../config/analysis/HANDOFF.md), including `report.json`
and the two `*-image.json` files. Do not borrow a related game's configuration.

```sh
python3 experiments/runtime-bakeoff/prepare.py --root "$BAKEOFF_CACHE" --fetch --configure-rexglue --build-rexglue
cmake --install "$BAKEOFF_CACHE/build/rexglue-release"
python3 experiments/runtime-bakeoff/mw2_tools.py --root "$BAKEOFF_CACHE" --fetch --build
python3 experiments/runtime-bakeoff/inspect_owned.py --candidate rexglue --root "$BAKEOFF_CACHE" --owned "$OWNED_PAIR" --metadata "$TITLE_METADATA"
python3 experiments/runtime-bakeoff/inspect_owned.py --candidate mw2 --root "$BAKEOFF_CACHE" --owned "$OWNED_PAIR" --metadata "$TITLE_METADATA"
```

Every inspection creates a fresh `runs/<uuid>` with private configuration,
logs, exact input/tool/config hashes and output snapshots. The current MW2
attempt intentionally returns failure because its generator diagnoses errors
despite exit code zero. Do not compile/run it as a successful title preparation.
The reviewed upstream patch is applied to a separate pinned generator checkout;
a temporary Git index verifies the exact derivative and preserves local edits.

Host checks use the SDK's original tests, one process/profile per selected
case. They retain failures rather than retrying until green. This isolates an
observed aggregate-suite state problem; it does not erase that problem.

```sh
python3 experiments/runtime-bakeoff/host_checks.py --binary "$BAKEOFF_CACHE/sources/rexglue-sdk/out/linux-amd64/unit_tests" --output-root "$BAKEOFF_CACHE/runs"
python3 -m unittest discover -s experiments/runtime-bakeoff/tests -v
python3 tools/check.py
```

The root suite and CI also include these 14 game-free experiment guards through
`tests/test_runtime_bakeoff.py`; the explicit command runs just this subset.

To compile a ReXGlue inspection's private output, substitute its exact generated
directory. Default behavior only builds. `--execute` requests a bounded startup
attempt, with fresh writable roots and all imported functions replaced by
diagnostic stops. Before launch, every import thunk must resolve to its expected
stop function. A failed guard exits 87. Reaching an unreviewed import exits 86;
that is evidence of reaching the stop, **not successful game boot**.

```sh
python3 experiments/runtime-bakeoff/rexglue_probe.py --owned "$OWNED_PAIR" --generated "$GENERATED_SP_DIRECTORY" --metadata "$TITLE_METADATA" --sdk "$BAKEOFF_CACHE/install/rexglue" --output-root "$BAKEOFF_CACHE/runs" --role sp --execute
```

Use `--role mp` and the MP generated directory separately. The isolated host
experiment uses **C++23** because this SDK's headers require `std::expected` and
`std::byteswap`; the maintained game-free foundation remains C++20. SDK-required
large-code-model flags apply. No LTO/PGO or register-context elision is enabled.
Upstream vector-math defaults are retained for this integer startup experiment;
they have not established console floating-point accuracy. Enable/review exact
math before correctness or performance claims about gameplay.

The probe disables GPU/audio/input/UI driver requirements explicitly. It
exits the process at the import boundary instead of testing normal teardown.
It cannot establish renderer, audio, input, memory-service, thread-service,
asset-loading, gameplay or shutdown correctness. Source and binary provenance
snapshots are reproducibility records, not independent proof of generator
semantics. [Distribution holds still apply](../../docs/legal/runtime-and-distribution-assessment.md).

## Common runtime-service contracts

These compile original, game-free native callbacks against the actual runtime
services. SP/MP labels select verified image/code geometry, not title execution.
The MW2 adapter compiles the pinned memory/kernel/thread sources directly;
unused title initialization is discarded. The ReXGlue adapter uses its real
TitleRuntime, memory, registry and termination import. No successful guest
service stubs or generated title objects are linked into this harness.

```sh
python3 experiments/runtime-bakeoff/prepare_rexglue_memory.py --root "$BAKEOFF_CACHE" --fetch
python3 experiments/runtime-bakeoff/run_conformance.py --root "$BAKEOFF_CACHE" --metadata "$TITLE_METADATA" --derived-sdk-report "$NATIVE_PREPARATION_REPORT"
python3 experiments/runtime-bakeoff/prepare_rexglue_memory.py --root "$BAKEOFF_CACHE" --core-sanitizers
python3 experiments/runtime-bakeoff/run_conformance.py --root "$BAKEOFF_CACHE" --metadata "$TITLE_METADATA" --derived-sdk-report "$SANITIZED_PREPARATION_REPORT" --sanitizers
```

Each preparation prints its private manifest location. Use that exact report,
not a previous profile's SDK. Sanitized core packages are validation-only and
must never be used for title generation. Only base/PPC/kernel and their built
dependencies are instrumented; unchanged packaged drivers are not a fully
sanitized SDK. The host collision fixture occupies ASan shadow space and is
explicitly skipped in that profile; native tests cover it. Nine-position
mapping-failure injection uses a test-only preload shim in the native profile.

Exit **1** from the comparison means recorded candidate failures, including
the intentionally retained MW2 defects. Exit **2** means an experiment error.
Neither may be reported as an overall passing comparison. No timing in these
logs is an MW3 performance result. The losing runtime is retired from further
adaptation; these commands retain a reproducible record of why.
