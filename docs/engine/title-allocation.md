# First owned-title allocation checkpoint (MW3-092)

This checkpoint admits one actual `NtAllocateVirtualMemory` call in each
hash-bound MW3 2011 SP/MP startup and stops **before returning to translated
title code**. It does not establish a rendered frame, menu, playable boot,
subsequent import, or retail-console ABI parity. MW3-011 remains unfinished.
The explicit header-only checkpoint remains the default.

## Identity and independent pre-admission evidence

The owner's Xbox 360 Rev 1 inputs are read-only. These executable identities
do not identify a title update, disc revision field or a generic "1.1" build:

| Role | Executable SHA-256 | Caller LR | Import thunk, ordinal |
| --- | --- | --- | --- |
| SP | `f59be1342c2fc664e2a2e7322d024028a0ca7216d279ed32fef6e114d8c37c30` | `0x824652e4` | `0x824e5e7c`, `0xcc` |
| MP | `ba1bc57af4c4f75934a106b3d470559b356252b9e100d98e335bcfd0e574806a` | `0x824e6f64` | `0x8256a114`, `0xcc` |

`config/runtime/title-allocation.json` binds each role's metadata, original
PPC call-site window, independent LLVM decoding and pre-call capture digests.
The explicit generation receipt SHA-256 is
`eacf6eed533a3e5a88dae07a68f6080fdd3be9d92bf5e9a8b4104eaf6d1ac52b`;
every generated payload file is verified before and after each run. Generated
title code is neither maintained nor published here.

An independent original XenonUtils image-loader adapter read bounded original
instruction windows before its import normalization. Raw branch decoding and
LLVM MC 18.1.3 agreed on the direct call from LR minus four to the per-role
thunk. The window was unchanged after normalization. This did not use the
ReXGlue translation as its reference. Private audit run
`122a40461a654aecae085b40249d6b42` retains source, compiler commands, decoded
words and assembly. The loader library SHA-256 is
`39731fa2c1590756cbcb033caa06eb42b492f8a5faabf04b14ddf1f41b2ff664`;
LLVM decoder SHA-256 is
`d2b9ff3e9dd1a2d5ad086cb1047d38ee0da60e62b03d69ef45231c0c6979a27e`.
No MW2 address is reused.

Both original call sites set r3 to r31+80, r4 to r31+324, r5 to
`0x60002000`, r6 to 4 and r7 from r27. Separate read-only title probes
stopped at the original unreviewed import without calling it: SP run
`0eebf1c24f0642b1bbfa1ef6ae935c20`, MP run
`c0526ad452df450386d90e5feab1e8fc`. Both observed initial base zero, size
`0x00100000` (1 MiB), region zero, r1=r31=`0x700cfa10`, with in/out words
at `0x700cfa60` and `0x700cfb54`. Their exact manifest hashes are in the
contract. These captures preceded admission and retain their original source
snapshots; later source revisions do not relabel them as final executions.

The reviewed selected-fork source interprets the flags as large-page, heap
and reserve, with no commit. Its heap flag has no independent effect in this
path. With base zero it selects a 64 KiB guest-virtual heap and rounds size to
64 KiB allocation granularity. Protection 4 is read/write and region zero is
accepted. These are selected-fork observations, not a retail ABI certificate.
The MW3-046 contract and MW3-091 repair receipts remain required foundations.

## Admission, oracle and recovery

`--checkpoint allocation` requires the explicit repaired `memory-imports`
SDK profile, immutable generation receipt, exact caller/argument contract
digest and completed dependencies. There is no verifier fallback. The
historical `stop` and `xma` profiles remain header-only options.
`--checkpoint allocation-inspect` validates the same caller and values but
never invokes the allocation export.

The maintained host verifies the complete import bindings, original header
oracle, exact LR and argument setup, nonwrapping aligned read/write in/out
words, manually decoded big-endian values and neighbouring snapshots. The
contract permits exactly one call and caps requested bytes at 16 MiB; these
executables must request exactly the independently observed 1 MiB. It resolves
the original export from the verified loaded kernel and rejects interposition
by the host stop function. No SDK patch, success stub, all-service enablement
or generated guest-source edit is involved.

After the real call, the independent host oracle checks zero status, big-endian
output words, nonzero 64 KiB alignment, exact rounded size and nonwrapping
geometry. Heap queries at both ends must describe the same reserve-only
allocation; checked edge spans must remain inaccessible, title-page accounting
must remain unchanged, and bytes surrounding both output words must match
their snapshots. The reserve-only region is never dereferenced as committed
memory. The existing private SDK diagnostic accessor is hash-bound along with
the selected source/package; it does not modify the SDK.

