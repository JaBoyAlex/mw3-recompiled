# REA evaluation — 2026-11-19

MW3-035 evaluates the official REA analysis adapters at a fixed revision.
Keep REA research-only and optional. Real REA/Ghidra sessions recovered the
original synthetic PPC fixture's selected instructions and cross-references,
but both exact owned MW3 executables were refused as unsupported formats.
No MW3 title-slice decompilation, XEX loading, VMX128 semantics or native game
execution is established by this evaluation. The selected runtime and its
existing title loader/scanner do not change.

## Versions and provenance

| Component | Evaluated identity |
| --- | --- |
| REA source inspection | `morluto/rea` commit `e9c72dbd1fa6b318cb3e455c92df064eed62333a` (clean tracked checkout) |
| Executed npm distribution | `rea-agents` 6.9.0; explicit `ghidra` provider over local stdio |
| Ghidra | 12.1.4 PUBLIC, build archive dated 2026-09-21 |
| Node / full JDK | 24.22.1 / Temurin 21.0.13.1+2 |
| Host | Ubuntu 24.04 x86-64 under WSL2; Python 3.12.3 |
| Independent readers/build tools | LLVM MC/objdump 19.1.1, LLD 20.1.2, GNU readelf 2.42, original Python ELF header checks |

Archive hashes are committed in [pins](../../experiments/rea/pins.json).
Each private attempt also hashes the actual Python, Node, Java, launchers,
decompiler, host tools and all 10,585 REA package / 5,219 Ghidra files as used.
The source checkout pin and npm archive integrity are separate identities;
this does not claim reproducible source-to-npm builds. No automatic setup or
installation was used by the evaluation, no proprietary provider was acquired,
and no game data was uploaded. The distributions were already explicitly
prepared by the operator before this run.

## Observed capabilities and limits

| Case | Local observation | Boundary |
| --- | --- | --- |
| Original ELF32 BE PPC `ET_EXEC` | Three fresh sessions pass exact bytes, `addi`, conditional branch/destination, procedure addresses, direct call, load data xref and BE global checks | Static selected-instruction evidence; no PPC execution or full ABI/ISA equivalence |
| Imported language | `PowerPC:BE:32:default`, compiler spec `default`, exact source-file digest preserved | Avoids Ghidra's upstream-reported default e500 ambiguity; not a Xenon CPU/ABI profile |
| Decompiler | Nonempty leaf pseudocode in all three sessions | Liveness only; pseudocode semantics not certified |
| VMX128 challenge | Original word `100b60cb` remains readable; instruction observation is `not-in-listing` in all three sessions | REA explicitly says no decode was attempted at this unlisted address; VMX128 support is unverified, not proven impossible |
| Load-image attestation | `inspect_native_load_image` reports verifier status `unsupported`, while language/file observations are available | Observation of hashes is not independent segment/load-image attestation |
| ELF relocatable / shared-header mutation | Expected Ghidra `architecture_unsupported` rejection requiring `ET_EXEC` | No relocatable/shared PPC support established |
| ELF32 little-endian | Independently assembled/linked image refused by the expected big-endian-only constraint | Not a malformed-endianness header shortcut |
| ELF64 PPC64 | Independently assembled/linked image refused with `unsupported ELF architecture: e_machine 21` | Family recognition itself fails before a provider session can analyze it |
| Embedded PPC flag | `EF_PPC_EMB` header mutation refused by the specific profile constraint | No Book-E profile validation |
| Truncated ELF | Expected `file_format_rejected`, 20 bytes versus required 52 | A diagnostic, not a timeout or missing-tool result |
| Owned `default.xex` / `default_mp.xex` | Both refused with `target_unavailable`, `unsupported_target`, `file_format_rejected`, reason `unsupported binary format` | No extraction, raw import, language override or auto-conversion attempted |

The VMX128 word is original fixture material matching the published helper
encoding in pinned XenonRecomp's README and `lvx128` decoder table. The
existing [MW3 executable map](../engine/executables.md) separately records
actual owned-title helper scans cross-checked with a Xenon-aware decoder.
That evidence does not transfer VMX128 support to Ghidra. Generic LLVM and
Ghidra tooling are not independent console semantic oracles.

Both owned inputs match the size and SHA-256 in the
[Rev 1 manifest](../../config/titles/mw3-xbox360-rev1.json):

| Executable | SHA-256 |
| --- | --- |
| Campaign `default.xex` | `f59be1342c2fc664e2a2e7322d024028a0ca7216d279ed32fef6e114d8c37c30` |
| Multiplayer `default_mp.xex` | `ba1bc57af4c4f75934a106b3d470559b356252b9e100d98e335bcfd0e574806a` |

