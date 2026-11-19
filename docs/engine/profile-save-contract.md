# Original host profile/save contract — MW3-081

`runtime/storage/profile` provides C++20 host persistence with original synthetic
records. It has no SDK, game-byte, translated-code or proprietary-format input.
**MW3 save/load compatibility, guest filesystem services, production sync and
playable boot remain unverified.** Integration requires a separately agreed task.
In particular, this does not repair the SDK link-confinement failures retained
by [MW3-060](profile-storage.md) or complete platform gate MW3-012.

## Ownership and confinement

`Profile::create(writable_base, prepared_content, profile_id)` exclusively creates
a new profile child. An existing directory is never adopted or overwritten.
`open` requires the exact original `.owner` marker bound to that profile ID.
Every open holds an OS writer lock until destruction; another object/process
cannot open that profile concurrently. Transaction tokens are move-only and
bound to an individual open session, including across close/reopen. Both roots
must already exist, be absolute and disjoint by native directory identity,
including ancestor relationships and Windows short-path aliases.

Profile/slot IDs use 1–32 lowercase ASCII letters/digits/underscore/hyphen, with
an initial letter/digit. Case, Unicode, dot components, separators, whitespace,
embedded NUL, Windows ADS syntax and reserved DOS device names are refused;
there is no lossy normalization that can merge identities. Roots reject raw
dot components, NUL, excessive length/depth and ambiguous Windows components.
Windows supports local drive paths; UNC/device namespaces are refused.

Linux walks roots with `openat(O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)`, uses pinned
directory descriptors for leaf operations, and requires user-owned writable
base/profile directories without group/other write permission. Files use
`O_NOFOLLOW|O_NONBLOCK`; regular-file type and single-link count are checked on
the actual handle before IO. Windows pins every directory ancestor with
`FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_BACKUP_SEMANTICS` and no delete sharing,
and rejects reparse/directory/multiple-link file handles. Operations use only
canonical single-component leaf names below those pinned roots. Real hard
links, Linux symbolic links and Windows junctions are tested with private
outside-root canaries. Neither a string-prefix test nor SDK mount policy is
the confinement mechanism.

Prepared content is only pinned/checked for separation; this API exposes no
write/create/remove operation there. All writable records stay in the new
profile child. The `.owner` marker is a cooperative ownership protocol, **not
account authentication**. Caller-controlled local roots are trusted against
external modification by the same user/admin, kernel mounts or other software
ignoring this protocol. Windows ACL ownership is not certified. This is not a
security boundary against a hostile account with permission to modify the
roots. External directory mutation, network filesystems and cloud-sync conflict
resolution are outside the contract. Callers must supply a private local base.

## Bounded immutable records and recovery

The original host envelope is versioned independently of any MW3 format:

| Byte offset | Field |
| --- | --- |
| 0 | Seven ASCII bytes `MW3HSV1` and one NUL |
| 8 | Profile ID, zero-padded to 32 bytes |
| 40 | Slot ID, zero-padded to 32 bytes |
| 72 | Nonzero generation, little-endian uint64 |
| 80 | Payload length, little-endian uint32 |
| 84 | IEEE CRC32 over bytes 0–83 followed by payload, little-endian uint32 |
| 88 | Original caller payload, at most 1 MiB; exact file length required |

CRC32 detects accidental corruption; it is not cryptographic authentication or
an adversarial checksum. Decode checks size before allocation, all header
bindings, exact length and checksum. Python independently validates a produced
record using `struct`/`zlib`; cross-profile/slot copies with a valid checksum
still fail binding checks. Readers inspect the newest committed generation;
older history is retained and checked if explicitly needed for recovery.

Each name is `slot.<16-lowercase-hex-generation>.pending|record|rejected`.
The directory budget is 256 entries including `.owner` and `.lock`, therefore
at most 254 history/artifact entries across all slots. There is no implicit
garbage collection. New writes refuse a full budget or uint64 exhaustion;
retained artifacts count toward the limit. Unknown/unsafe entries refuse
operation without deleting them. Payload buffers are bounded by 1 MiB + 88
bytes; callers retain their own payload memory. This is a single-thread-owner
API, with no unagreed runtime/threading seam.