The probe throws its diagnostic thread stop before returning from the import
trap. It checks stopped guest-thread metadata, exit status, runtime unload,
full `0x120000000` mapping release and equal before/after host thread counts.
The allocation is released by runtime teardown. The next guest instruction,
next import, unaudited data-variable access and first frame are unobserved.

Every new-checkpoint process echoes its fresh nonce before binding checks.
The producer requires exact input/result/stop event sequences, the actual
loaded kernel hash, complete recovery and immutable source, generation,
compiler/package and executed-binary identities. Output roots cannot overlap
owned inputs, metadata, generation, selected receipts/packages, SDK source or
build/install/preparation caches, or maintained host/tool/config inputs.

The actual controls change the allocation binding, misalign its in/out pointer,
compare a validated result against an intentionally wrong size, omit the
completion footer after otherwise normal recovery, and exceed a five-second
deadline after a validated allocation. The incomplete/deadline cases are
accepted only as rejection controls, never as successful startup evidence.
The deadline control is terminated by its owning driver; it intentionally
cannot demonstrate in-process cleanup. Ordinary positive, wrong-result and
pointer controls must demonstrate recovery. Original header binding, pointer,
oracle and interrupt controls remain part of every suite.

## Reproduction

Use private paths to verified owner inputs and receipts. The same commands run
on native Windows and Linux; append `--sanitizers` for host instrumentation
or the supported Linux participating-kernel preparation. Do not select an
unverified receipt simply because its filename matches.

```sh
python tools/verify_kernel_gate.py --root "$SDK_CACHE" --sdk-report "$REPAIRED_REPORT" --sdk-profile memory-imports --owned "$OWNED_REV1" --metadata "$ANALYSIS" --generation "$GENERATION" --expected-generation-sha256 eacf6eed533a3e5a88dae07a68f6080fdd3be9d92bf5e9a8b4104eaf6d1ac52b --role sp --checkpoint allocation --expected-allocation-contract-sha256 d7339f9a99a4d357faf1893a266213030807363dcc727604d95c7e87c1f49be7 --output-root "$PRIVATE_RUNS"
```

Repeat with role `mp`, then `--checkpoint allocation-inspect`. To reproduce
the original header boundary, select `--checkpoint header --sdk-profile xma`
and its verified original XMA receipt; omit the allocation contract argument.
Each run uses isolated writable app/user/tmp/config profiles. CMake builds
use at most two workers and heavy builds are serialized. No GPU suite runs.

```sh
python -m unittest discover -s tests/lifecycle -v
python tools/check.py --config Release
CXX=clang++-18 python3 tools/check.py --config Release --sanitizers
python tools/project.py validate
python tools/check_repository.py
git diff --check
```

## Acceptance evidence

The final matrix has **246 processes PASS** with 246 distinct nonces:
120 allocation-checkpoint processes, 70 read-only inspection processes and
56 original-XMA header-only regressions. Allocation positives repeat three
times for each SP/MP role on five profiles (30 positives). Thirty additional
wrong-oracle/incomplete/deadline controls each execute one validated actual
allocation before their intentional rejection: 60 real calls in total.
Neither inspection nor header-only mode invokes that allocation export.
No sanitizer or crash diagnostic is accepted as a passing control.

Each run received a separate artifact audit of its retained source copies,
compiler, SDK receipt/package/source, immutable generation and metadata,
compile commands, binary/copied DLLs, actual loaded kernel, case log hashes,
nonce and protocol. The original header classifier AST and CMake source are
unchanged from the merged baseline. Individual log and trap/header hashes
remain bound by the private manifest digest below; no raw trace is published.

Source SHA-256 identities:

- `tools/verify_kernel_gate.py`: `53407a1bdf4f82c34eb80880076f0d80ebb16f3954868615e29fdc57e9a03f0d`.
- `runtime/lifecycle/checkpoint.cpp`: `403cd7348f8fcd6a784c2387fe0d915c5fd5b1fd6142ac59d284463b1401611e`.
- `runtime/lifecycle/CMakeLists.txt`: `982b93627b6675f9770945f26e4ef8e6601b7dbd1bde626b793675a0cb857388`.
- `config/runtime/title-allocation.json`: `d7339f9a99a4d357faf1893a266213030807363dcc727604d95c7e87c1f49be7`.

