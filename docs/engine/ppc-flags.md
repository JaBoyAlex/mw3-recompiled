# Conditional-store SO propagation — MW3-048

The selected emitter left CR0 SO unchanged after `stwcx.`/`stdcx.`. The actual
instruction observations in [MW3-047](ppc-reservations.md) show why that is wrong
when initial CR0 SO differs from XER SO. This opt-in profile adds one emitter
statement that copies current XER SO to CR0 after either compare/exchange
outcome. No reservation validity/invalidation, ordering, CPU ABI, memory/kernel
service or startup allowlist is changed.

The profile fixes that flag behavior only. The independent reservation oracle
and original inputs are unchanged, and remaining lifetime/ABA failures must
continue to fail. It does not establish full PowerPC/Xenon compatibility or
playability. The architecture reference and defined/spurious/undefined bounds
are recorded in the original audit; no mismatched-address result is invented.

## Isolated construction and provenance

`tools/prepare_ppc_flags.py` first verifies an existing approved **native memory
profile** SDK/source receipt. It reads those sources and libraries without
modifying them. A fresh exclusive private output contains one copied emitter
file, the original project MW3-038 fixture adapter, a separate build and its
generator executable. The pinned patch is applied only inside that output.
Existing destinations, source/profile/patch/adapter/license changes and a patch
exceeding the one-line/one-file scope are refused.

The exact target is pinned ReXGlue
`ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d`,
`src/codegen/builder/memory.cpp`. Before/after file hashes, the patch hash and
original adapter/license identities are locked in
`config/toolchains/rexglue-conditional-so/lock.json`. The private CMake target
removes the original emitter translation unit and substitutes exactly its
verified overlay; every other translator input remains the approved source.
Compile-command verification requires exactly that overlay at `memory.cpp`.

The overlay's private Git operation forces LF and disables whitespace rewriting
per command, rather than changing user/global Git configuration. An initial
synthetic Windows test exposed inherited CRLF conversion; that fixture failure
is retained separately from the accepted preparations. SDK source bytes remain
unchanged. The patch is original BSD-3-Clause contributor work with the target's
copyright/license preserved; the original preparation/CMake/adapter tooling is
GPL-3.0-only. [NOTICE](../../config/toolchains/rexglue-conditional-so/NOTICE.md)
records that split. No SDK, binary, generated output, game content or private
receipt is published, and no game-linked distribution permission follows.

The prepared generator is the bounded **fixture adapter**, not the production
XEX discovery/generation CLI. Do not replace the production generator by
renaming it. Production adoption requires a separately agreed composition,
rebuild/regeneration and title-checkpoint task. No existing SDK/source cache,
package, generator or selected production recipe is overwritten here.

## Explicit diagnostic selection and negative controls

The baseline command for `tools/test_ppc_reservations.py` remains the default.
`--flags-report <prepared-manifest>` explicitly selects the new profile after
verifying its SDK, producer, profile files, compiler/tool, overlay, adapter,
compile-command and executable identities. An invalid opt-in receipt fails
before output or execution; it cannot silently fall back to the old generator.

The diagnostic copies that immutable generator into its own attempt before
running it. Library byte/path checks still identify the unchanged actual SDK
kernel/base modules. Repeated generation must match, and Windows must match a
Linux fixture reference with the **same selected generator profile**. A baseline
reference cannot certify the fixed profile. The original strict nonce, complete
typed observations, case ordering, resource cleanup and result controls remain.

Prepared-profile observations explicitly record generator SO patch application,
unchanged runtime SDK and unrepaired reservation lifetimes. Their overall
compatibility result can remain FAIL; that is not hidden behind passing flag
checks. Wrong-result controls still execute an actual defined load then mutate
one observation; incomplete controls clean up and omit ordinary completion.
The existing timeout test requires captured plausible output before expiration.

Eight new Python tests cover exclusive real Git patching of original synthetic
text, wrong-path/source rejection, changed receipt/artifact/SDK/tool identities,
invalid SDK before output, no opt-in fallback and profile-mismatched references.
Their receipt/compiler fixtures do not load or certify an SDK. The existing
fifteen independent transition/evidence tests remain in place.

## Reproduce locally

