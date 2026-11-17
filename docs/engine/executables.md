# Initial executable map — owner-supplied Xbox 360 Rev 1

Status: MW3-007 **in progress**. Observed on 2026-11-17 after exact input verification. No guest code was executed. This is an image/import/control-flow inventory with verified ABI helper locations, not a complete function map or recompiler configuration.

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
| Complete, unique ABI helper families | 8 | 8 |
| Valid `.pdata` entries | 15,024 | 15,951 |
| Entries with handler metadata | 310 | 322 |
| Code bytes covered by `.pdata` ranges | 4,128,520 | 4,544,184 |
| Total executable-section bytes | 4,616,416 | 5,092,216 |
| Immediate-call instruction words | 78,716 | 86,346 |
| Immediate-call words targeting outside code | 0 | 0 |
| Unresolved noncanonical LR/CTR branch sites | 3,658 | 4,093 |

Both images also contain `.rdata`, `BINKBSS`, `.data`, `.tls`, `.XBMOVIE`, `BINKDATA`, `.XEXID`, `.idata`, `.XBLD` and `.reloc`. Entry points agree with the earlier independent XEX optional-header observations. All detected dispatch addresses and targets are inside executable sections. Image size and section sizes are layout facts, **not measured runtime RAM usage**.

## Verified save/restore helper locations

The Campaign column applies only to SHA-256 `f59be1342c2fc664e2a2e7322d024028a0ca7216d279ed32fef6e114d8c37c30`; the Multiplayer column applies only to `ba1bc57af4c4f75934a106b3d470559b356252b9e100d98e335bcfd0e574806a`.

| ABI family | Campaign address | Multiplayer address |
| --- | --- | --- |
| `savegprlr_14` | `0x824bed00` | `0x825424a0` |
| `restgprlr_14` | `0x824bed50` | `0x825424f0` |
| `savefpr_14` | `0x824bedb0` | `0x825425f0` |
| `restfpr_14` | `0x824bedfc` | `0x8254263c` |
| `savevmx_14` | `0x824bff40` | `0x82543ab0` |
| `restvmx_14` | `0x824c01d8` | `0x82543d48` |
| `savevmx_64` | `0x824bffd4` | `0x82543b44` |
| `restvmx_64` | `0x824c026c` | `0x82543ddc` |

Each location is the sole complete match across both executable sections in that image. The scan checks GPR/FPR registers 14–31, VMX 14–31 and VMX128 64–127, their stack slots, all suffix strides and the appropriate return/LR tail. The pinned table-driven decoder independently agrees with every instruction of each actual match, including VMX128 register extension bits. These are ABI identities inferred from complete instruction semantics, not recovered retail symbol names or borrowed MW2 addresses. Possible extra entries before register 14 are not assigned by this scan.

