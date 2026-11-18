# Selected-translator PPC oracle

MW3-038 is in progress. This suite executes original synthetic PowerPC programs
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

The upstream `recompile-tests` CLI enables all nine exact-math settings, but also
hardcodes stack-store forwarding on. Our adapter sets all nine modes to exact,
keeps the six register-local options off and disables stack forwarding, matching
the conservative title recipe's emission policy. Synthetic analysis supplies
known fixture bounds; it does not validate full-title discovery or imports.

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
branches, CTR loops, a guest-to-guest direct call with stack/LR/r31 preservation,
scalar add/fused cancellation, signed zero/quiet-NaN classification, vector word
addition/XOR and exact-mode vector fused multiply-add.

Untested: overflow-enabled arithmetic, all other ISA instructions, VMX128/high
vector registers, reservation/atomic memory ordering, indirect target misses,
nonlocal exits/exception unwind, FPSCR exception bits and non-nearest rounding,
NaN payload propagation, vector denormal/estimate/transcendental peculiarities,
guest OS/ABI completeness and real-title execution. Selected finite vectors
exercise exact-mode emission but do not certify all nine math modes.

Validation results and reproducible commands will be added after the native and
supported sanitizer/platform runs finish. No CPU milestone passes while required
evidence or discovered defects remain unresolved.
