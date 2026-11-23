# Isolated allocation-import safety profile

MW3-091 implements `memory-imports-v1` on selected ReXGlue
`ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d`, composed with the exact
reviewed XMA/stop/memory parent. The scoped repair matrix below passes.
This opt-in profile admits no title service and executes no MW3 code.

## Repair and evidence boundary

[MW3-046](startup-memory.md) retains actual-kernel baseline failures for
allocation/free in/out pointers, aliased free output words and signed-minimum
size negation. Its original callbacks use a real SDK-created guest thread,
export names/ordinals, manual big-endian byte access, canaries, checked guest
memory, allocation/handle accounting and orderly unload. These are selected
fork safety contracts, not a retail-console differential oracle.

The small BSD-noticed patch changes only
`src/kernel/xboxkrnl/xboxkrnl_memory.cpp`. Both entry points validate both
in/out addresses before a trace read or typed dereference: nonzero, aligned
to four bytes, a complete nonwrapping four-byte range, and checked readable
and writable mappings. Distinct aligned words exclude partial overlap; equal
guest addresses and equal physical offsets through distinct physical windows
are rejected. Distinct valid physical words remain supported. A physical view
can alias committed backing without its own allocation record: the repair
requires an unallocated requested view, readable/writable committed physical
backing and an independently queried readable/writable host mapping. It does
not override a requested view's explicit reservation or protection. The global
mapped-pointer thunk and other services are untouched.

Negative sizes are converted to magnitude with unsigned subtraction. This
preserves the ordinary negative-size policy and defines the `0x80000000`
case without negating signed minimum. The existing heap/rounding/protection,
zeroing, endian output and release semantics remain the parent policies.
Invalid pointer pairs return `X_STATUS_INVALID_PARAMETER` without mutation;
this rejection choice does not certify a retail Xbox status code.

The range checks do not add a transaction against concurrent protection,
release or unload by another thread. General race freedom, self-unmapping
output buffers and other memory-service ABIs are not established by this
bounded single-thread callback suite. Unknown title imports remain diagnostic
stops. Full MW3-046 consumer acceptance follows separately after this repair.

## Private preparation and verification

```sh
python tools/prepare_runtime_memory_imports.py --root "$SDK_CACHE" --baseline-report "$VERIFIED_XMA_REPORT" --fetch
python tools/prepare_runtime_memory_imports.py --root "$SDK_CACHE" --baseline-report "$VERIFIED_XMA_CORE_REPORT" --core-sanitizers
python tests/host_platform/memory_imports_profile/exercise.py --root "$SDK_CACHE" --sdk-report "$REPAIR_REPORT" --output-root "$PRIVATE_RUNS"
```

The first command prepares a fresh native profile on Windows or Linux. The
second is Linux participating-kernel ASan/UBSan with a matching parent;
Windows core instrumentation is refused. Exercise native packages directly,
add `--sanitizers` for host instrumentation, and use that flag with the Linux
core report to cover the participating kernel as well. Each build is bounded
to two workers. A separate source worktree, build root, writer lock and UUID
output/package preserve existing parent sources, SDKs and build outputs.

Preparation verifies the parent before making a new attempt. It derives the
full reviewed patch composition in its own source worktree and checks the
source tree, pinned recursive submodules, critical mapped-pointer/guest-memory/
heap contracts and upstream license. It hashes the driver/helpers, lock/patch,
compiler, source, compile commands and build/configure logs. Only the kernel
library replaces a file in a copied verified parent package; every unaffected
file must retain its exact hash/size, and the replacement must differ.
Verification rechecks the current compiler, all these records and the complete
package rather than trusting a PASS stamp. Redirected source/build/output
roots are refused, and invalid parents fail before creating an attempt.

The exercise driver reuses MW3-046's original callback source and protocol
verifier, binds both their identities and checks them again after execution.
It hashes the actual loaded kernel in every owned process. It does not embed
kernel object libraries, replace exports or manufacture successful imports.
Synthetic receipt/configuration mutation tests are separate from actual
kernel execution. Each private manifest records exact per-attempt commands,
source/compiler/configuration/package/library/binary/log identities and cases.
The exercise refuses outputs overlapping maintained source/configuration,
the selected receipt/package, source or build caches, or any parent preparation
directory before creating an attempt. A disjoint output lane may share the
private cache's top-level directory.

## Retained development findings

The first derivative required the requested physical view to have its own
checked allocation record. Its actual Linux native suite rejected the valid
`physical-alias` case. That failed preparation, source/configuration snapshot
and all 41 process results remain private; the final correction uses the
physical-backing and host-mapping checks described above. Original MW3-046
baseline failures also remain retained. Neither set is counted as repaired
acceptance.

