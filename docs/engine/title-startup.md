# Bounded post-allocation startup — MW3-093

This checkpoint returns from the reviewed first reservation, admits one
independently audited commit using the existing selected kernel, checks the
title's following heap initialization and stops before the next service.
It does not establish a rendered frame, menu, playable mode or general heap ABI.
The supported local acceptance matrix and separate artifact review pass;
exact-head public CI and merge review are recorded on the linked PR.

## Identity and source review

Use MW3 **2011**, Xbox 360 USA/Korea Rev 1, the unchanged owner-supplied
[SP/MP identities](../../config/titles/mw3-xbox360-rev1.json), the MW3-091
memory-imports preparation, and the MW3-041 generation receipt
`eacf6eed533a3e5a88dae07a68f6080fdd3be9d92bf5e9a8b4104eaf6d1ac52b`.
The [startup contract](../../config/runtime/title-startup.json) binds each
role's original-source window, LLVM disassembly, owned data word, executable,
metadata and private precall capture. Its digest must be explicitly supplied.
The earlier [first-allocation contract](title-allocation.md) stays separate.

The private source audit observes the original loaded XEX before import
normalization, verifies the observed words remain identical afterward, decodes
direct branches independently, and reads the same window with LLVM MC 18.1.3.
The full enclosing-function window and its one accessed owned data word remain
private. SP and MP have separate addresses and signed data displacements;
no MW2 guest address or inferred retail symbol is used.

| Boundary | SP LR | MP LR |
| --- | --- | --- |
| Reviewed first reservation | `824652e4` | `824e6f64` |
| Following commit | `82465334` | `824e6fb4` |
| Next `KeGetCurrentProcessType`, not invoked | `82465438` | `824e70b8` |

Both native Windows precall captures observed a 64 KiB commit inside the
1 MiB reservation, type `60001000`, protection 4 and region 0. In/out words
are at the same audited frame plus 84/332. The original title path accesses
the audited stack, allocated heap and one zero-valued owned data flag before
the next service. No new imported data variable is enabled.

The initially attempted source audit rejected an incorrect assumption that
MP used SP's data displacement. Deriving and independently checking each
role's original signed load resolved it: SP −13112, MP −14072. The failed
attempt is retained privately and is excluded from accepted evidence.

## Runtime and evidence contract

`--checkpoint startup-inspect` executes the already accepted first reserve,
returns to title code, records the second request and stops **before commit**.
`--checkpoint startup` additionally admits that one exact request and returns
to the audited heap initialization. Header remains the default checkpoint;
`allocation-inspect` and `allocation` preserve the preceding stop behaviors.

The guarded host checks caller, frame, context, aligned mapped read/write
big-endian in/out words, captured values and a two-allocation-call budget.
The original dynamically resolved kernel export must differ from the local
trap. Every other function remains a diagnostic trap. The commit oracle checks
status/output, original allocation extent, committed region/edges, read/write
access, reserve-only inaccessible tail, title-page accounting, fresh zero fill,
neighbouring bytes and unchanged header/module/owned-data bindings before
returning. Host checks do not initialize the title heap.

At the next service the read-only oracle checks the title-written heap markers,
flags, halfwords and eight-node links, exact caller and unchanged frame/global.
The next kernel service is never called. Wrong callers, pointers and values are
rejected before commit; result/heap oracle controls require a valid real-call
baseline. Incomplete evidence follows orderly teardown but omits the footer.
The late control reaches the real heap baseline and is killed at five seconds;
it is not claimed to recover its mapping or threads. Normal probes have a
30-second outer deadline and an eight-second title-exit deadline. Build workers
are capped at two, and heavy runs are serialized.

The new checkpoint parser requires per-process nonces, exact event order/multiplicity, the
actual call and result, complete recovery, and matching loaded kernel hashes.
Missing, stale, reordered, duplicated, late or sanitizer/crash evidence fails.
Input/generation/SDK/source/config/package identities are checked before and
after execution. Retained artifacts are separately reviewed before acceptance.

## Reproduction

Use the private owned input and verified preparation paths for each host; never
place game inputs, generated code, dumps or traces in Git. For example:

```text
python tools/verify_kernel_gate.py --root PRIVATE_CACHE --sdk-report MEMORY_IMPORTS_RECEIPT --sdk-profile memory-imports --owned OWNED_REV1 --metadata PRIVATE_ANALYSIS --generation GENERATION_RECEIPT --expected-generation-sha256 eacf6eed533a3e5a88dae07a68f6080fdd3be9d92bf5e9a8b4104eaf6d1ac52b --expected-allocation-contract-sha256 d7339f9a99a4d357faf1893a266213030807363dcc727604d95c7e87c1f49be7 --expected-startup-contract-sha256 STARTUP_CONTRACT_DIGEST --role sp --checkpoint startup --output-root PRIVATE_LANE_OUTPUT
```