Actual allocation binary SHA-256 identities:

| Profile and role | Probe binary | Loaded kernel |
| --- | --- | --- |
| linux-native-sp | `1e13a372c94a21fab568b9f902c89a5e7824540c984f3eaa6dba77d708f64bba` | `828fc85eabd1c07bfa32dadf92ee2a6547a44444fde945a9384b9ae56169139b` |
| linux-native-mp | `1883b73c3b19455ee3e53fa392f66427ba3ef6a7a66921a36aeeec430ebdb995` | `828fc85eabd1c07bfa32dadf92ee2a6547a44444fde945a9384b9ae56169139b` |
| linux-host-sp | `c33e7000477e65eca14bc5ce3f4b55423b2e719897df45f46833573617a363c9` | `828fc85eabd1c07bfa32dadf92ee2a6547a44444fde945a9384b9ae56169139b` |
| linux-host-mp | `ddae018f8daf8b33b9b80dc782a37ef7434089a18fe728c8e86347a71e10160b` | `828fc85eabd1c07bfa32dadf92ee2a6547a44444fde945a9384b9ae56169139b` |
| linux-core-sp | `c650d756ebd3eb67ece9ba7a5d5797c9cd23b5b3f06c5a745a47d089436bda55` | `ef88723255d88a31f092eff0a169782b8bca8611442330e7588058838adfdce6` |
| linux-core-mp | `c172db53c32e0d24bb5cef5b99ba727452f1e40a76b6681456c3bc9b4b2d6bda` | `ef88723255d88a31f092eff0a169782b8bca8611442330e7588058838adfdce6` |
| windows-native-sp | `24397664af619ee1bb3c8c84e195f054903339a03092c68259f1aadfdedc2616` | `aaa93ebbfa3706ae54ac5aaae33931651abf79d4b976299cd2164c48224f3d92` |
| windows-native-mp | `e432768adf174161ac9dfef573348d98c3568269719494ee33740f0ee3a61d4b` | `aaa93ebbfa3706ae54ac5aaae33931651abf79d4b976299cd2164c48224f3d92` |
| windows-host-sp | `5359b13f654ad6ae926812bfe148a67bef7edd02e5079dbdd39f606b0c758caf` | `aaa93ebbfa3706ae54ac5aaae33931651abf79d4b976299cd2164c48224f3d92` |
| windows-host-mp | `ec6580795e4a2bf366633d91321ad2c0f3a1980558debf3880487c03b097be3d` | `aaa93ebbfa3706ae54ac5aaae33931651abf79d4b976299cd2164c48224f3d92` |

Exact SDK and compiler identities (shared across both roles):

- linux-native: SDK preparation manifest `7e60b272ab13c51d02a585052499a96bf83fc6c7762da43bb7be2f6c31fe8bff`; compiler `{"sha256": "b15e7640bf3082f36ef14321711706b265df3058721e3c2caef3a4b83895d07d", "version": "Ubuntu clang version 20.1.2 (0ubuntu1~24.04.3)"}`.
- linux-core: SDK preparation manifest `633ee7dfc40f38147c9590df73bc46220d4b624daa6365e6d446e07feff897a2`; compiler `{"sha256": "b15e7640bf3082f36ef14321711706b265df3058721e3c2caef3a4b83895d07d", "version": "Ubuntu clang version 20.1.2 (0ubuntu1~24.04.3)"}`.
- windows-native: SDK preparation manifest `1922f16daff43554a6aef5cdba4b034e9700330267cdfadf72d787eea4a6ab3d`; compiler `{"archive_sha256": "8e771a685cd718303ea0d632a8a95ad7b3cb17068f3952fbefa64a77290324d8", "files_sha256": "300ca7cd9b2d224ef1e57b70fa3351166047bb313de6b49ae2fbc7becbaef3d7", "version": "clang version 20.1.2"}`.

Retained acceptance run IDs and manifest SHA-256 identities:

