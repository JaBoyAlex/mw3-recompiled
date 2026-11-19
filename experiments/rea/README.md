# REA provider evaluation (MW3-035)

This optional Linux x86-64 experiment statically analyzes an original fixture
through a real REA/Ghidra stdio session. It never executes PPC or game code.
It is separate from the native runtime, generation and normal game-free CI.
See [findings and retained evidence](../../docs/research/rea-evaluation.md).

## Operator preparation

Supply the exact distributions in `pins.json` yourself. The evaluation does
not download tools, run package installation scripts, register an MCP server,
invoke `rea setup`, or acquire licenses. Extract the npm archive with its
bundled runtime dependencies; do not substitute an unpinned global install.
Keep all distributions, archives and output outside Git. Preserve their
original license/NOTICE files. The Ghidra extraction must retain executable
permissions for its launchers and native decompiler.

The preparation JSON names existing absolute Linux paths:

```json
{
  "rea_package": "/private/prepared/rea/package",
  "node": "/private/prepared/node/node-v24.22.1-linux-x64/bin/node",
  "java_home": "/private/prepared/jdk/jdk-21.0.13.1+2",
  "ghidra": "/private/evaluation/ghidra_12.1.4_PUBLIC"
}
```

Place the four pinned archives in `/private/prepared/` (two parents above
`rea_package`). Ghidra can be extracted separately. Python 3.11+, LLVM MC and
objdump 19, LLD 20, and GNU readelf are caller-supplied host tools. Their actual
versions and executable hashes are recorded; the verified host used Python
3.12.3, LLVM 19.1.1, LLD 20.1.2 and binutils 2.42. Explicit `--mc`, `--lld`,
`--objdump` and `--readelf` arguments can select other installed paths, but
other tool versions have not been validated by this receipt.

## Run

From the task worktree:

```sh
python3 experiments/rea/evaluate.py --preparation "$PREPARATION" --output-root "$PRIVATE_OUTPUT" --owned "$OWNED_PAIR" --runs 3
```

Omit `--owned` for a game-free provider experiment. With that option, the
directory must contain the two unchanged executables from
`config/titles/mw3-xbox360-rev1.json`. They are opened only to test format
admission after checking both size and SHA-256; no conversion is attempted.
The original ISO/install is never used as writable output. The successful
receipt establishes that REA refused both XEX files, not title decompilation.

Each attempt gets a UUID output and each session gets private HOME, cache,
configuration and temporary directories, with an owned process group. Runs
are sequential, with two active Java processors and a 1 GiB Ghidra heap.
Requests have a 150-second deadline, tool subprocesses a 60-second deadline,
and MCP cleanup a 20-second normal deadline followed by bounded termination
of that session only. A cleanup failure fails the experiment. Large raw
JSON replies, generated fixtures, diagnostics and pseudocode stay private.
No network tool or target execution operation is requested. This harness
is not an OS network sandbox for arbitrary third-party software.

## Evidence checks

- LLVM MC/LLD create ELF32 big-endian PPC `ET_EXEC`; GNU readelf provides
  independent symbol/header observations, and Python checks ELF identity and
  entry. LLVM objdump independently confirms the fixed instruction encodings.
- Real Ghidra observations must retain the exact file SHA-256, generic PPC
  language and compiler spec. Fixed instruction words, conditional destination,
  a direct call, a particular load's data xref, and big-endian global bytes are
  compared with the fixture. Pseudocode presence checks provider liveness only.
- An original `lvx128` word challenges the generic listing. Its retained bytes
  and the actual decoder observation are reported without claiming successful
  VMX128 semantics. This is an observation, not a required successful decode.
- A deliberately wrong expected instruction word must fail for the byte
  mismatch reason in every positive run.
- Independently built little-endian and PPC64 images, relocatable input,
  `e_type`/embedded-flag mutations, truncated input and the optional owned XEX
  pair must fail with their expected target/format diagnostics. Missing tools,
  timeouts and unrelated errors cannot satisfy these controls.

`report.json` retains source/config, archive, executed binary, complete REA
package and Ghidra file hashes, plus all request/reply and generated-artifact
hashes. Extracted file identities are recorded as used; archive hash checks
are not an attestation that a local extraction has never changed. Receipts
start as FAIL and become PASS only after all requested checks and cleanup.
PASS describes this bounded evaluation, not supported XEX/VMX128 analysis,
complete PPC accuracy, runtime correctness or gameplay.
