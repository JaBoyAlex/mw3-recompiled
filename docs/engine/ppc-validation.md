# Selected-translator PPC oracle

This suite executes original synthetic PowerPC programs
through pinned ReXGlue instruction emission and compares their observable state
against independent Python integer/rational calculations. It does not execute MW3,
measure performance or establish full ISA correctness.

## Design and configuration

`tests/ppc/fixtures.s` is original assembly. LLVM assembles/links it at a synthetic
test address, never an MW3 hook address. A private disassembly and offset symbol
map remain with each run. The small original generator adapter compiles unchanged
pinned ReXGlue codegen sources and uses its StubModule/AnalyzeTestBinary/EmitCpp
API and templates. The runtime is dynamically imported from the verified SDK;
kernel objects are not embedded in the harness.

No game files are required. Canonical assembly/linking uses Linux LLVM 20.1.2,
with separately fingerprinted LLVM 18 metadata utilities. The pinned Windows
LLVM package lacks a PowerPC assembler: Windows consumes a successful,
source/hash-verified Linux fixture bundle, then generates, compiles and executes
the instructions natively. Windows output must match that reference byte for
byte. Every attempt preserves its actual generator executable separately from
the reusable build directory, so later builds cannot invalidate earlier receipts.

The upstream `recompile-tests` CLI enables all nine exact-math settings, but also
hardcodes stack-store forwarding on. Our adapter sets all nine modes to exact,
keeps the six register-local options off and disables stack forwarding, matching
the conservative title recipe's emission policy. Synthetic analysis supplies
known fixture bounds; it does not validate full-title discovery or imports.

Generated instruction objects use the production guest arithmetic policy
`-fwrapv -ffp-contract=off`; the host runner keeps ordinary overflow checks.
Compile-command inspection enforces that separation. The synthetic fixture
contains no SEH scopes and does not certify the production asynchronous exception
or unwinding configuration. An early sanitizer failure exposed a missing
wraparound flag in this new harness, while the existing title build already had
the correct policy; the failing artifact remains retained. No SDK instruction
patch was needed. Both sanitizer platforms run an inert/overflow calibration
against host code to demonstrate that host checks remain active.

`tests/ppc/oracle.py` supplies expected values using integers, Fraction and explicit
round-to-nearest/even. It contains no translator or copied interpreter. The C++
runner calls the actual generated functions and compares selected register and
memory outputs. Two fresh generations must agree. Every run records compiler,
assembler, linker, metadata utilities, SDK, source, recipe, generator, binary and
case/log hashes. Inputs, emitted code, mismatches and counterexamples stay private.
An additional run changes one expected result and must report exactly that error;
an exit code alone cannot establish detection.

## Semantic references