| Suite | Private run ID | Manifest |
| --- | --- | --- |
| linux-native-sp | `347eb1e7d2784d8b90230195db565cbf` | `1615c446e4ddd6573f3898fc27528368caba16ecbadc78f152e697e4944648a0` |
| linux-native-sp-inspect | `fc2aed17de224a699c231b2b50eba886` | `b95497fa0149cdb35157dceee3ccf178d9789ff288e4edc2774b80adabbbc083` |
| linux-native-sp-header | `5ddab1b690da498aa3121499666ef6c9` | `2bfc7cbeacf15e5c8ba7299395d3536f4a8df40d23c49b79a158a8f757ff7547` |
| linux-native-mp | `ad45c1cf327743ad91359549cf5deb41` | `fe0841a295dd5c7f89b4fa0f389968a465b90c50dceda28e0fc8fcccebfa488d` |
| linux-native-mp-inspect | `816240fa04094dd7951783d1d42760c6` | `6832080e88e9167861dd787f52c0cf8cca07a5c6341e54ee05c0fa25efe24dc9` |
| linux-native-mp-header | `d35cea8fd4cb44c1b1cbaa75b4f64268` | `ebda455b85c9eff51ca60334d32d1dc94ca316b1bbc9df696ef21d0d01a1bc07` |
| linux-host-sp | `1caa8b40b5464bd6a48039b17eb8a6f4` | `3bb883c93fecd7b46904c0cfb27ad5c4a6c797defb500cabba0f46a457f80268` |
| linux-host-sp-inspect | `7d6990b615d64a6abece8a17366768b8` | `d7b0c5630daa9f1ce3ce16e25afcb2c8778556e1253d2dc3b0e4ee10e342fde9` |
| linux-host-sp-header | `fa5278d4d4e24065a1a785d03848538d` | `8a93e9cbc6cb376d9a7b007a4013dfca6d51645cf5ead00c9933f967b4862cd7` |
| linux-host-mp | `656e5dc43db6455188f90b09ad7a894e` | `5c2169112a4baac56983ccdeb58edd47700e1b9fe7de547c1a06cff2bb4f63e6` |
| linux-host-mp-inspect | `41f8d3815872458f97a957e0192b6de9` | `f9a456387681fa76dd737b9b6e1d7fb284db441a69395f6ba06c03d5aa0fb5a5` |
| linux-host-mp-header | `9a3c367788b24518824bf0ebe7ff0b05` | `65b61bc7bcbc5e7416ba69701355d484dae653ab50957dd7a02676952c97c1c4` |
| linux-core-sp | `1a6d0343a46c45898dbc84a1f81710e1` | `17ba435f1570d8472ce52a3065fb73f00d47276d3d30c2de16f9650673c64efe` |
| linux-core-sp-inspect | `b337338b59a847fb8d30f1566a40bb80` | `0bc99c3b2caaf7b1ada05672630890de8ee54666dd822813ce03ad1530e40815` |
| linux-core-mp | `6e96a56b1d7b4592b139cad6ceddbb34` | `d2908ca7fa5bd9b9d0e725c4e37425fc81a22d5aaf6787c989363b2a270744b7` |
| linux-core-mp-inspect | `18ea768fd4884bc7b300c473172678b3` | `3ce55e331b6095d406949fac0dc7334d0779032f28ca05048cd4bbd4022cf1bf` |
| windows-native-sp | `51b420b55b07482ba9df91aaab234be8` | `0038c502eae0d9bffaafae405deb55670488542f86ac143a664655b7e9679ed3` |
| windows-native-sp-inspect | `a010d9a41bcb45f7bb2f72a305c1b580` | `fa6873992e3f137ae23c7fbd1c75a998149d411012644655a0d0af978b440e2a` |
| windows-native-sp-header | `2e8cbbbd76304d1aba934c490883ca30` | `77e7b07a00c0b30d4e84608bd4fbb144fa749c972a3dcfdda27a10002aa676a9` |
| windows-native-mp | `e0e615a52a894015a573870163b2cc8e` | `3a61bd13f988fbbfd39634285f63be4402e26373b9b51cb62e5aa6848d61acbe` |
| windows-native-mp-inspect | `ce00426761264f3b8854409ff17ebce3` | `e22962c47da3395549da21b06256a02ed775260ee24a5b90f600d9b678871abe` |
| windows-native-mp-header | `1da95c62c83a40eca019849ed58ea544` | `0f1ce99e63fc38ea20a5e3797f324f150eff7d85d21cebcdeea278c659932ec3` |
| windows-host-sp | `90d3ae265e054b4fa4757e243e90e302` | `dd292948937cd6fea67deee9d557f2b5a2436b51bc9ae1fb4b8959c833dbf32c` |
| windows-host-sp-inspect | `44c6f99aac7145e985e7d64de1538489` | `7bcdfef677093cff24368d20f98d7fa431317ddf45900e2337c2b586131dd485` |
| windows-host-sp-header | `462c7fb34fff4a6aa4d39798a650dcb3` | `6e008044fcbba26bec52b00e49f7a2e1c20bcd053cd1c234a1ada84b1452aaf0` |
| windows-host-mp | `64a30d7e78d94b80956197b4dbe76ef7` | `8c6796cf42003615209d29866d24c6b87228f7cb5a2b9e8a0c8fc3a2ec5b4ff9` |
| windows-host-mp-inspect | `72216b63cc0e4b678822882224578501` | `7037fb4eb6ecd09e78947b5da1658c5f6722b6816dffadd8271793088b1d30bd` |
| windows-host-mp-header | `5a70422a69074974b039f3ceedcbfee4` | `0723d57692e2448494f5816cc3285f85b20555dd028a502b1afb5b62b3c8181b` |