```text
python tools/prepare_ppc_flags.py --root <private-runtime-root> --sdk-report <approved-native-memory-manifest.json> --output-root <new-private-generator-output>
python tools/test_ppc_reservations.py --root <private-runtime-root> --sdk-report <approved-native-memory-manifest.json> --output-root <new-private-diagnostics>
python tools/test_ppc_reservations.py --root <private-runtime-root> --sdk-report <approved-native-memory-manifest.json> --output-root <new-private-diagnostics> --flags-report <prepared-generator-manifest.json>
# Repeat diagnostics with --sanitizers; Windows also needs --reference <matching-linux-output>.
python -m unittest discover -s tests/ppc_flags -p test_*.py -v
python -m unittest discover -s tests/ppc_reservations -p test_*.py -v
python tools/check.py --config Release
python tools/check.py --config Release --sanitizers
```

Preparation uses the approved pinned Clang 20.1.2, a native SDK and two workers.
The SDK-facing fixture target uses C++23 for its existing headers; the public
project remains C++20/Python standard library. Each output, temporary directory,
context/address space and process belongs to this lane. Builds are serialized
here, and no GPU, game inputs, physical audio/controller or production service is
used. Public CI runs only game-free tooling/guards; actual SDK validation stays
private and local, independently of hosted Actions allowance.

Windows host/generated UBSan traps and Linux host/generated ASan/UBSan cover
the observed instruction path. Native SDK and generator internals remain
uninstrumented. Explicit memory release, private address-space destruction and
SDK-tracked thread recovery are bounded observations, not every OS allocation,
general race freedom or hardware context-switch proof.

## Decision boundary

Correctness requires copying the flag even when that adds work. There is no
new allocation, lock or reservation manager in this patch; that is source
inspection, not a measured zero-cost claim. Compare matched raw dispatch tails
over three independent processes and retain timer quantization, cold first
operations and sanitizer costs. These observations cannot establish MW3 frame
performance, a fastest framework or a performance win by ignoring reservation
failures. Missing architecture scores remain unknown.

Broader reservation repair still needs a separately agreed CPU/memory/thread
contract covering validity, consumption, invalidation/aliases, scheduling and
forward progress, plus regression and owned-title evidence. The lead's guarded
startup/allocation lane and the other instance's input interfaces remain
untouched. Self-review only; no independent review is represented.

## Recorded local evidence — 2026-11-19

These are original synthetic instruction executions against the actual selected
SDK, on one Intel Core i5-11400 machine: Windows x64 and WSL Ubuntu 24.04.
They are not console-reference, separate-machine, title or gameplay observations.
Clang 20.1.2, Release O2, x86-64-v2 and the existing native memory-profile
packages are held fixed. WSL uses GCC 13 headers and LLD 20; native Windows
uses its verified MSVC environment. Build concurrency is two, with suites
serialized. The private receipts retain full commands and tool/environment
identities; published hashes below identify them without publishing private logs.

Each profile executes three independent same-seed processes, reversed order,
one held-out seed, wrong-result and incomplete-output controls. Every ordinary
process has 672 cases. Baseline reports 240 PASS / 432 FAIL; the derivative
reports 368 PASS / 304 FAIL. Each command exits 1 because compatibility still
fails. Both negative controls pass their detector expectations. Across eight
profiles that is 40 ordinary FAIL outcomes and 16 expected-control PASS outcomes,
not 56 passing compatibility runs. Each variant has 13,440 repeated case
evaluations; these are not distinct instructions or a compatibility percentage.