1. **Stage:** refuse a slot needing recovery; choose the next generation across
   committed, pending and rejected names; exclusively create `.pending`, write
   the envelope, flush and close it. A failed/partial write remains diagnostic.
2. **Commit:** revalidate staged bytes; publish `.pending` to `.record` without
   replacing any target. Prior generations are never written or deleted.
3. **Rollback:** rename the pending file to `.rejected`, retaining its bytes.
   A consumed/moved/wrong-session token cannot act again.
4. **Load:** a pending file or invalid newest record returns
   `recovery_required` with no payload. It never silently loads an older save.
5. **Recover:** explicit caller consent quarantines pending files (never
   promotes them), then invalid newest records, to `.rejected`. It returns the
   last valid committed generation, or `missing` if none exists. Diagnostics
   identify retained artifacts. A quarantine-name collision fails without
   replacing either artifact; partial recovery can be retried after inspection.

Linux publishes with `renameat2(RENAME_NOREPLACE)` and fsyncs the containing
directory; an unsupported no-replace rename is an error, with no unsafe
overwrite fallback. Windows uses same-volume `MoveFileExW` with
`MOVEFILE_WRITE_THROUGH`, no replace/copy flags. Staged files use
`FlushFileBuffers`. Windows directory metadata/power-cut durability is **not
promised**. A publication followed by failed directory fsync is `uncertain`:
the token is consumed and the caller must inspect state, not assume rollback.
Creation interrupted before the ownership marker can leave an unowned partial
directory; `open` refuses it and no automatic cleanup/adoption occurs.

Process exits are tested after staging and after publication. These establish
recovery at those boundaries, not atomicity under every power-cut/storage
controller scenario. Disk-full/power-loss injection, network/cloud storage,
hostile concurrent root mutation and compatibility with real saves are NOT RUN.

## Reproduce

From an isolated checkout with Python 3.11+, CMake 3.25+ and a C++20 compiler:

```text
python -m unittest discover -s tests/host_platform/storage -p test_*.py -v
cmake -S tests/host_platform/storage -B <private-build> -DCMAKE_BUILD_TYPE=Release
cmake --build <private-build> --config Release --parallel 2
ctest --test-dir <private-build> -C Release -V
python tools/check.py --config Release
python tools/check.py --config Release --sanitizers
```

Use `-DMW3_PROFILE_SANITIZERS=ON` for the standalone native project. Discovery
enables Linux ASan/UBSan by default. On Windows, set
`MW3_PROFILE_TEST_SANITIZERS=ON` and add the installed MSVC ASan runtime directory
to PATH for a separate instrumented run. Public discovery defaults to native
Windows so an absent optional ASan DLL does not suppress all native tests.
Root `check.py --sanitizers` instruments the root parser; this separate option
controls storage's standalone project. No root CMake/CI/shared-test edit is
needed: existing Python discovery picks up this owned test package.

Eleven CTest groups cover normal/empty/max records, invalid names, disjoint roots,
exclusive ownership, corruption/truncation/oversize/invalid length/empty/staged
damage, rollback and token lifetime, valid-checksum profile/slot crossing,
no-replace publication/quarantine conflicts, capacity/overflow, resources and
actual links. Python additionally tests independent CRC, abrupt `_Exit` before
and after publication, real second-process writer exclusion/release, a wrong
payload detector (exit 1, no PASS), invalid invocations (exit 2) and three real
Windows junction placements (root, profile and record entry).

Resource cases compare native handle/FD counts before/after 128 repeated open,
load and failed-open sequences. Linux also lowers only its own process
`RLIMIT_FSIZE` to force a real 90-of-91-byte partial write, restores the limit,
and verifies recovery retains the partial bytes and previous valid payload.
Windows exercises actual sharing/no-replace failures; no disk is filled.
Fixtures use only newly created synthetic trees/canaries. Native CTest failures
retain their private fixture paths; Python successful temporary trees are removed.

