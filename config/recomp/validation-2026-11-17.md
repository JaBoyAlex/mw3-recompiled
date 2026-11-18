# Private generation validation — 2026-11-17

MW3-009 generates the exact owned SP/MP pair using the selected ReXGlue profile.
**Generation only: no title code executed or compiled by this driver.** This
does not establish Windows execution, control-flow completeness, console math
accuracy, supported gameplay or permission to distribute generated artifacts.

Commands: [build guide](../../docs/BUILDING.md#reproducible-private-generation-linuxwsl).
The Linux/WSL machine/compiler/source profile and SDK preparation are recorded
in [runtime evidence](../../experiments/runtime-bakeoff/conformance-2026-11-17.md).
The normal preparation is `runtime-bakeoff/runs/b938f93b72e343c3b49ed44ad7a51f17/manifest.json`.
Its source/submodule/patch identity, all 744 SDK input files and five linked
system-library identities are part of the private cache manifest. The driver,
recipe, helpers, executable pair and preparation receipt are also hash-bound.
This is local provenance, not signed build attestation or bit-reproducible SDK
binaries. Cache keys may differ between independently built SDKs or hosts.

Two fresh generations emitted identical byte hashes/sizes for **326 C++ and
header files**, 155 SP / 171 MP. Code-manifest SHA-256 over canonical sorted
JSON is `2bb4225f3e3bf6017a01caf9c469e0d3e8637a814ecff3f86e191de443770846`.
Ancillary files are hashed and verified per attempt, but absolute dependency
paths, stamps and logs differ; the entire payload is not claimed byte-identical.
Exact vector/estimate math is requested explicitly and register/stack forwarding
optimizations remain off. This setting needs independent CPU differential tests.
Unresolved automatically discovered indirect flow and nonlocal exits remain
runtime bring-up work. Manual targets/includes/hooks and forced validation are
not permitted by this recipe.

| Check | Observed result |
| --- | --- |
| First canonical generation | Generated both modules without `--force` |
| Second clean generation | All 326 source/header hashes and sizes match |
| Existing cache reuse | Full payload rehash, CACHE_HIT |
| Flip one byte in private copy of SP input | Fingerprint refusal before cache creation; originals unchanged |
| Temporary original untracked marker in SDK source | Dirty dependency refusal before cache creation; own marker removed afterward |
| Supply validation-only ASan SDK receipt | Refused before cache creation |
| Game-free fixtures | Modified/missing/extra cache files, identity/manifest tampering, concurrent writer, symlink escapes and unreviewed recipe changes refused |

The first attempt correctly refused publication when the SDK created rotating
logs beside its executable and changed its package inventory. A following
attempt demonstrated that the tool CLI does not accept App settings as options.
The final driver filters inherited REX/loader/sanitizer overrides and supplies
private app/user/log roots through the SDK's documented environment settings.
The new logs are observed under each attempt's root. Old SDK `bin/logs/` is
excluded as observation data; no SDK library/header/binary is excluded. Both
setup failures remain private. Original inputs were never patched.

## Private evidence

Paths relative to `~/.cache/mw3-recompiled/title-generation/`:

| Artifact | SHA-256 |
| --- | --- |
| `8ba54c6bb9c3250dc50b67f4d8c5d9bdf5259b42a42650b853de22b5c2406ac9/manifest.json`, first generation | `4ea00686affa0cf460155bc1f85e44ee21357312caf9670a9da724eef33491b8` |
| `attempt-962805c2f3ee41898c73e9c08a20fb92/manifest.json`, clean reproduction | `4eb49f150127a88e9775c24fedb68530d17bd9bb31e724073beca841e0dcb2d9` |
| `negative-a672da01145c4135962cc0432a184e45/manifest.json`, actual copied-input mutation | `a2c8cabbeaad0e1085555c12bb14eef508859fb5369fc3469a5ea0ff44ad18c5` |
| `validation-b76992b7fde54df0aa1ae1e38b98b8f1/manifest.json`, reproduction/cache/dirty-source/sanitized-package checks | `c9159d90349b03d572f438be3adb4f94a15a1fd42b4b5773a21364ff9e545be7` |

Windows `python tools/check.py --config Release` passes 78 Python cases (five
explicit unavailable LLVM/symlink privilege skips) and native CTest. Linux
Release ASan/UBSan and exact-head CI are required before integration. Eight
new game-free generation guard cases run in ordinary CI without game files or
SDK access. Public code is original GPL-3.0-only Python/JSON/docs; no upstream
source, game bytes, generated C++, SDKs or private logs are committed.
Self-review only; no independent reviewer available. No gameplay-performance
impact has been measured, and no release or product gate passes here.

Initial Windows CI correctly failed the existing overlap guard fixture on its
8.3 temporary-directory alias (`RUNNER~1` versus the resolved long name). The
driver now resolves both comparison paths after refusing symlinks. This fixes
the guard rather than skipping the fixture. Linux CI originally passed; fresh
generation and the Windows/Linux matrix are repeated for the corrected driver.