Method references: [XenonRecomp's ABI descriptions](https://github.com/hedge-dev/XenonRecomp/blob/ddd128bcca99fe8bfbb99bea583c972351fa6ace/README.md), [ReXGlue's complete-run detection practice](https://github.com/rexglue/rexglue-sdk/blob/ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d/src/codegen/phase_register.cpp) and [its `.pdata` interpretation](https://github.com/rexglue/rexglue-sdk/blob/ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d/include/rex/ppc/image.h). The maintained scanner is an original implementation of these documented encodings/ABI rules; no upstream implementation was copied or runtime selected by this work. Unlike a first-match detector, it preserves all matches and ambiguity.

## Function and unresolved-flow inventory

Neither image has malformed, unsorted, zero-padding or overlapping `.pdata` rows under the bounded reader. Type counts (save / normal / restore / handler) are Campaign **3 / 14,708 / 3 / 310**, Multiplayer **3 / 15,623 / 3 / 322**. Metadata ranges are evidence of declared boundaries; bytes outside them may contain leaf functions, helper suffixes, padding or embedded data. Coverage is not a recompilation percentage or proof of every boundary.

The word scan identifies canonical `blr` encodings (17,493 Campaign / 17,926 Multiplayer) and separately records all other LR/CTR branch sites as unresolved. It does not prove instruction reachability, infer callees from register values or parse exception handlers. Recognized switch tables are not automatically subtracted from unresolved sites. Complete private direct-call target inventories support subsequent leaf-function and nonlocal-exit work; no host stubs or guest execution are involved.

## Platform boundaries identified

Resolved names include `ExCreateThread`, thread wait/suspend/resume primitives, `XamInputGetState`/capability/rumble APIs, GPU ring/display/`VdSwap` APIs, `XAudioSubmitRenderDriverFrame`, XMA context functions, and legacy `NetDll_*` sockets. These identify concrete kernel/input/GPU/audio/network seams to examine during the runtime comparison. They do not prove any host implementation is correct or that every import is resolved. Names come from the pinned loader's ordinal tables; version/ordinal coverage still needs a complete audit.

The separate code/data sections named BINK are evidence of an embedded video component. Its execution, compatibility and any replacement/delivery implications remain to be tested and rights-reviewed. No vendor SDK or decoded game image is distributed here.

## Loader and analysis caveats

The upstream loader normalizes import thunks in its private in-memory image. The adapter reports metadata only and does not dump that modified image. PE section names are fixed eight-byte fields; the upstream string construction can include adjacent bytes when a name has no NUL. The reporting adapter limits names to eight bytes and JSON-escapes all byte values. This fixes the inventory representation without changing the pinned loader source.

Five recognized switch tables do **not** establish completeness. The analyzer looks for specific compiler patterns; other jump tables, leaf functions, indirect calls and exception/nonlocal flow remain open. There is no valid decompilation/recompilation percentage from these results.

Still required before MW3-007 can close: verify setjmp/longjmp, refine leaf/function boundaries, audit all import kinds/versions and unresolved ordinals, and investigate switch-pattern coverage, indirect-call behavior and exception paths. Never copy MW2 addresses into an MW3 config. No production title-generation config is authorized by this inventory alone.

## Reproduction and evidence

Use the canonical toolchain and `config/analysis/analyze.py` as described in [the analysis guide](../../config/analysis/README.md). It verifies the owned pair, pinned sources and analyzer digest before loading either executable; output must be a fresh private directory. It records tool/library/probe/input hashes and refuses invalid switch bounds. Public unit tests use original synthetic metadata, not game bytes.

Private SP/MP metadata report hashes: `7d25bb3a75e548a1b72b49cd5936f4b589ad49f0fed8f8925a60032afffb69d3` and `7518207c91212c60f17ffd1fcf12b6c5dcb997f07b271445a5d3ed4ec09740fa`. Linux analyzer TOML hashes: `4eccd47e2749d5d53865fd321ccb5d56efdbeca14f63832e282c7cbbc927b75e` and `9daef0eb624e3eb459972e3d80237f4cfed5f14ff5ba4a7f93be98e705cfd121`. Native TOML line endings differ; parsed data equality was checked rather than asserting cross-host byte identity. Raw tables and import-address inventories remain private.

Expanded helper/function/branch report hashes are Campaign `49daa629982ea7b69e88cfec0d322322c5fd499f2220d99d8233cececcabe1e1` and Multiplayer `6aa04c0109fbce13d177d553a8b668038aa24e2a7262fd785bf1ba5f6d07f7f7`. These include the complete private inventories, not just counts. The linked decoder archive hash is `cf42b9d0dd65576c267c98242fe41520f1a65a4871b3b95fa0f64164b7526af1`. Sanitizer instrumentation covers the maintained adapter/scanner; prebuilt upstream loader/decoder archives remain uninstrumented. Game-free tests include an independent LLVM assembly oracle for the six standard PowerPC families; the owned-title decoder checks cover the two VMX128 families. No gameplay correctness or runtime performance is established by these checks.