## Evidence and performance decision

Local validation used one physical host: Intel i5-11400, native Windows 11 build
26300/NTFS (Python 3.12.14, CMake 3.31.6, MSVC 19.44.35229), and WSL Ubuntu 24.04
on ext4 (Python 3.12.3, CMake 3.28.3, GCC 13.3). This is not two-machine evidence.
Native and ASan Windows suites pass all six Python tests, including 11 CTest
groups. Linux native and ASan/UBSan pass the native groups and process/CRC tests;
the Windows-junction Python test is an explicit Linux skip. Windows symbolic
links require unavailable privilege and are explicitly skipped inside the link
case; hard links and actual junctions pass. Linux real symbolic/hard links pass.
The initial Windows junction run correctly refused access but reported generic
IO; adding directory-aware handle opening fixed the classification, and the
suite was rerun. No redirect was accepted and no canary was changed.

Final root checks pass **154 Python tests** on each OS (Windows eight explicit
skips; Linux two Windows-only skips), plus the root parser CTest 1/1. Linux root
Release uses `--sanitizers`; storage and input packages independently build
their sanitizer-enabled standalone projects. The separate final Windows ASan
storage run passes six Python tests and all 11 native groups. Builds use two
workers and task-private output/profile trees. No shared SDK/preparation,
startup/allocation/input file or process was modified. Completion evidence is
limited to this host persistence task; review is still required before lead
integration.

Three independent Release processes per scenario measured complete
stage+commit+load of a verified 64 KiB synthetic payload. `profile-tests benchmark
<private-parent>` performs three warmup generations then 24 measured operations;
`benchmark-history` preloads 200 generations then measures 24. Every sample
includes file flushing, no-replace rename, supported directory sync, integrity
checks and byte-equality load. Histories grow during each run. The p95 below is
the nearest-rank 23rd ordered sample of 24; no frame/GPU/input-latency claim.

| Local filesystem / initial generations | Run medians (ms) | Run p95 (ms) | Maximum (ms) |
| --- | --- | --- | --- |
| Windows NTFS / 3 | 21.461, 22.660, 22.026 | 24.996, 29.816, 26.045 | 31.450 |
| Windows NTFS / 200 | 53.951, 67.213, 61.725 | 61.882, 89.656, 72.491 | 91.390 |
| WSL ext4 / 3 | 11.069, 11.003, 10.546 | 13.306, 13.350, 13.057 | 15.574 |
| WSL ext4 / 200 | 11.841, 11.753, 11.719 | 15.100, 13.225, 13.772 | 15.175 |

These are synthetic local costs, with ordinary host scheduling/cache variance,
not an OS/framework ranking, gameplay speedup or deployment latency budget.
The host was not isolated from the other contributor's background work; no
controlled hardware comparison is inferred. Measurements used temporary local
roots, no game content or GPU work. Raw observations/binaries/logs remain private.

Correctness/licensing precede the project's weighted choice criteria. The
demonstrated SDK mount escape excludes simply using that mount as confinement.
Immutable no-replace generations preserve prior bytes at the cost of bounded
history scans and disk use. For performance (30%), the measured Windows history
cost requires a future caller to schedule this work outside frame-critical
execution; no asynchronous runtime integration is added here. Stability (25%)
is supported by failure/recovery/ownership checks, without a power-loss claim.
Maintainability (20%) favors one original bounded format and two small native
backends. Integration (15%) remains deliberately unmeasured until a separate
service/format task; hardware compatibility (10%) has Windows/WSL evidence on
this host only. Missing comparative scores remain unknown. Future retention,
async scheduling, guest-service admission and original-save migration require
separate scoped work and real-title evidence. No unbenchmarked alternative is
called fastest. Self-review only; no independent review is represented.
