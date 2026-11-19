# Selected-SDK profile/content mount investigation — MW3-060

This is an original game-free investigation of the actual selected filesystem
module. It establishes tested behavior and a **host-link confinement gap**;
it does not implement profile/save services or complete platform task 012.
No guest instructions, owned content, existing saves or production services
are accessed by this diagnostic lane.

## Contract and actual boundary

Each fixture creates two synthetic profiles, shared content and an outside-root
canary under one private per-attempt tree. Separate filesystem instances mount
their own host directory at the same guest `\Profile` path and the content
directory read-only at `\Content`. The canary is outside the mounted profile
but remains inside the attempt's private tree. Link probes cannot target any
real save or game file. Attempts and their changed canaries remain retained.

The C++ harness gets `IFileSystemFactory` from the running SDK app. It does not
embed an implementation object or replace a filesystem service with a stub.
It resolves a factory virtual-method address to the loaded filesystem module;
the Python driver verifies that module's actual bytes against the selected
package. All filesystem objects and handles are destroyed before app shutdown,
and SDK host-thread counts must recover. A watchdog/nonzero process or missing
completion record cannot pass an ordinary case.

| Case | Required observation |
| --- | --- |
| `profiles` | Same guest filename returns different profile payloads; a write persists after remount and leaves the other profile unchanged. |
| `read-only` | Read-only content cannot be written, truncated, created, removed or renamed into a writable profile; canaries remain unchanged. |
| `bounds` | Traversal beyond the profile mount, misleading mount prefixes, invalid host-name characters and embedded NUL are refused. |
| `relative` | A directory-relative create/read preserves its payload and cannot read the private outside-root canary. |
| `rename-remove` | Same-mount closed-file rename/read/remove works; mount-root deletion and a move to read-only content are refused. |
| `file-link` | A host file symlink cannot expose the outside-root canary. |
| `directory-link` | A host directory symlink cannot expose or modify that canary. |
| `directory-junction` | The corresponding Windows directory-reparse test, using a fresh bounded mount-point buffer and private paths. |

The SDK's documented read-only-open policy can downgrade requested write access
to a read-only handle. A successful open is therefore not itself a failure;
actual writes, truncation and mutating operations must be refused. Node size
metadata is cached: the fixture explicitly calls `Refresh()` before observing
a newly written file. No atomic save-commit, crash durability, save-format
validation, corrupt-save rollback or console profile semantics are inferred.

## Observed failure and source corroboration

Native Linux accepts both the file and directory symlinks. The file probe reads
the canary; the directory probe reads it and changes its first byte. Native
Windows accepts a directory junction with the same read/write effect. These
are actual SDK observations, not mocked filesystems. The ordinary path-traversal
controls pass; lexical path checks do not establish physical confinement.

The emitted records retain `opened`, `read_outside`, `wrote_outside` and
`changed` separately. A crossed boundary reports
`host-link-crossed-profile-root`, exits 42 and remains **FAIL**, even though
shutdown and resource accounting complete normally. A canary change affects
only the retained synthetic tree. No existing directory or link is reused.