Fresh Python inventory/struct and Windows native XEX inspection agree on
these inputs' hashes, container flags, image/security offsets and optional
header counts. Private cross-check receipt SHA-256:
`a8b18f1fa4b7fda629e77a6a5cc0f8e9538e396bdfb24b6dd7067ca757dc4d67`.
It binds the native inspector binary and both reader sources, and checks
unchanged input hashes again after inspection. Reproduce the fingerprint and
native observations with `python tools/verify_inputs.py "$OWNED_PAIR"` and
`mw3-xex-inspect` on each manifest member. REA refuses their format; this
is the owned-title comparison, not a recovered title function comparison.
Private title-slice analysis is **NOT RUN** because the required admission
path is unsupported. Filename changes or MW2 addresses cannot fix that gap.

## Other providers and licenses

These are statements from the pinned source and returned capability
diagnostics, not real analysis runs of those tools. REA's Hopper adapter
does not admit PowerPC; its IDA adapter has no verified PowerPC lane; Kuna's
verified lanes do not admit PowerPC. Their missing/unconfigured availability
diagnostics were retained separately and never counted as architecture
verification. No Hopper/IDA/Kuna process was configured or executed. Native
Windows REA/Ghidra was **NOT RUN**: the pinned Windows boundary does not
admit this PPC ELF lane. The Windows repository checks below are game-free
tooling checks, not Windows REA coverage.

REA-authored code is MIT, with its bundled dependency notices retained.
Ghidra supplies Apache-2.0 plus its government-work, component and GPL-program
qualifications; preserve the complete distribution's LICENSE/NOTICE/module
records. Node includes MIT and third-party notices; Temurin/OpenJDK includes
GPLv2 with Classpath Exception and component notices. LLVM and GNU binutils
retain their own distribution notices. IDA/Hex-Rays, Hopper and JEB require
separately obtained applicable tool licenses; REA supplies no entitlement.
This experiment redistributes none of those distributions and grants no
rights to game-linked outputs. See [project policy](../LEGAL.md).

Source references at the inspected REA commit:

- [PPC admission and language contract](https://github.com/morluto/rea/blob/e9c72dbd1fa6b318cb3e455c92df064eed62333a/docs/ghidra-ppc.md)
- [Actual profile constraints](https://github.com/morluto/rea/blob/e9c72dbd1fa6b318cb3e455c92df064eed62333a/src/ghidra/GhidraPowerPcProfile.ts)
- [Windows boundary](https://github.com/morluto/rea/blob/e9c72dbd1fa6b318cb3e455c92df064eed62333a/docs/providers/windows-ghidra-p0.md)
- [Third-party notices and external tool terms](https://github.com/morluto/rea/blob/e9c72dbd1fa6b318cb3e455c92df064eed62333a/THIRD_PARTY_NOTICES.md)

## Reproduction and results

The [experiment guide](../../experiments/rea/README.md) describes existing-tool
preparation and the complete command. The verified final command, run from
the isolated task worktree with private absolute paths substituted, was:

```sh
python3 experiments/rea/evaluate.py --preparation "$PREPARATION" --output-root "$PRIVATE_OUTPUT" --owned "$OWNED_PAIR" --runs 3
```

Final attempt `30ce3aa6754248c584b400702742fc95`: PASS; three fresh positive
sessions, three deliberate wrong-word expectation rejections, eight expected
format/profile refusals, and normal MCP shutdown for every session. Private
`report.json` SHA-256:
`0272a834ee1ea48c67e065b37302da982123766717ff63fb5e5b16671e61b7fa`.
Fixture ELF SHA-256:
`464a96cc97dfa356648e828108d2364d85c5ad72c7228c53b724e73c26249388`.
Harness SHA-256:
`3a13eacaf9186af359457d839dd64358e4edbfd410855460170f51f3a3495bf4`.
Raw JSON/pseudocode, generated files and logs remain private. The earlier
interrupted FAIL attempt and initial narrower PASS are retained; neither is
relabelled as the completed final suite.

Observed import-plus-load-observation wall times were 10.051, 12.266 and
12.007 seconds with a 1 GiB heap and two Java processors. They concern this
tiny static fixture on one machine, with possible host cache effects and
concurrent game-free checks. They are not a controlled provider comparison,
memory measurement, gameplay benchmark or evidence that any framework is
fastest. There is no runtime performance impact because this experiment is
not linked into the product.

Repository validation: Windows `python tools/check.py --config Release`:
114 Python tests, five explicit skips (one LLVM assembler/objcopy case and
four symlink-privilege cases), native CTest 1/1 PASS. Linux
`python3 tools/check.py --sanitizers`: 114 Python tests without skips,
ASan/UBSan native CTest 1/1 PASS. Final catalog validation (44 tasks) and
repository artifact heuristic pass. The Windows shell needed the existing
Git/CMake directories added to PATH; an initial missing-Git check failed
before tests, and a narrower run skipped two scanner tests until CMake was
on PATH. Those attempts do not replace the final totals. No public tests
install or launch REA. No parser/runtime interface or
generated game code is edited. Self-review only; no independent reviewer
was available during preparation.

Before adopting this tool for MW3, require a separately scoped, reviewed
XEX/normalized-image provenance and mapping contract plus a Xenon/VMX128
language/ABI validation against independent title evidence. Until those
exist, retain the established exact-title analysis and runtime tools.