| Profile | Five ordinary processes: PASS / FAIL | Store SO mismatches | Private manifest SHA-256 |
| --- | --- | --- | --- |
| baseline-linux-native | 1200 / 2160 | 2880 | `456cb23e6986824a84a712e4b13faa25101d0b6547cf38e9163383d4c3de75de` |
| baseline-linux-asan | 1200 / 2160 | 2880 | `2dfbc7bbcfb5dc3bbe38fbada85377bef418a179625c94204149d3d71d452498` |
| fixed-linux-native | 1840 / 1520 | 0 | `6c2eb944455ff8523327c380ff1c32cfeadb8e79777fb012ad6adf5a7a658447` |
| fixed-linux-asan | 1840 / 1520 | 0 | `d2d27b18abf53038e1413df0b7a1e571b08d21e9e56bbc7cd39686dfa3e0eec8` |
| baseline-windows-native | 1200 / 2160 | 2880 | `c574b9d4c06ffeaf3f4bdb6e038332763cb3dfacd2d10e6f3ea2b87021f09d6e` |
| baseline-windows-ubsan | 1200 / 2160 | 2880 | `9c8ebbbd8566d699e7b91377d4d220033eb1f5b97383e3c6d4727775489036f3` |
| fixed-windows-native | 1840 / 1520 | 0 | `9c0c56a725d06bd85aba868caae15eac232e5ef00228be713494c4b7b11aa8d7` |
| fixed-windows-ubsan | 1840 / 1520 | 0 | `44175ac6c7a656619a025d3a7725e8725ed2582bab270c11a278252f73570a8a` |

The 11,520 baseline store SO mismatches become zero in the derivative. Both
observed compare/exchange outcomes are covered (4,360 successful and 1,400
unsuccessful stores per profile across the five ordinary processes). Those
outcomes and all unrelated observations are unchanged. Each matched profile
compares 10,080 step observations; 3,120 change SO, including its propagation
through subsequent loads in the same context. Across four matched profiles,
40,320 step comparisons preserve r3, XER SO, memory, guards, preserved registers
and CR0's lower three bits. CR0 error checks fall from 768 to 304 in the first
process; reservation checks remain 304 and memory checks 312. These overlapping
check counts are not case counts. Remaining CR0 EQ errors are not fixed by SO.

The generated C++ differs by exactly four `ctx.cr0.so = ctx.xer.so;` lines,
covering each width/outcome. Removing those lines reproduces baseline output
byte-for-byte; `ppc_config.h` is identical. Repeated generation and same-profile
Windows/Linux cross-host comparisons pass. Existing source/oracle/fixtures,
SDK package/source bytes and actual loaded kernel/base bytes remain unchanged.
All retained artifacts and producer/source/helper identities were rehashed.

The original MW3-038 14-function fixture also emits byte-identical files with
both new baseline and derivative generators on both hosts. This is an emission
regression check against original passing receipt
`024d6ea35d1726f27673921cfb7be62b3aafbe86785dec8646da427add8ec029`;
it is **not a new execution of its 2,410 cases**. Its generated C++ hash remains
`6a3d48ce3b582e7958fd428705bd2a7fbfe2677d4fe58d09cafbec8ced34a52e`
and header hash
`53f136e9061095fdb5cc4f4e7485cc4ef5a68821e538cee8fe5edac5542ec35a`.

### Exact preparation and execution identities