Run separately with `--role mp`, `--checkpoint startup-inspect`, `header` and
`allocation`. `--sanitizers` instruments maintained host code on supported
profiles; the Linux participating-kernel profile uses its separately prepared
sanitized SDK. Public checks are `python tools/check.py --config Release` on
Windows and `python3 tools/check.py --config Release --sanitizers` on Linux.

## Limits and review

This remains a private headless startup probe with graphics/audio/input disabled.
It uses the minimal two-XEX input directory. Prepared full game content is
available separately but has not been loaded by this checkpoint. Original
Campaign, MP, Spec Ops, Survival and split-screen parity remain unverified.
The first-frame epic stays unfinished. No gameplay performance or calendar
delivery estimate follows from this milestone.

The integration reuses the selected SDK; it adds bounded diagnostic validation,
not a replacement allocator or renderer. Probe zero-fill and identity scans
have diagnostic overhead, with no claim about gameplay performance. Windows
kernel sanitizer support remains unavailable; Linux/WSL is the same physical
machine. Generated guest code and retained native dependencies are outside
parts of instrumentation. Review is self-review; no independent reviewer or
second-machine validation is claimed.

## Accepted local evidence — 2026-11-23

The final frozen implementation passes 206 isolated process cases across 22
separately audited runs: 150 continuation, 48 historical first-allocation, four
header-only and four continuation-inspection cases, with 206 unique generated
nonces. The checkpoint protocol validates 202 nonce echoes; the four unchanged
header-only cases retain their nonce in the child environment and receipt.
There are 198 actual allocation-export calls including deliberate post-call
controls. All 14 intentional deadline controls require their valid baseline
and make no recovery claim. Every other case checks mapping release and host
thread-count recovery; pre-launch binding controls never launch a guest thread.
Fourteen deliberately incomplete cases perform orderly teardown but omit the
completion footer and cannot pass as positive evidence.

| Profile | SP/MP continuation | Historical regressions |
| --- | --- | --- |
| Windows native | 15 / 15 | 12 allocation + 1 header + 1 inspection per role |
| Linux native | 15 / 15 | 12 allocation + 1 header + 1 inspection per role |
| Windows host UBSan, trap mode | 15 / 15 | Native regressions above |
| Linux host ASan/UBSan | 15 / 15 | Native regressions above |
| Linux host + participating-kernel ASan/UBSan | 15 / 15 | Native regressions above |

The default continuation suite selects all 15 cases. Native regression commands
use `--checkpoint allocation` (all 12 cases), `--checkpoint header --cases
positive-0` and `--checkpoint startup-inspect --cases positive-0`, for each
role. Host sanitizer commands add `--sanitizers`; the Linux participating-kernel
commands also select their separately verified sanitized preparation receipt.
The full exact argument vectors are retained in each private receipt.
Historical checkpoint reruns here use the selected memory-imports SDK on
native hosts. Separate historical sanitizer/original-XMA matrices from 092
are not rerun or counted as new 093 evidence.

