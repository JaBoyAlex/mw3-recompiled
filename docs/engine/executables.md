# Initial executable map — owner-supplied Xbox 360 Rev 1

Status: MW3-007 **in progress**. Observed on 2026-11-17 after exact input verification. No guest code was executed. This is an image/import/control-flow inventory, not a complete function map or recompiler configuration.

Inputs are the exact SP/MP SHA-256 values in [title identity](../research/title-identity.md). The pinned XenonRecomp source is `ddd128bcca99fe8bfbb99bea583c972351fa6ace`. A metadata-only adapter links its XenonUtils loader; the analyzer is from the verified Clang 18.1.3 preparation build. The owner-restored ClangCL analyzer was also run separately, and its parsed switch tables matched the Linux results exactly.

| Observation | `default.xex` | `default_mp.xex` |
| --- | ---: | ---: |
| Image base | `0x82000000` | `0x82000000` |
| Entry point | `0x82459e58` | `0x824dbae0` |
| Loader image size | 36,896,768 bytes | 33,161,216 bytes |
| Sections | 13 | 13 |
| Main `.text` start | `0x82090000` | `0x820a0000` |
| Main `.text` size | 4,548,284 bytes | 5,024,084 bytes |
| Additional `BINK` code start | `0x824e6800` | `0x8256aa00` |
| Additional `BINK` code size | 68,132 bytes | 68,132 bytes |
| `.pdata` size | 120,192 bytes | 127,608 bytes |
| Import symbols resolved by loader | 258 | 262 |
| Switch tables detected by pinned analyzer | 5 | 5 |
| Targets in those tables | 29 | 29 |

Both images also contain `.rdata`, `BINKBSS`, `.data`, `.tls`, `.XBMOVIE`, `BINKDATA`, `.XEXID`, `.idata`, `.XBLD` and `.reloc`. Entry points agree with the earlier independent XEX optional-header observations. All detected dispatch addresses and targets are inside executable sections. Image size and section sizes are layout facts, **not measured runtime RAM usage**.

## Platform boundaries identified

Resolved names include `ExCreateThread`, thread wait/suspend/resume primitives, `XamInputGetState`/capability/rumble APIs, GPU ring/display/`VdSwap` APIs, `XAudioSubmitRenderDriverFrame`, XMA context functions, and legacy `NetDll_*` sockets. These identify concrete kernel/input/GPU/audio/network seams to examine during the runtime comparison. They do not prove any host implementation is correct or that every import is resolved. Names come from the pinned loader's ordinal tables; version/ordinal coverage still needs a complete audit.

The separate code/data sections named BINK are evidence of an embedded video component. Its execution, compatibility and any replacement/delivery implications remain to be tested and rights-reviewed. No vendor SDK or decoded game image is distributed here.

## Loader and analysis caveats

The upstream loader normalizes import thunks in its private in-memory image. The adapter reports metadata only and does not dump that modified image. PE section names are fixed eight-byte fields; the upstream string construction can include adjacent bytes when a name has no NUL. The reporting adapter limits names to eight bytes and JSON-escapes all byte values. This fixes the inventory representation without changing the pinned loader source.

Five recognized switch tables do **not** establish completeness. The analyzer looks for specific compiler patterns; other jump tables, leaf functions, indirect calls and exception/nonlocal flow remain open. There is no valid decompilation/recompilation percentage from these results.

Still required before MW3-007 can close: locate and independently verify eight save/restore helper families, setjmp/longjmp, function boundaries including `.pdata`/leaf coverage, all import kinds and unresolved ordinals, switch-pattern coverage and indirect-call behavior. Never copy MW2 addresses into an MW3 config. No production title-generation config is authorized by this inventory alone.

## Reproduction and evidence

Use the canonical toolchain and `config/analysis/analyze.py` as described in [the analysis guide](../../config/analysis/README.md). It verifies the owned pair, pinned sources and analyzer digest before loading either executable; output must be a fresh private directory. It records tool/library/probe/input hashes and refuses invalid switch bounds. Public unit tests use original synthetic metadata, not game bytes.

Private SP/MP metadata report hashes: `7d25bb3a75e548a1b72b49cd5936f4b589ad49f0fed8f8925a60032afffb69d3` and `7518207c91212c60f17ffd1fcf12b6c5dcb997f07b271445a5d3ed4ec09740fa`. Linux analyzer TOML hashes: `4eccd47e2749d5d53865fd321ccb5d56efdbeca14f63832e282c7cbbc927b75e` and `9daef0eb624e3eb459972e3d80237f4cfed5f14ff5ba4a7f93be98e705cfd121`. Native TOML line endings differ; parsed data equality was checked rather than asserting cross-host byte identity. Raw tables and import-address inventories remain private.