Twelve fresh real CLI identity-refusal processes PASS (six per native host):
wrong contract/generation digest, unreviewed SDK profile, tampered SDK receipt,
tampered generation and tampered metadata all exit 2 before output creation.
Windows refusal manifest SHA-256: `ff3a86c539c046183847ec2946fb5f3c45a600333064fd966e3b6fc4ffb8f79f`.
Linux refusal manifest SHA-256: `200fc5e8764e839cdfb926704dd2c9bcd9896033d71fdbda24def3f821d7b200`.

A deliberate live driver-source change also refused a complete 12-case Linux
kernel-sanitized development run, reporting `maintained lifecycle source
changed during verification`. Its retained run ID is
`6a6cc26bd38a4142b86c529cabae8cc2`. That run is excluded from the matrix above.
Self-review's reordered-cleanup fixture exposed the protocol gap; final
guards now reject cleanup before admission, late rejection records, and
unexpected unreviewed imports in allocation controls. All 14 focused lifecycle
tests PASS; these synthetic fixtures are not title-execution evidence.

windows-release: 327 Python tests, 8 explicit skips, parser CTest 1/1 PASS; log SHA-256 `353432476c867960f9417f52596773ae0309d3f334dd463c0721af69c7c1df17`.

linux-release-asan: 327 Python tests, 2 explicit skips, parser CTest 1/1 PASS; log SHA-256 `15c9bc6c629d8344c85b7b5228af14a0dcbc7d1dd049009f04418056f0408761`.

Windows skips cover unavailable FIFO/LLVM/symlink cases; Linux skips cover
Windows junction cases. The 67-task DAG, heuristic artifact check and manual
provenance/diff review pass. Native private probes use Clang 20.1.2, public
Windows parser checks MSVC 19.44 and Linux parser sanitizers Clang 18.1.3.
Linux/WSL is on the same Windows machine, not independent hardware.
No performance benchmark is claimed: this adds opt-in diagnostics and changes
no shipping renderer, framework choice or gameplay policy.

## Limits and review

Initial exact-head CI run `45126657829` passed all three Linux jobs but failed
both Windows jobs in the output-isolation fixture: the runner's short temp
alias was compared with the guard's canonical long path. The fixture now
resolves the expected path as well. Runtime admission, source/config hashes,
all output-overlap refusals and the 246-case title evidence are unchanged.

The first public Windows check passed 307 tests with 13 skips, but CMake/CTest
were absent from PATH for native Python fixtures. Supplying `--cmake` and
`--ctest` selects the top-level commands only. The final Windows run also puts
their binary directory on PATH to exercise those supported native fixtures;
the earlier log is retained and is not substituted for that full run.

Windows host sanitizer coverage uses calibrated UBSan traps; it does not
instrument the native kernel library. Windows participating-kernel sanitizers
are unsupported. Linux host and participating-kernel ASan/UBSan retain native
XAM/system dependencies and disabled vptr checks. Recompiled guest objects
are outside the maintained host instrumentation. WSL and Windows share one
machine and are not independent hardware results. No performance comparison
or fastest-framework claim follows from this diagnostic checkpoint.

The first admission build failed at compile time because the host initially
requested a private address-space member directly. No allocation executed in
that attempt. It is retained privately as
`320c5ba27c9342509f3f6905c68f0850`; the corrected host uses the SDK's existing
diagnostic accessor. The first corrected SP smoke passed but predates the
final nonce and edge checks and is not substituted for final acceptance.

Self-review only; no independent reviewer is claimed. The public change is
maintained diagnostic code, factual contract and tests. Existing BSD/Xenia
notices and GPL tooling provenance remain intact. SDKs, game bytes, decoded
or translated title code, private traces/logs, keys and binaries remain outside
Git. Dynamic loading and ownership do not imply distribution permission.