An interrupted rebuild produced no accepted preparation receipt and was
superseded by a fresh attempt. The first Linux public-check invocation stopped
at Git discovery because the Windows-created worktree metadata used an
absolute Windows path. Making that private Git link relative allowed both
native Windows and WSL to inspect the same maintained source; no repository
code or check was changed to hide the failure.

The paired audit initially required the entire baseline source snapshot to be
byte-identical. Two uncompiled Python unit-test files changed only CRLF/LF
line endings after the baseline was merged; the audit now explicitly checks
that difference. The executed C++ callback, CMake input and protocol parser
remain byte-identical to the retained baseline. Both complete source snapshots
and their differing raw hashes are retained.

## Verified matrix — 2026-11-22

All **615 actual-kernel processes** pass the strict protocol: 570 ordinary
successes and 45 correctly rejected wrong-result/incomplete/deadline controls.
Each of five profiles runs all 41 cases three times, using a separate binary,
output directory and per-process nonce. All 615 nonces are distinct. The
`repeat` case additionally executes twelve alternating allocation/lifecycle
scenarios per process. The retained matched 205-process baseline has 83 real
failures, 107 ordinary passes and 15 rejected controls; it is not relabeled
as successful negative testing.

| Profile | Ordinary passes | Rejected controls | Repair failures | Retained baseline failures |
| --- | ---: | ---: | ---: | ---: |
| Windows native | 114 | 9 | 0 | 17 |
| Windows host UBSan traps | 114 | 9 | 0 | 17 |
| Linux native | 114 | 9 | 0 | 15 |
| Linux host ASan/UBSan | 114 | 9 | 0 | 15 |
| Linux participating kernel ASan/UBSan | 114 | 9 | 0 | 19 |

The paired audit checks the exact original XMA SDK as each repair's parent,
matching Clang 20.1.2 compiler hashes, host instrumentation, byte-identical
original C++/CMake inputs and the original protocol parser. It does not claim
an identical probe binary after relinking against another kernel. C++ input
SHA-256 is `73e7d4be8445eca261fea1369ee53b1cac0d9b82d7d92bd26a20d120b6abd7ef`;
the new exercise driver is
`707d6dec648b8536a1f4ba61b6c441b26843e51daa726d958d75af327ff5870e`.
The locked repair patch SHA-256 is
`3093f68104f74978dc3efb9f94d16304d0b1474ad95b97983be4e69b95adc531`,
and repaired memory-source SHA-256 is
`983706d57085a822dc4b27d821ced18af74b63132a8b51d7f67ea19bfecc7a12`.

Preparation receipts and actual loaded kernel contents (SHA-256):

| Preparation | Receipt | Kernel |
| --- | --- | --- |
| Windows native | `1922f16daff43554a6aef5cdba4b034e9700330267cdfadf72d787eea4a6ab3d` | `aaa93ebbfa3706ae54ac5aaae33931651abf79d4b976299cd2164c48224f3d92` |
| Linux native | `7e60b272ab13c51d02a585052499a96bf83fc6c7762da43bb7be2f6c31fe8bff` | `828fc85eabd1c07bfa32dadf92ee2a6547a44444fde945a9384b9ae56169139b` |
| Linux participating kernel ASan/UBSan | `633ee7dfc40f38147c9590df73bc46220d4b624daa6365e6d446e07feff897a2` | `ef88723255d88a31f092eff0a169782b8bca8611442330e7588058838adfdce6` |

Each process's actual loaded kernel path/content, probe binary, compile-command
record and full log were rehashed in a second artifact audit. That audit also
rechecks the current preparation, source/compiler/package identities, copied
callback sources and protocol parser. Complete package inventories prove that
only the declared kernel changed; original parent source/package verification
passes after preparation, mutation controls and execution. Existing build roots
are not build destinations. Linux XAM and external/system libraries remain
native, vptr instrumentation is disabled, and no generated guest code is
instrumented. Windows participating-kernel sanitizers are **NOT RUN**: this
profile supports host UBSan traps with native runtime libraries only. Linux
is Ubuntu 24.04 under WSL on the same machine, not independent hardware.

Per-run manifest SHA-256 records bind the complete binary, SDK, compiler,
configuration and log identities; private artifacts are retained by run ID:

| Profile / repetition | Private run ID | Manifest SHA-256 |
| --- | --- | --- |
| Windows native / 1 | `eb0eb99161464a5db57c70c655be2d97` | `ba94e558198d5f3d6340b8ef25f8520f71502e4cac873747a8228eb3c73e3386` |
| Windows native / 2 | `d893ef49cfdd4bd89d86262953c3b300` | `1bbab4ce6862c78dafb1fb53f2488176ae35b86e29dcaab7328b3c803e5ed010` |
| Windows native / 3 | `dccb3e12399641f9b495a57b28489836` | `0e699b3a014a8d8a4546283b5fb009605db6c7aefba3c6e665aaaec548e6f867` |
| Windows host UBSan traps / 1 | `486838f02aae4f15863c4b43b98f5de5` | `111db89ff1f7310e6e74c463b1a94949d04f0bc81012a9ecb7a508df60dc0f49` |
| Windows host UBSan traps / 2 | `ebfbf3f0ef3848fb9be400d440062172` | `3562c94eb2360c2ecc9e50c04bd843f40b2431dad327e885ae394cdd3f5df2c0` |
| Windows host UBSan traps / 3 | `5bebfa7fbb654cd88737c81a111dc31f` | `b896710b1155d8b8d7358b588f4004a99bc7f44c5230cac81af506e7fa790298` |
| Linux native / 1 | `e01bd3cb4f2045b3a81f438b421320b7` | `fbfc40f41fe30598ecc50afe8b8bdb65f9800cdd2702c4f1a33a2c308153d310` |
| Linux native / 2 | `093ad973bcea4a369608cdde22fc5be6` | `dab0778991cd07456cb5790dbefc3f1e6148e17c36bff160f51b7f90c13ab396` |
| Linux native / 3 | `626e17ef013247559bf2c0870b723650` | `6a2ac1c9bb7020f1c4086c8b9d9230d5fa34408434dacdc03cc04c39570fd549` |
| Linux host ASan/UBSan / 1 | `3a807afba7294b689b9ac4f8933da214` | `27b25a3f67e7c0240a410e15f891f38b425045c5635c6ba4efacbeb15be6c214` |
| Linux host ASan/UBSan / 2 | `670e956e6af345348c222a05fbda042a` | `49dc581bc8b85de2598a1ab493522c69c78a19291270bc7e03faa492d5e716eb` |
| Linux host ASan/UBSan / 3 | `6285a936ffd44a1aaa06bcce7ef5cd16` | `6264d7df0cdf6af852aef870c1a062119646d9c5c7fdd99a02f9b596b65a7174` |
| Linux participating kernel ASan/UBSan / 1 | `1cca446a59a34c7c997d0301aa241c89` | `efe0f52a936ac9f18601d6c54cbecb0162b1355f213af381f40cbaf83a4a0e83` |
| Linux participating kernel ASan/UBSan / 2 | `f77d2e5b75ed406e8e2d185cacda9bd6` | `61c8e175a513a7c82ff91c10fe59c6db4ff108fa5c66e2b9e79d342f010a927c` |
| Linux participating kernel ASan/UBSan / 3 | `39890d143500401bbc15074668eaa4b3` | `4edcac3f53570a1eecd5eac2d005dac9e7ba12369f33027580160624f9adba8a` |

All 36 actual preparation mutation controls pass (12 for each of three
packages): changed receipt status/mode/source/compiler/parent/package, derived
source, kernel, unaffected header, compile commands, build log and patch are
rejected. Every mutated child file is restored byte-for-byte and verified;
original parent receipt/source/package identities remain unchanged. Eight
public synthetic preparation/output-isolation tests also pass. These synthetic
checks are not counted among the 615 actual-kernel processes.

Exact public validation commands:

```sh
python -m unittest discover -s tests/host_platform/memory_imports_profile -v
python tools/check.py --config Release
CXX=clang++-18 python3 tools/check.py --config Release --sanitizers
python tools/project.py validate
python tools/check_repository.py
git diff --check
```

Windows Release: 313 Python tests, eight explicit platform/LLVM/symlink skips,
and parser CTest 1/1 PASS (MSVC 19.44). Linux Release with ASan/UBSan: 313 tests,
two Windows-junction skips, and parser CTest 1/1 PASS (Clang 18.1.3). Windows
uses bundled Python 3.12.14 and the installed Visual Studio CMake/CTest tools;
Linux uses Python 3.12.3. The 66-task DAG and heuristic artifact/diff checks
pass. An initial Linux check stopped before tests on a Windows-absolute private
worktree Git link; a relative link fixes that host-path issue and the failed
log is retained. No shared source or product change was needed.

Full MW3-046 adoption remains separate: explicitly select and verify this
profile there before marking its allocation-import ABI consumer accepted.
No other task is marked complete by MW3-091.

## Provenance and limits

The patch retains Xenia/ReXGlue ancestry, BSD notices and full upstream
[license](../../config/toolchains/rexglue-memory-imports/LICENSE.ReXGlue).
The public preparation and test tooling is original GPL-3.0-only code. No SDK,
game bytes, generated guest code, private logs or binaries are distributed.
The public source/local-build policy grants no game-linked binary release.
No MW3 startup advance, rendered frame, gameplay, retail ABI certification or
performance claim follows from this profile. Pointer validation adds checks
whose MW3 cost is unmeasured. Self-review only; no independent review claimed.