Both full public Release checks pass 338 Python tests plus parser CTest 1/1:
Windows has eight documented platform skips; Linux ASan/UBSan has two.
Windows skips are six unavailable symlink-privilege tests, one POSIX FIFO
contract and the unavailable LLVM assembler/objcopy fixture. Linux skips the
two native Windows junction contracts. The original title source audit uses
its independently verified Linux LLVM reader despite that public Windows skip.
The 25 focused lifecycle tests include 11 new original synthetic startup tests.
Three additional direct CLI controls refuse stale startup/allocation/generation
hashes before creating output or building. These are not title process cases.
Exact-head public CI and merge review are recorded on
[PR143](https://github.com/JaBoyAlex/mw3-recompiled/pull/143).

The initial source-inspection failure described above remains retained. The
two original Windows precall captures and focused Campaign development run
are retained separately and excluded from the final frozen-source totals.
No selected-SDK defect was observed or patched in this task. Historical header
and first-allocation classifier/contract ASTs are unchanged.

An initial separate artifact audit stopped because its compile-source allowlist
omitted the SDK host-allocation adapter and generated GPU-preference exports.
Their pinned SDK file/template hashes were verified before extending the
private audit allowlist; the failed audit is retained. Runtime admission and
checkpoint acceptance rules were unchanged.

Separate artifact review rechecks compiled source ownership, source/config/
generation/metadata/preparation/compiler identities, execution inventory,
binary and actual loaded kernel hashes, logs, nonces, event classification and
the retained original source/LLVM/precall artifacts. Final source bindings:
driver `278d62b0212d5f6d0e659f4bc9647a0ba6f5f5a065eb9e16d6b6c20af49ca799`; startup contract `a22e8e67b903cf6d0cbcc190bdbbb8b602a0f684536b13edc341335bbb9e591f`.

| Profile | Preparation receipt SHA-256 | Loaded kernel SHA-256 |
| --- | --- | --- |
| linux-core | `633ee7dfc40f38147c9590df73bc46220d4b624daa6365e6d446e07feff897a2` | `ef88723255d88a31f092eff0a169782b8bca8611442330e7588058838adfdce6` |
| linux-host | `7e60b272ab13c51d02a585052499a96bf83fc6c7762da43bb7be2f6c31fe8bff` | `828fc85eabd1c07bfa32dadf92ee2a6547a44444fde945a9384b9ae56169139b` |
| linux-native | `7e60b272ab13c51d02a585052499a96bf83fc6c7762da43bb7be2f6c31fe8bff` | `828fc85eabd1c07bfa32dadf92ee2a6547a44444fde945a9384b9ae56169139b` |
| windows-host | `1922f16daff43554a6aef5cdba4b034e9700330267cdfadf72d787eea4a6ab3d` | `aaa93ebbfa3706ae54ac5aaae33931651abf79d4b976299cd2164c48224f3d92` |
| windows-native | `1922f16daff43554a6aef5cdba4b034e9700330267cdfadf72d787eea4a6ab3d` | `aaa93ebbfa3706ae54ac5aaae33931651abf79d4b976299cd2164c48224f3d92` |

| Accepted run | Cases | Private manifest SHA-256 |
| --- | --- | --- |
| linux-core-mp | 15 | `c845925dbec7131bda1bee135fbb2c8a8fb64a861a8c854ea4bce7ce14d06d40` |
| linux-core-sp | 15 | `4c77fcb9f268eef51722b229cb427e6952c84692b89315d312a69091e1ab094d` |
| linux-host-mp | 15 | `5808df656babe47c54b66c7e53aa0e25d12085fd30dd62ad028e761fb440e679` |
| linux-host-sp | 15 | `2b6c1fb181ac4c1c183773fb40de5d751a5c007ccd64458d2e8ad0ce5e1e1d33` |
| linux-native-mp | 15 | `42bb0b71fdad61adb0c6e2eeac126e6a51dacb1fc02370e427df1b1aacdc74e0` |
| linux-native-sp | 15 | `7620373058309f1b486e377ac8bb51fc3b386f050d40bcbe0abbffbd3f25ffc2` |
| windows-host-mp | 15 | `662dff5ddebf3d36404e5eb48cff437c2b1ab26b3bacab60f7f72ccfa54e3a68` |
| windows-host-sp | 15 | `3b93aac4fae424e2d39262db0c7d316185bc1906fb7345363370a6b6d72f785b` |
| windows-native-mp | 15 | `e0b624e9f015a4f3a8d6c3e27e683614c3accdf3c8856fc36313129c85a41bf6` |
| windows-native-sp | 15 | `242770c8c4b1181acf61d959b78be30e9dba7da612879b49a4458c6cd718c6a8` |
| header-linux-native-mp | 1 | `2622b53190ca1b79b1b48e5e9fde94fe55543211baea22f0e49fcce86cb65c04` |
| header-linux-native-sp | 1 | `96c3254f6808dcb7a3207b9b0e5a2984b1040e21dc211d54d993242ec0a94399` |
| header-windows-native-mp | 1 | `a4be1257113e48b367dc6ad4de06dca8bb8650e9db2d65e6a2d038b70b978b98` |
| header-windows-native-sp | 1 | `527be4b428229823da22df34e527b1a862cb21ff92421581d296fc0f890573cb` |
| inspect-linux-native-mp | 1 | `3b6e15c50e46ea3b235ce856c138b237392c892efafe9f33527a84f34108833c` |
| inspect-linux-native-sp | 1 | `e620f22d8e7bf1108f01db313f75ff33c895f5162053adc468c6ca26f2ac14d8` |
| inspect-windows-native-mp | 1 | `aa89310ad46e95efb79eba4d23496cd029ecf9ea4bd129c0afd99591dfa85871` |
| inspect-windows-native-sp | 1 | `e727d80cc761b9ce6b658fcd532ddf48ef9756e4a3dca232bdf20a34d1d7a002` |
| regression-linux-native-mp | 12 | `8da21f5444fbcbf17dcd726650e90a4b99bd784613adab46d913e1fa263c0691` |
| regression-linux-native-sp | 12 | `a99a27fbd5e0f222b3810e17f4ff38f4828ec3df894ff6673a5046a41a7ef60f` |
| regression-windows-native-mp | 12 | `2e03ea61a0bff1f9b16c990f002d27186c83419d1d46498deedfe9c430ef90e0` |
| regression-windows-native-sp | 12 | `4a505903cb7cc0b3b90876432bc6eeccdc7cffb5c3d60e22ad3e4430db7bafb4` |