| Artifact | SHA-256 |
| --- | --- |
| tools/prepare_ppc_flags.py | `58d12030205abdac7b0d27a0a53338a62e31727705bad61b0802c03e4292823b` |
| tools/test_ppc_reservations.py | `e6311238a892a493035c4354575729ed0c7212716fc7690a8f291630f477fff1` |
| Unchanged reservation fixtures.s | `02b90489150dc39a992a82ba319289cbf23d611000fd31a5f3c62187ceb534e1` |
| Unchanged reservation oracle.py | `6517b9401e6d671aeb96a9d6ad62d29263adc7868914b8cc1e57a57888bb8281` |
| Unchanged reservation runner.cpp | `9e1cd8f26ff6e86b9a220e757902e0dbf9ff30cead37e4402e13d6d63dcf66fc` |
| Profile CMakeLists.txt | `61da4a95b2a1f92c6a816282d32e09ed5aef338c66e876f565491435e0010873` |
| Profile NOTICE.md | `d0372ca58e9e19fa628289bf4b451cdd01016ffe31debe6413111d48b1032b82` |
| Profile atomic-so.patch | `6ee793ae387d918d89890d1b9588eca0b8a5effa0ee3000866b0ab1edc60b3e3` |
| Profile lock.json | `95463e816e3bfef8884266d9a206cc0448857459f29671cd300e7e77bf35e96f` |
| linux generator preparation receipt | `6b1bd708404bd6cbc52603b0506598298db62c872276f1202884d870911391ad` |
| linux prepared generator | `6dcc84743b21534add217ab487b35670b3a4d1bbc84efa02a03bc82bc390b8d4` |
| linux compiler executable | `b15e7640bf3082f36ef14321711706b265df3058721e3c2caef3a4b83895d07d` |
| linux SDK tree | `0704f49b704ed1f2d015c8c6860674e616b13280a86b6b3f928b8e169d9ceb5e` |
| linux native SDK receipt | `c1996460def39792edb3cb6ee94abf6606c760aeeb59fdd07999e1766c20e00d` |
| linux actual loaded rexbase | `b50211be9ada217a59b19a3356325fca9efa3665af8c7f9eae394cf52c6674b4` |
| linux actual loaded rexkernel | `a08af4c04d13aff9759d1cb2fc36820173bd119dd6a40757659a00e976de6220` |
| linux unrelated-emission receipt | `a318cfd54cf7c8643b4eac562c6030c8280ae13db97a22f0f72fe5b7644aceb7` |
| windows generator preparation receipt | `faa6d19ce4eba729bfed75090f491686e9a7112156454eb9e8bb1f63d642d7d0` |
| windows prepared generator | `5bc3bc13f14f00dfc9a9b5390e14fa213f9680d1c6f467fa3de0ad4866ccff32` |
| windows compiler executable | `0eb656a5c9f59d040a3a1cfd09a0dfabc22241528ea917ad07daa1d9037e2d15` |
| windows SDK tree | `8e0ac9324376d04668025dd8c97caa680c45c3d329d80f49f0ab0b28f9787f4d` |
| windows native SDK receipt | `4744ae8546dd7f79728dbbb5f53afb66bca983d2b2e58a28ac495780af8ac8f8` |
| windows actual loaded rexbase | `b9fa2b6e94ed6bd2d952d0c8e03a743da0a769eba43a0ca3e6524511475f05ff` |
| windows actual loaded rexkernel | `98affe3840672b7b75cb92e6430d8a599e389c46eeae997c8c25d5d1b82ea415` |
| windows unrelated-emission receipt | `66375d3aca899b6a59452cbba7bde8127fc886a5cce1f36a4ef2ade73b52e5dd` |

| Profile | Actual generator SHA-256 | Actual runner SHA-256 |
| --- | --- | --- |
| baseline-linux-native | `790bffa833828becde89a24e5f2e2c9c1d0755d5a63976abb469300aa3044005` | `f8a5d6eeb7e39d7da39513b4388db1d3e84317fe37655a420c587efa79dd8869` |
| baseline-linux-asan | `790bffa833828becde89a24e5f2e2c9c1d0755d5a63976abb469300aa3044005` | `b60b1c12c9e530c8093abb1603f2ca0caba0f8fe87b5cc15a03e56d79c4c1653` |
| fixed-linux-native | `6dcc84743b21534add217ab487b35670b3a4d1bbc84efa02a03bc82bc390b8d4` | `ddce1550add6960d08b67af260e7b55d1e012bd85cd07d369bb40b59d2a131b5` |
| fixed-linux-asan | `6dcc84743b21534add217ab487b35670b3a4d1bbc84efa02a03bc82bc390b8d4` | `e2f10f7b21c2544af675362b098959f6d6761fa57c572e73053ade35fc07c5ec` |
| baseline-windows-native | `1bd939ff328e76ce937bd5a6d9d11f2bec3baac3e47662913764b99cff7bd4c2` | `f9874e5f9267b23e740488d4f809ab68167f30ee32a0a2349e866ef86f132513` |
| baseline-windows-ubsan | `ee29b685fc4a4ee0ecb43a4a4689aefe0ab4f529527a4c5e798cd47a35badd64` | `72e7f6402d433bfe77772462ce4bcb9058bdf23d7b3eec3089d3bf539279ace7` |
| fixed-windows-native | `5bc3bc13f14f00dfc9a9b5390e14fa213f9680d1c6f467fa3de0ad4866ccff32` | `ca464c39ef668494913b154a430b3e722ebb9942c3aa9b36f214a1dba98dc50e` |
| fixed-windows-ubsan | `5bc3bc13f14f00dfc9a9b5390e14fa213f9680d1c6f467fa3de0ad4866ccff32` | `09bf08598a5f324e49c0112c7e6aa2c80478c0b4bf7a5024a053998287bc9307` |

