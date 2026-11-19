# Emitted PPC reservation transitions — MW3-047

This is an investigation of actual selected-translator instructions with
original game-free inputs. It is **not a passing reservation-compatibility gate**.
The standalone instruction path exhibits failures that need a separately agreed
repair/integration task. No SDK, CPU/thread interface or guarded startup code is
changed, and no MW3 instructions or game bytes are executed.

## Independent oracle and bounded execution

Eight original two-instruction fixtures in `tests/ppc_reservations/fixtures.s`
cover `lwarx`, `stwcx.`, `ldarx` and `stdcx.`, each with RA zero or indexed base,
followed by return. LLVM assembles 64 bytes at an explicitly synthetic address.
The unchanged original MW3-038 adapter invokes the pinned translator's actual
analysis/emission implementation. Two emissions must match; native Windows must
also match the canonical Linux fixture/emission hashes. Generated output is
private and regenerated, not edited or committed as maintained source.

The independent Python oracle tracks reservations as state, not a remembered
value or native compare/exchange algorithm. The public specification basis is
[PowerPC VEA Book II v2.02, sections 1.7.3.1 and 3.3](https://powerpc.dev/general/PPC_Vers202_Book2_public.pdf)
(IBM-authored January 2005 document, hosted mirror), supplemented by the
[manufacturer's `stwcx.` reference, PDF pages 137–138](https://www.nxp.com/docs/en/reference-manual/MPC82XINSET.pdf#page=137).
The rules used here are limited: absence of reservation forbids a conditional
store; every conditional store consumes the reservation; a successful conflicting
store invalidates it; CR0 records the store outcome and XER SO. Value equality
does not itself establish a reservation. These are architecture references,
not evidence of Xbox 360 granules, full Xenon semantics or console execution.

Each of 672 cases uses aligned private memory at one location, word/doubleword
edge or seeded values, equal/opposite initial CR0 SO controls, and one of seven
sequences. Two independently initialized PPC contexts provide explicit logical
ownership. The runner calls generated load-reserve/conditional-store functions;
host code only initializes registers/memory, schedules finite steps and observes
results. It does not implement guest conditional stores or expected results.
There is no host callback substituted for an instruction.

| Family | Defined property checked |
| --- | --- |
| load | Big-endian data, word zero extension, address forms and preserved condition/register/guard state. |
| pair | Store outcome, memory and CR0 agree; a valid reservation may fail spuriously. |
| none | A fresh context with no executed load-reserve cannot manufacture a successful store. |
| consumed | Two conditional stores after one load-reserve: the second has no reservation, including when the first wrote identical bits or failed. |
| lost | Context B changes the location; context A's first failure cannot establish a new reservation for its next conditional store. |
| aba | B changes and restores the bits; A must still have lost its reservation. |
| isolation | A's load cannot establish a reservation in a separately initialized context B. |

The oracle permits failure with a valid reservation. Interference cases are
`INCONCLUSIVE` if their successful-write premise was not exercised; they cannot
silently pass. No mismatched-address, unaligned, MMIO, exception, alias/granule,
reservation-width mixing or arbitrary ordinary-store behavior is assigned a
deterministic result. Sequence scheduling is serialized: no concurrent
non-atomic host loads/writes, host race test or general memory-ordering claim.
Logical context isolation here does not execute guest thread switching or prove
the kernel's reservation-clearing/context-switch behavior. The reference warns
that switching hardware contexts requires an explicit clearing convention;
the `none`/`isolation` tests instead specify empty state for a newly initialized
standalone PPC context. They cannot certify that kernel convention by analogy.

## Result integrity, resources and sanitizer limits

Fresh nonce-bound library and completion records identify actual loaded kernel
and base modules. Their path/bytes must match the approved native SDK (or its
identical private build copy). Strict typed case/step/ordering/count bounds,
guard/preserved-state checks and resource markers reject malformed/duplicate/
partial/stale results, process crashes and sanitizer diagnostics. An observed
semantic mismatch remains `FAIL`; runner exit zero only means observations
completed, never that the oracle agreed.

Wrong-result controls execute a real defined load and mutate its observation;
exactly the independent load comparison must fail. Incomplete controls clean up
then omit ordinary completion. Informational SDK log lines are permitted while
fresh library/marker identity remains mandatory. A public test captures a real
owned child timing out after plausible output; its timeout exit cannot pass.
Fifteen Python tests exercise independent transition positives/negatives and
evidence/package/reference controls without loading an SDK in public CI.

Each process owns its address space, committed range, contexts, output/temp
directory and handles. Explicit committed-range release must succeed before
address-space destruction and completion; SDK-tracked threads recover their
initial count. A marker plus host sanitizer coverage does not prove every SDK
allocator or OS resource is leak/race free. No other lane's process or cache is
stopped or modified. Builds use two workers in this lane, serialized.

Linux ASan/UBSan and Windows calibrated UBSan traps instrument both the host
runner and actual generated instruction object. The unchanged SDK libraries
and generator internals remain uninstrumented. Windows core ASan and TSan are
not claimed; no concurrent host execution is exercised. Generated guest code
uses `-fwrapv -ffp-contract=off`; host code keeps ordinary overflow checks.
The SDK-facing diagnostic uses C++23 because the approved headers require it;
the public project remains C++20/Python standard library. This test-only linkage
does not authorize SDK or game-linked binary distribution.

## Reproduce and repair handoff

Use an existing immutable approved **native memory-profile** SDK preparation.
No SDK preparation/repair is performed by this runner. Canonical Linux:

```text
python tools/test_ppc_reservations.py --root <private-runtime-root> --sdk-report <approved-native-memory-manifest.json> --output-root <new-private-output>
python tools/test_ppc_reservations.py --root <private-runtime-root> --sdk-report <approved-native-memory-manifest.json> --output-root <new-private-output> --sanitizers
```

Windows uses the same commands with `--reference <completed-linux-output>`:
its pinned LLVM package lacks a PowerPC assembler. A completed failing
investigation is valid fixture provenance; its compatibility failures must not
be erased to obtain a reference. Source/assembly/emission identities are checked.
All ordinary runs include three independent common-seed processes, reversed
case order and held-out seed `0x0badc0de`; controls are separate. The runner
intentionally exits **1** when complete observations expose incompatibilities.

```text
python -m unittest discover -s tests/ppc_reservations -p test_*.py -v
python tools/check.py --config Release
python tools/check.py --config Release --sanitizers
```

Before admitting a repair, agree its owner and shared CPU/thread/memory contract.
It must cover reservation validity/consumption, cross-context invalidation and
conditional-store flag semantics, while considering the cost of invalidation,
aliasing and guest scheduling. A CAS-only value check cannot establish the
observed lifetime properties by itself. Do not silently repair SDK sources in
this diagnostic lane or weaken the oracle to bless repeated stores. Any future
repair must replay these retained counterexamples, existing CPU/thread/memory
tests, supported sanitizers and actual owned-title checkpoints before wider
service admission. General guest ordering, physical console equivalence and
gameplay remain unverified. Self-review only; no independent review represented.

## Recorded outcomes and counterexamples

Four final native/host-generated sanitizer profiles each complete seven
processes: five ordinary FAIL observations and two expected detector PASS
controls. Total **28 process outcomes = 20 FAIL / 8 expected control PASS**,
with no skipped or inconclusive ordinary cases. Every ordinary process has
**240 PASS / 432 FAIL out of 672 cases**, consistently across common seed
`0x20110360` (three repeats and reversed order) and held-out `0x0badc0de`.
The 20 runs evaluate 13,440 cases (4,800 PASS / 8,640 FAIL); these are repeated
bounded observations, not distinct instructions or a compatibility percentage.
All four diagnostic commands intentionally exit 1. Investigation completion
does not turn these mismatches into passing CPU compatibility.

| Family (96 cases each ordinary process) | PASS | FAIL |
| --- | --- | --- |
| load | 96 | 0 |
| pair | 48 | 48 |
| none | 48 | 48 |
| consumed | 0 | 96 |
| lost | 0 | 96 |
| aba | 0 | 96 |
| isolation | 48 | 48 |

Representative original word/RA-zero cases with initial value 0, XER SO 0
and initial CR0 SO 1 (`*-4-0-0-0`) expose the following. The same semantic
failures recur for doubleword and indexed forms. These are observed values,
not conclusions drawn only from upstream source comments.

- `pair`: the write succeeds and EQ is set, but CR0 is 3 rather than 2;
  its old SO survives instead of copying XER SO. Equal-SO controls separately
  pass the ordinary pair, so flag and reservation checks are distinct.
- `none`: a fresh context can successfully replace 0 with `0xffffffff`
  without a preceding load-reserve. This is the explicit standalone fresh-
  context contract above, not a hardware context-switch experiment.
- `consumed`: one load of 0 is followed by a successful store of 0 and
  then a second successful store of `0xffffffff` without another reserve.
- `lost`: B writes `0xffffffff`; A first fails its conditional store,
  then succeeds on a second attempt without another load-reserve.
- `aba`: B writes `0xffffffff`, then restores 0; A subsequently succeeds
  in storing `0xffffffff` using its earlier reservation. Bit equality
  has incorrectly substituted for reservation lifetime.

The first ordinary process in every profile reports 768 CR comparisons,
304 reservation-validity checks and 312 memory comparisons failing. These
checks overlap within cases and must not be added as separate test counts.
Loaded value, guard bytes and checked preserved state have no mismatches.
The source inspection is consistent with these observations: selected
`src/codegen/builder/memory.cpp` emits a remembered-value compare/exchange
without an explicit validity/consumption state or SO assignment in that
path. No source change is hidden in this diagnostic.

Retained development attempts are separate: the first incomplete-control
comparison wrongly required an otherwise empty log and rejected a normal
SDK information line. Its first source snapshot was also invalidated by
ongoing local test development, so it is an ERROR receipt, not a final run.
A Python timeout test initially expected 124 instead of the existing helper
sentinel -999; the assertion was corrected after reading that contract.
None of these fixture errors is counted among the final 28 outcomes.

A previously sealed set precedes final review of the timeout-output assertion
and incomplete-control nonce format. It remains retained separately; the final
receipts below were refreshed for the exact maintained source hashes and are
not pooled with the earlier set.


## Exact provenance

Scope PR 105 merged at `73ba86bc9ae766377371d2f74c31a0ba620945e3`; task-admin
claim run 44497871241 succeeded and issue 106 assignment was verified before
implementation. Dependencies 038/039 were done/closed. Existing generator and
verification helpers are unchanged from that base and separately hashed in
each receipt. All original maintained sources are GPL-3.0-only; only source
and this evidence summary are published. No SDK, binary, generated fixture
output, private trace, game content, key or credential is committed.

| Profile | Private attempt ID | Manifest SHA-256 | Runner SHA-256 |
| --- | --- | --- | --- |
| windows-native | `5456f3ddfa63436ebe7aa5958212c7ba` | `fe751e90349efa0f3d0aea2fc98348f215b1be503e7266ee0619eb1e0b56cacc` | `afca121054fbfd773dd9298d3746188a30559cc23f3bc8d67a9dff2184b3e477` |
| windows-ubsan | `d1cc0849dd924ac9bf105fa6baf18b86` | `f6c50f5d291dfc8ad1b1d91e2f50e250668e5df3a09c4301298836f146616820` | `4b7f6e4351d2d30e12a27031c7fba8963f83ac700474a9026888e1a151d2a027` |
| linux-native | `757a5932b3c047f4939acb369077ae4f` | `dd9c5b9f6cbe81878b7b1a161d5ca851cc697e626940b03aafcfbe54a84a4dc2` | `f8a5d6eeb7e39d7da39513b4388db1d3e84317fe37655a420c587efa79dd8869` |
| linux-asan | `13e1c1fcb154457d9dcc51ba173c67f8` | `aa97c87c0571b9a6034cf68e6df4167ed1d4ab936743cf4df82fb49b6ea42d6e` | `6289100f92bb2c56ff5e63a203310b1e5adbad7c7fc97c295464577600fa9552` |

All retained artifacts, case/log files, current sources and loaded libraries
were rehashed after execution. Both platforms use Clang 20.1.2, Release
`-O2 -DNDEBUG`, x86-64-v2, exact math, register locals off and stack forwarding
off. Linux assembly/linking uses LLVM20, metadata utilities LLVM18. The
production guest wraparound/no-contraction flags are checked on emitted
objects; supported sanitizer calibration checks remain separate.

| Profile | Generator binary SHA-256 |
| --- | --- |
| windows-native | `a2ad714cd14dc9f28d1ba910e6bfb5cbad4d298fef497d68c761963de01256b1` |
| windows-ubsan | `0a107df6693c7109c68381d4fd338b0ede3706d4dfae8b58538327f87b577b75` |
| linux-native | `790bffa833828becde89a24e5f2e2c9c1d0755d5a63976abb469300aa3044005` |
| linux-asan | `790bffa833828becde89a24e5f2e2c9c1d0755d5a63976abb469300aa3044005` |

Each actual generator binary is retained separately; Windows native/sanitizer
builds have different binary hashes, while their emitted bytes match. No
bit-identical compiler/linker-output claim is made. Compiler identities:
Windows archive `8e771a685cd718303ea0d632a8a95ad7b3cb17068f3952fbefa64a77290324d8`, files
`300ca7cd9b2d224ef1e57b70fa3351166047bb313de6b49ae2fbc7becbaef3d7`;
Linux binary `b15e7640bf3082f36ef14321711706b265df3058721e3c2caef3a4b83895d07d`.

| Approved input/module | Windows SHA-256 | Linux SHA-256 |
| --- | --- | --- |
| preparation_sha256 | `4744ae8546dd7f79728dbbb5f53afb66bca983d2b2e58a28ac495780af8ac8f8` | `c1996460def39792edb3cb6ee94abf6606c760aeeb59fdd07999e1766c20e00d` |
| sdk_tree_sha256 | `8e0ac9324376d04668025dd8c97caa680c45c3d329d80f49f0ab0b28f9787f4d` | `0704f49b704ed1f2d015c8c6860674e616b13280a86b6b3f928b8e169d9ceb5e` |
| loaded rexbase | `b9fa2b6e94ed6bd2d952d0c8e03a743da0a769eba43a0ca3e6524511475f05ff` | `b50211be9ada217a59b19a3356325fca9efa3665af8c7f9eae394cf52c6674b4` |
| loaded rexkernel | `98affe3840672b7b75cb92e6430d8a599e389c46eeae997c8c25d5d1b82ea415` | `a08af4c04d13aff9759d1cb2fc36820173bd119dd6a40757659a00e976de6220` |

Native and sanitizer processes load identical approved SDK bytes per OS.
Those are the reviewed memory-profile SDK derivatives, not a new production
package or integration of later thread/allocation repairs.

| Maintained input | SHA-256 |
| --- | --- |
| `tests/ppc_reservations/__init__.py` | `005968a953091e26becb75148418187a7737a57731485eec99d23fc07a6677b9` |
| `tests/ppc_reservations/CMakeLists.txt` | `ed5fbb33ddc1fff75c8f48dab0f8677397a4ed4182be81294dd1f03cdead8060` |
| `tests/ppc_reservations/fixtures.s` | `02b90489150dc39a992a82ba319289cbf23d611000fd31a5f3c62187ceb534e1` |
| `tests/ppc_reservations/oracle.py` | `6517b9401e6d671aeb96a9d6ad62d29263adc7868914b8cc1e57a57888bb8281` |
| `tests/ppc_reservations/runner.cpp` | `9e1cd8f26ff6e86b9a220e757902e0dbf9ff30cead37e4402e13d6d63dcf66fc` |
| `tests/ppc_reservations/test_driver.py` | `504b6bc98ca1f6773439e508b0dd2daf445a719655eca76fecb89de217b18650` |
| `tests/ppc_reservations/test_oracle.py` | `be9db633f522cea3137c6014d3237bdc669ae790499f1334860aa32dd41b5f05` |
| `tools/test_ppc_reservations.py` | `d748f104414ad3644d1f6f98791f8f65a54882ef3f21ea2c22305296107cbe7b` |

The two emitted-file hashes agree across all four profiles:

- `ppc_config.h`: `53f136e9061095fdb5cc4f4e7485cc4ef5a68821e538cee8fe5edac5542ec35a` (16811 bytes).
- `ppc_test_functions.cpp`: `1ea720b651984ba3ac6bbb64a860954161619b1cc244f75b1fbbbab2ef200d5f` (3012 bytes).

## Timing limits and implementation decision

Three fresh common-seed processes per profile retain every timed operation:
864 load and 1,152 conditional-store dispatches per process. There is no
discarded warmup; cold first operations remain included. The interval includes
host name dispatch plus an actual generated fixture and clock overhead,
excluding subsequent JSON capture/oracle checking. These are synthetic
diagnostic observations on one i5-11400 (6 cores/12 threads), about 32 GiB RAM,
Windows 11 build 26300 / WSL Ubuntu 24.04. Background activity is uncontrolled.
They are not a controlled OS comparison, instruction microbenchmark or MW3
frame-time/input-latency/performance result.

| Profile/dispatch | Three medians (ns) | Three p95 (ns) | Three maxima (ns) |
| --- | --- | --- | --- |
| windows-native load | 0.0, 0.0, 0.0 | 100, 100, 100 | 2800, 2300, 1600 |
| windows-native store | 0.0, 0.0, 0.0 | 100, 100, 100 | 600, 800, 300 |
| windows-ubsan load | 0.0, 0.0, 0.0 | 100, 100, 100 | 2700, 2400, 2200 |
| windows-ubsan store | 0.0, 0.0, 0.0 | 100, 100, 100 | 500, 800, 400 |
| linux-native load | 25.0, 25.0, 27.0 | 48, 65, 43 | 409, 6052, 8355 |
| linux-native store | 27.0, 28.0, 29.0 | 52, 60, 47 | 248, 353, 236 |
| linux-asan load | 112.5, 104.0, 111.5 | 232, 207, 219 | 566, 477, 11829 |
| linux-asan store | 111.0, 103.0, 117.0 | 212, 203, 241 | 8799, 744, 5208 |

Windows medians of zero reflect 100 ns quantization of short intervals,
**not zero instruction cost**. Median native Windows cost is unresolved
at this resolution; a future eligible performance comparison needs batched
windows and matched correctness work. Nearest-rank p95 and central-mean
medians are recomputed independently from all retained raw samples. Tails
are kept. Native and sanitizer costs remain separate. Per-run maxima
and sanitizer distributions are retained rather than silently trimmed.

Decision: keep the bounded diagnostic and require a separately agreed
correctness repair before treating this path as reservation-equivalent.
Correctness fails the tested transitions, so a fast value CAS cannot win
by skipping invalidation. Licensing/provenance permit this original source
investigation, not game-linked distribution. Performance (30%) has no eligible
comparison; stability (25%) has reproducible failures and cleanup limits;
maintainability (20%) favors retaining the existing unchanged generator rather
than another translator; integration effort (15%) remains tied to an agreed
reservation/invalidation/scheduling contract; hardware compatibility (10%)
lacks console/physical-tier evidence. All numeric scores remain unknown.
No fastest-framework or title-speed conclusion follows.

Final public checks: Windows Python 3.12.14/CMake 3.31.6/MSVC 19.44
`python tools/check.py --config Release` passes **230 Python tests/eight
explicit skips plus parser CTest 1/1**. Linux Python 3.12.3/CMake 3.28.3/GCC 13.3
`python tools/check.py --config Release --sanitizers` passes **230 tests/two
Windows-only skips plus parser 1/1**. Fifteen new pure-Python tests pass on
both hosts; public green checks do not erase the private CPU failures.