The [PowerPC Programming Environments manual](https://www.nxp.com/docs/en/user-guide/MPCFPE.pdf),
section 4.2.1, defines low-word CR0 and carry behavior for a 64-bit implementation
in 32-bit execution mode. GPR arithmetic results remain checked at 64 bits. The
first prototype oracle incorrectly assumed 64-bit flags; its mismatches are
retained as an oracle-development error, not a translator defect. Fixed cases
now distinguish low-word zero/sign/carry from upper GPR bits.

Scalar fused arithmetic follows IBM's
[fmadd description](https://www.ibm.com/docs/en/aix/7.1.0?topic=set-fmadd-fma-floating-multiply-add-instruction).
The [e600 vector reference](https://www.nxp.com/docs/en/reference-manual/E600CORERM.pdf)
provides the ordinary AltiVec lane arithmetic reference. This is an architectural
mathematical oracle, not a retail-console differential capture or proof of all
Xenon-specific floating-point behavior.

## Coverage and limits

Cases include fixed 32/64-bit edges and seeded arithmetic, CR0/SO/carry,
rotate/mask, big-endian byte/half/word access and byte-reversed loads, conditional
branches, CTR loops, a guest-to-guest direct call with stack/LR/nonvolatile GPR preservation,
scalar add/fused cancellation, signed zero/quiet-NaN classification, vector word
addition/XOR and exact-mode vector fused multiply-add.

Untested: overflow-enabled arithmetic, all other ISA instructions, VMX128/high
vector registers, reservation/atomic memory ordering, indirect target misses,
nonlocal exits/exception unwind, FPSCR exception bits and non-nearest rounding,
NaN payload propagation, vector denormal/estimate/transcendental peculiarities,
guest OS/ABI completeness and real-title execution. Selected finite vectors
exercise exact-mode emission but do not certify all nine math modes.

## Validation — 2026-11-18

Six final runs each pass all **2,410** fixed/seeded cases: Linux native and
host/generated ASan+UBSan, Windows native and host/generated UBSan traps, plus
Linux seed `1` and Windows seed `0xffffffff`. The common seed is `0x20110360`.
That is 14,460 ordinary case evaluations across repeated profiles/seeds, not
14,460 distinct instructions. Six additional full mutation runs each detect
exactly the deliberately wrong first result and reject no other case.

Every run independently generates twice. Both emitted files are identical in all
six runs, including native Windows versus Linux. Register policy, exact math,
compiler flags and actual kernel linkage are recorded. The post-run audit checks
the retained generator and runner binaries, case files/logs, compile commands,
assembled inputs and both generations against their receipts.

Windows `tools/check.py --config Release --cmake <VS cmake.exe> --ctest <VS ctest.exe>`
passes 98 Python tests (five explicit unavailable-tool/symlink skips) and native
CTest. Linux `CXX=clang++-18 python3 tools/check.py --config Release --sanitizers`
passes 100 Python tests without skips and ASan/UBSan CTest. Six focused guard
tests cover flag width/rounding, seeded reproducibility, incomplete/duplicate
results, unexplained failure, exact mutation rejection and stale/modified reference
refusal. The Linux public suite uses a native-filesystem checkout: Windows Git
worktree pointer files are not portable to WSL Git. No global Git setting changes.

Windows ASan is not claimed; its SDK allocator/link limitation is documented in
[Windows bring-up](windows-bringup.md). Linux instruments the runner and actual
emitted instructions. SDK cores, graphics/dependencies and the generator itself
are native, not instrumented by this CPU suite. Floating/vector coverage is the
selected subset above. No MW3 instruction, gameplay, full ISA, timing or release
claim follows. Full thread/lifecycle and real-title teardown remain separate
039/041 dependencies. Self-review only; no independent reviewer was available.

Retained development failures include the independently corrected low-word flag
oracle, the missing harness wraparound policy, unavailable native Windows PPC
assembly, text-mode newline conversion, and cache-binary replacement. None is
counted as a final pass. Final generation writes canonical bytes and copies each
executed generator into that attempt before running it.

## Reproduce privately

Prepare a native `decommit-v1` SDK with
`python tools/prepare_runtime_memory.py --root <runtime-root> --baseline-report <verified-baseline-manifest>`.
Use the resulting exact receipt; do not edit a stale receipt to make it pass.
The original 042 experiments used a CRLF lock file before Git normalized it;
these fresh canonical-lock preparations retain the same patch/source policy.

On Linux:

```sh
python3 tools/test_rexglue_ppc.py --root <runtime-root> --sdk-report <native-manifest> --output-root <private-output>
# Repeat with --sanitizers or --seed 1.
```

On native Windows:

```powershell
python tools/test_rexglue_ppc.py --root <windows-runtime-root> --sdk-report <native-windows-manifest> --output-root <private-output> --reference <successful-linux-output>
# Repeat with --sanitizers or --seed 0xffffffff.
```

LLVM 20.1.2, MSVC 14.44.35207/Windows SDK 10.0.26100.0 and the exact selected SDK
base/submodules are bound in the private receipts. Linux metadata utilities are
LLVM 18; all assembly/linking/host compilation uses LLVM 20. Two build workers
and one active suite per machine were used. No performance comparison was made.

## Private receipt index

Locations are below the private `ppc-oracle-038` output root on the named host.
These are audit locators and SHA-256 values, not published binaries or traces.

| Run | Output directory | Manifest SHA-256 |
| --- | --- | --- |
| linux-native | `060ae87d42704480a8b7d29912733dd4` | `024d6ea35d1726f27673921cfb7be62b3aafbe86785dec8646da427add8ec029` |
| windows-native | `f2755821d2fe47b08f7cc2accfddab7d` | `e0ddd5f739f745298f0665fb4431e2f26c2a239599aab80405f55b13b402a96b` |
| windows-ubsan | `e7e4de7e7a8a4701b3fee2ba035dc48c` | `6a1d4e4450ab5b0271996da6fd919f950c8df3859c86b64a619071d7fae930a0` |
| linux-asan | `2da3c200338a40a9a8b36b8923efc15a` | `972f2ae6452c59a9bc2ea0d7fbab5b57d8c13d4d7cbcd22276e6e796d9aef64e` |
| linux-heldout | `f48df8e7223a45449e5914dcc7a6e1bf` | `56e442d711fbaf1cd93da5ea4eff864bd1837f17a7f0d54f228d5ff4b9fa23a4` |
| windows-heldout | `a552d94c6a45421e80996c38ea2f0e38` | `090db5855c34f6136b76368596a42b395f6b01c2b7fdd209dcd505b6bb8fd45d` |

Native SDK preparations (below each host runtime root):

| Host | Receipt | SHA-256 |
| --- | --- | --- |
| Linux | `memory-preparations/8b945a023e8942a7860590691876dcbb/manifest.json` | `c1996460def39792edb3cb6ee94abf6606c760aeeb59fdd07999e1766c20e00d` |
| Windows | `memory-preparations/9cdfc3f652e64b2082bfd85e211267ac/manifest.json` | `4744ae8546dd7f79728dbbb5f53afb66bca983d2b2e58a28ac495780af8ac8f8` |

Emitted-file hashes:

- `ppc_config.h`: `53f136e9061095fdb5cc4f4e7485cc4ef5a68821e538cee8fe5edac5542ec35a` (16811 bytes).
- `ppc_test_functions.cpp`: `6a3d48ce3b582e7958fd428705bd2a7fbfe2677d4fe58d09cafbec8ced34a52e` (5021 bytes).