The lock binds the exact before/after emitter, adapter and upstream-license
hashes; the tables bind the producer, profile, libraries, generators and executed
runners. Receipts additionally bind every assembly/map/generated file, tool,
case seed/order, log and command. No binary or receipt is part of this PR.

### Dispatch observations and decision

Each cell below lists three independent per-process values in nanoseconds.
Each process contains 864 timed loads and 1,152 timed stores. Timers bracket
named dispatch plus the emitted instruction fixture and clock overhead, excluding
JSON output and Python oracle work. There is no discarded warmup; cold first
operations are included. These are host dispatch distributions, not CPU/GPU
frames or input latency. Background activity was not controlled.

| Profile | Load median / p95 / max (three runs each) | Store median / p95 / max (three runs each) |
| --- | --- | --- |
| baseline-linux-native | 25,25,25 / 37,31,32 / 550,304,314 | 27,27,28 / 42,39,40 / 129,203,134 |
| baseline-linux-asan | 106,115,102 / 175,209,187 / 445,833,572 | 112,120,117 / 189,208,196 / 382,8710,792 |
| fixed-linux-native | 24,24,26 / 32,34,35 / 197,199,323 | 27,27,28 / 39,47,41 / 137,179,126 |
| fixed-linux-asan | 102,97,101.5 / 211,193,192 / 475,529,430 | 105,103,106 / 208,196,184 / 531,365,453 |
| baseline-windows-native | 0,0,0 / 100,100,100 / 2600,2700,1600 | 0,0,0 / 100,100,100 / 200,400,200 |
| baseline-windows-ubsan | 0,0,0 / 100,100,100 / 2300,2100,1300 | 0,0,0 / 100,100,100 / 200,500,200 |
| fixed-windows-native | 0,0,0 / 100,100,100 / 2500,2900,1500 | 0,0,0 / 100,100,100 / 200,200,200 |
| fixed-windows-ubsan | 0,0,0 / 100,100,100 / 2300,1300,1300 | 0,0,0 / 100,100,100 / 400,200,11900 |

Native Linux store medians are 27/27/28 ns in both variants. Native p95 changes
are small and inconsistent; instrumented runs have separate costs and tails.
Windows observations are quantized to 100 ns and contain many zero deltas;
zero median does not establish zero execution cost. The 11,900 ns fixed Windows
UBSan store tail is retained. These samples cannot prove a speedup or exclude
a small regression. No samples were removed to improve results.

Keep the opt-in, one-statement correctness repair for synthetic diagnostics;
retain baseline and visible reservation failures. The tested flag condition
passes, while full reservation correctness and game-linked distribution gates
remain unsatisfied. Performance 30%, stability 25%, maintainability 20%,
integration effort 15% and hardware compatibility 10% remain **unknown** as
MW3 architecture scores; no weighted total is calculated. A one-file source
surface is observed, but upgrade effort and production integration are unmeasured.
Production composition/regeneration, broader reservations and owned-title checks
remain separate tasks. No renderer/runtime selection or title performance claim
is changed by this diagnostic-only repair.

### Public verification and review

Windows `python tools/check.py --config Release` and WSL
`python3 tools/check.py --config Release --sanitizers` pass 254 Python tests
each (eight Windows skips, two Linux skips), plus parser CTest 1/1 each. The eight
new preparation tests and fifteen existing reservation guard/oracle tests run
on both hosts. Supported actual SDK fixture sanitizer results are recorded above;
native SDK/generator internals, Windows ASan and TSan remain unverified.
Task DAG validation (60 tasks) and repository artifact heuristic pass.
Plain staged `git diff --cached --check` reports one required blank context line
in the unified patch (line 10); it is not added emitter whitespace. All other
files pass that check with the patch excluded, and the patch passes actual
one-line/one-file replay plus exact resulting-byte verification on both hosts.
Manual scope/provenance review finds only the reserved
profile, preparation helper, diagnostic selection, new tests, this report and
MW3-048 JSON. No startup, input, shared runtime ABI, game input or SDK package
changes. Self-review only; hosted checks validate public code and do not replace
the separately identified actual SDK evidence.
