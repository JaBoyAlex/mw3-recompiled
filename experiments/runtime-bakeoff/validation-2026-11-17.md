# Bounded runtime evidence — 2026-11-17

**Owned MW3 SP and MP startup code executed privately on Linux/WSL, stopping at
the first unreviewed function import. Not playable. MW3-008 is incomplete.**

The exact pair is bound to [the Rev 1 manifest](../../config/titles/mw3-xbox360-rev1.json).
The unchanged pair and canonical analysis fingerprints are checked by the
drivers. Game bytes, generated C++, native game-linked binaries and logs stay
private. Rev 1 does not establish a title-update or informal "1.1" identity.

## Environment and source identity

One i5-11400, 12 logical CPUs, 16 GiB assigned RAM, WSL Ubuntu 24.04, kernel
`6.18.58.1-microsoft-standard-WSL2`, glibc 2.39. Clang 20.1.2, GCC 13.3 headers,
system libstdc++ runtime package 14.2.0. Preparation reports' "stdlib release 13"
identifies the selected header ABI, not that shared-library package's version.
Release `-O2 -DNDEBUG`, x86-64-v2, no LTO/PGO. ReXGlue adds its required large
code model/SSE flags and requires C++23. Maximum two build workers. GPU
capabilities and performance were not tested. Vulkan loader package 1.3.275,
explicit pinned headers 1.4.313 and VMA 3.2.1 do not prove device API support.

[pins.json](pins.json) binds source commits, submodules and the reviewed MW2
generator patch. Canonical Clang 18 preparation remains separate. Source
notices remain upstream; no SDK source was copied here. The existing
[distribution holds](../../docs/legal/runtime-and-distribution-assessment.md) apply.

## Observed results

| Case | Result | Limit |
| --- | --- | --- |
| ReXGlue host build | 1,462 steps, ~574 s initial successful build | Preparation, not a speed comparison |
| MW2 host tools | Exact base + reviewed patch built | Separate canonical tools unchanged |
| MW2 analyzer SP | 128 tables / 3,168 targets, including 123 `.text` tables | Candidate discovery only |
| MW2 analyzer MP | 156 / 3,810, including 151 `.text` tables | Original analyzer found five BINK tables each |
| New switch range checks | Unique dispatches, valid registers, executable targets and nonzero defaults | Five SP / four MP defaults unknown; no edge/dominance/coverage proof |
| ReXGlue generation | SP 161 / MP 177 private files; passed without `--force` or manual title addresses | Generation does not prove semantics |
| MW2 generation | 377 SP / 436 MP switch-case target/function-boundary errors despite exit 0 | Our driver rejects both; no title execution |
| Isolated ReXGlue host checks | 261 selected original cases passed in separate processes/profiles | Synthetic SDK tests, not all tests or gameplay |
| Aggregate ReXGlue checks | Initial report has 37 failing assertions; narrower memory/thread selections each expose another shared-state/log-counter assertion | Isolation does not fix aggregate reliability |
| SP title entry | All 258 function thunk bindings checked; first import stop reproduced 3/3 processes | Translated startup only |
| MP title entry | All 262 bindings checked; stop reproduced 3/3 processes | No multiplayer feature established |
| Deliberate SP guard failure | Exit 87, no image-ready/import-stop marker | Refused before guest launch |

Both entries stop at `RtlImageXexHeaderField`, exit **86**. Captured LR values
match independently decoded original direct calls at `LR - 4` targeting each
image's resolved import. No imported function service was permitted. Thirteen
imported data variables remain unaudited as runtime behavior. The probe removes
GPU/audio/input/UI requirements and exits the process at the boundary; no
graceful shutdown, asset loading or complete native boot is established.

Pinned MW2 `runtime/guest_memory.h/.cpp` starts the heap at `0x84600000`.
Its formula puts the function table at image end through
`image_end + 2 * PPC_CODE_SIZE`. Hash-bound generated headers give SP
`0x84330000..0x84bfe448`, MP `0x83fa0000..0x84956848`: **6,284,360 / 3,500,104
bytes overlap the fixed heap**. Image/section bounds independently match the
canonical inventory. This is a static incompatibility, not measured corruption
or a memory benchmark. Generated output with errors has not been accepted.

## Private evidence index

Relative to `~/.cache/mw3-recompiled/runtime-bakeoff/` on the owner's machine.
These are locators, not distributed files. Reports retain commands and exact
input/tool/config/output hashes; raw logs and all generated content stay private.

| Artifact | SHA-256 |
| --- | --- |
| `runs/cc7c86a4921b4ac98a69be88d413febd/manifest.json` — ReXGlue generation | `dc7eeeaabb2da41a6bd8e459a90e6b3ee8ac12080a5020cb9f54b4c3bdf70324` |
| `runs/eea7655247674ffdb5b9e9d6bd41b43e/manifest.json` — rejected MW2 generation | `e6f9dea251c24a81f8dcbc0e5c8ce3eb9eb75e8f5f383dbc2c1664e4aa5e6d3b` |
| `runs/521ef5c0f7cb48129288d08e258d1c1e/manifest.json` — isolated host tests | `de20dd96f7884c67b503ac9c109f752ae46d093de6fcf9e692574543e672b743` |
| `runs/902676c4806947f9b70b3202b2e1a63b/guard-and-repeat-v2.json` — SP guard/repeats | `e974ad7f0ba651cfacea64902550934e21d95ffdb16f950af7fa5b5c2160d7d4` |
| `runs/c4ee4e8f2fed4dd3a8cf1c979f1301b9/manifest.json` — MP build/first stop | `10368ab52dd11d8173360f4de142f5ac51479fe5ff7d73f6743cc9fc0befab11` |
| `runs/c4ee4e8f2fed4dd3a8cf1c979f1301b9/repeat.json` — MP repetitions | `736624c5517692234f68eec78bc97d2384fec8b24176211ce127f73d362be7c1` |

Aggregate failures remain in `runs/1aef698d29ad45938f4ceee3612a322d` and
`runs/196c3f2e193246b997c8b27bb0a2d2a8`. Setup failures (missing development
dependency, C++20 headers, malformed private trap string, wrong CLI options,
missing MW2 output directory) remain recorded separately from title failures.
SP report v2 corrects the original top-level startup flag to include the three
positive runs, retaining the original file/hash. No original trace was rewritten.

## Verification and limits

Commands: [reproduction guide](README.md). The combined Windows Release root
check passes 67 Python cases with three explicit skips (LLVM oracle tools,
two symlink-privilege cases), plus native CTest. The combined Linux Release
ASan/UBSan root check passes all 67 and native CTest. This includes all 11
experiment guard cases; the standalone subset also passes on both hosts
(one Windows privilege skip). Exact-head remote CI accompanies integration.
Upstream SDK and actual title execution were not part of root sanitizer checks.

No common runtime workload has executed on the MW2 candidate. No comparable
FPS/frame time, memory peak, loading, GPU or latency measurement exists. The
canonical PPC oracle, SDK tests and title startup are different evidence
classes. No Windows title build/run or fully instrumented upstream-runtime
sanitizer suite has completed. ReXGlue leads provisionally; no weighted or
"fastest" winner is asserted. All product gates remain open. Continue with
[the ADR handoff](../../docs/adr/0002-runtime-selection.md).