Source inspection at the locked ReXGlue revision
`ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d` corroborates the tested path:
[HostProvider](https://github.com/rexglue/rexglue-sdk/blob/ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d/src/filesystem/host_provider.cpp)
builds host-backed nodes and opens their host paths. The
[public filesystem contract](https://github.com/rexglue/rexglue-sdk/blob/ebac1cf0d04bab0042a5dd6148b34ab3953e9c0d/include/rex/filesystem/file_system.h)
describes mount, access and rename behavior; it is not a guarantee that the host
provider is an adversarial sandbox. This finding does not establish every link
race or every filesystem API's behavior. Windows fixture construction follows
Microsoft's [mount-point buffer layout](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_reparse_data_buffer)
and [FSCTL_SET_REPARSE_POINT](https://learn.microsoft.com/en-us/windows/desktop/api/winioctl/ni-winioctl-fsctl_set_reparse_point);
no shell command or pre-existing reparse point is used.

## Identity, isolation and commands

Only native SDK receipts already approved by
[`config/toolchains/rexglue-xma/validation.json`](../../config/toolchains/rexglue-xma/validation.json)
are accepted. The entire selected receipt must match an approved SHA-256, its
profile/preparer/lock must match, and all package files are rehashed before and
after execution. The harness compiler must match the receipt's compiler.
Changed libraries/headers, a modified receipt, validation-only core profiles
and a differently loaded filesystem module are refused. This is a read-only
package verification path; it neither derives nor repairs shared source trees.

Each attempt retains source/driver copies, compiler and tool identities, compile
commands, the executed binary, loaded-library hashes, exact process commands,
raw logs and a hash-indexed artifact manifest. Intentional fixture links are
recorded without walking through redirected directories; a link leaving the
private attempt is rejected by artifact collection. Receipt identity binds
the exact source/configuration provenance of the approved package. No SDK,
translated code, private logs or binary artifacts are committed.

```text
python tools/test_profile_storage.py --root PRIVATE_RUNTIME_CACHE --sdk-report APPROVED_NATIVE_XMA_RECEIPT --output-root PRIVATE_STORAGE_OUTPUT
python tools/test_profile_storage.py --root PRIVATE_RUNTIME_CACHE --sdk-report APPROVED_NATIVE_XMA_RECEIPT --output-root PRIVATE_STORAGE_OUTPUT --sanitizers
python -m unittest discover -s tests/profile_storage -v
python tools/check.py --config Release
python3 tools/check.py --config Release --sanitizers
```

The SDK-facing standalone target needs the selected SDK's C++23/Clang 20
toolchain. Maintained public game-free targets remain C++20. Builds use two
workers and profiles run sequentially with private config/temp/app/profile
roots. The driver acquires no tools or game files and changes no shared SDK,
preparer, storage runtime interface, controller model or allocation import.

## Validation and limits

The 2026-11-19 matrix retains these process outcomes. PASS includes two
expected-result detectors per profile; FAIL is an actual link-isolation
counterexample, not a passing negative test. Every suite exits **1**.

| Profile | PASS | FAIL | SKIP | Actual gap / unavailable case |
| --- | --- | --- | --- | --- |
| Windows native | 19 | 3 | 6 | Three junction crossings; file/directory symlink privilege unavailable |
| Windows host UBSan traps | 19 | 3 | 6 | Same junction crossings and explicit symlink skips |
| Linux/WSL native | 19 | 6 | 3 | Three file and three directory symlink crossings; Windows junction API unavailable |
| Linux/WSL host ASan/UBSan | 19 | 6 | 3 | Same symlink crossings and explicit junction skips |

That is 112 processes: **76 PASS / 18 retained FAIL / 18 SKIP**. The ordinary
five-contract sequences pass in both combined orders as well as three isolated
processes per case. All eight wrong-result/incomplete-process detectors behave
as expected. A separate artifact audit rehashes every retained file, binary and
log, checks every recorded loaded-module identity, and confirms that other
profile and read-only content payloads remain intact. No sanitizer diagnostic
appears in these final processes; the library coverage limit below still applies.

Private receipt IDs and SHA-256 values (manifests/logs/binaries stay outside Git):

| Profile / receipt ID | Manifest SHA-256 | Executed binary SHA-256 |
| --- | --- | --- |
| Windows native `2dc3f1b891f848809270534e2e1d58ad` | `dd02db3d456e888ea9d00a00e7e13204087b691b448534d29ebfdfd364b7af27` | `97530701cd27a7e7a3e09149d960734943c1f4829a0fc416ec840677a69bb59c` |
| Windows UBSan `5227562e4c224dd4b47f1c9d35cafe23` | `2212291c82799db3698d85bb8dcaf824707ab886f66e2b3961c132704bf11c35` | `1c064741609193fbeade91024aa668098b7abf6de11660883108c2256782572f` |
| Linux native `e40494337a834d4f87bd7d823c1869cf` | `3d69d26ada8aad110defdf964f4d3cfaface997ac53f572a7e3ccc91818be350` | `c1a3fb3995bd513b4d4764f988e534bfd46b79fc96ac42b54e2cd59d9e1a6d48` |
| Linux ASan/UBSan `77c47457602b4d9d8defdcb9e88b34b7` | `32a5673b5dd9d28f60e383970f06c924e246ed12f25b903ff39eafae2f0dd0df` | `2a7bebaa5272ae938ad7e8e663bf38daac0e7830da8760aaea1178401f75769e` |

Both hosts use Clang 20.1.2 and the native XMA-v1 SDK from the existing approved
receipts. The actual filesystem module hash is
`ff0328e944f15765177b4eea63cf034e61bb9b1110208aa1f3dd7f82f3ee3bb9`
on Windows and
`6f5decc4c0ce24e1ca57fb2e04a3d25d3151bf2008febd1f9d4e09c2e2ef0a87`
on Linux. All four attempts preserve the same maintained source/driver bytes:
`contracts.cpp` SHA-256
`4bdb439ca06a4225d0ab13d7c9df327e89aad5127defc2a202b45b4870526f80`,
driver SHA-256
`f669ebf509f9a0da21bd31bf530df84fbc3ea36c9ee6f6481f7fea806534ef90`.
This is one machine with native Windows and WSL, not independent hardware.

All host-sanitizer runs use native approved SDK libraries:
**the filesystem library itself is uninstrumented**. Windows uses supported
host UBSan traps; Linux uses host ASan/UBSan with leak detection enabled.
This cannot establish absence of bugs inside uninstrumented libraries or
freedom from TOCTOU races. Unsupported host link capabilities remain explicit
SKIP results and do not count as passing isolation checks.

Every ordinary case runs in three independent processes, followed by combined
forward/reverse orders of the five ordinary non-link contracts. An exact wrong
profile expectation and an intentionally incomplete process exercise result
rejection. Sanitizer errors, unexpected failures, stale/tampered artifacts,
duplicate/missing cases, nonzero/late processes and changed thread accounting
cannot be relabelled successful semantic tests.

The recorded microseconds cover fixture creation, mounting and the selected
operations. Host filesystem caches are not flushed. These small synthetic
samples are diagnostic cost observations, not comparable game load/save
benchmarks, a storage-policy speedup or hardware recommendations.

For the `profiles` case, the three isolated fixture-plus-operation samples
have medians of 12,946 microseconds (Windows native), 9,793 (Windows UBSan),
4,439 (Linux native) and 6,676 (Linux host ASan/UBSan). The raw samples and
min/max remain in receipts. Cache state and host environment differ; these
numbers do not rank operating systems, sanitizer overhead or storage designs.
Approved-package validation in these attempts takes approximately 0.16-1.77
seconds; no matched timing exists for the earlier source-checkout verifier.

Development attempts remain retained separately. Linux
`a5bfc9c6d675480e9f03e70d8e14e40e` used stale node-size metadata for two newly
written files and compared a source tree containing Python cache files with a
cache-free source copy. Its final ERROR and relative/rename mismatches are
fixture/accounting defects, not SDK defects. After correction,
`3832aea3978e4c9285fbee2bc3785929` passes those contracts while retaining the
two symlink failures; it predates the added Windows-junction case. Windows
`f9159063e9e8460e82e69a8c636f0b59` was stopped during pre-test preparation
while the verifier was revised and is not acceptance evidence. No earlier
attempt is silently relabelled as a final passing suite.

The seven game-free Python guard tests pass on both hosts; Windows explicitly
skips the real-symlink artifact-collection test because of missing privilege.
Root Windows Release checks pass 145 Python tests with eight explicit
tool/platform/link-privilege skips and CTest 1/1. Root Linux Release ASan/UBSan
checks pass 145 Python tests with one Windows-only skip and CTest 1/1.
These public checks do not run the private SDK matrix automatically. Self-review
is recorded; no independent reviewer or hardware/console validation is claimed.

## Required handoff

Before relying on an SDK host-directory mount as a profile boundary, the lead
must agree a separate host-link/reparse confinement scope and regression policy.
It must cover file/directory links, Windows reparse behavior, existing and
new path components, create/open/rename/remove/relative operations and races
where supported. Preserve these failing baseline controls and require actual
loaded-library identities after any repair. A lexical prefix check or a passing
ordinary profile case does not resolve the demonstrated host-link crossing.

This task changes no SDK code and admits no guest save import. Task 012 still
needs integration, controller/audio evidence, corruption/rollback behavior and
the appropriate real-title/console checks. Do not mark secure saves, gameplay,
performance or release acceptance complete from this investigation.
