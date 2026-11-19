# Complete private disc content — MW3-045

`tools/prepare_content.py` prepares the complete supported owned disc content
into a new private directory. It does not decrypt executables, acquire game
files, modify the original ISO, enable guest services or execute the game.
The existing `Disc` reader and supported-build manifest are unchanged.

## Run and layout

Use Python 3.11+ on native Windows or Linux, an unchanged owner-provided ISO,
and a **new** output directory whose parent already exists. The CLI accepts
only the versioned `config/titles/mw3-xbox360-rev1.json` identity; there is no
custom-manifest or force/overwrite switch.

```sh
python tools/prepare_content.py "$OWNED_ISO" "$PRIVATE_PREPARATION"
```

PowerShell uses the same two arguments with its own variable syntax. Paths
may contain spaces. On Windows use an ordinary local drive path; device/UNC
namespaces and redirected ancestors are refused. Keep output outside Git, or
under an ignored `.local/` directory. Do not select the source ISO/install or
an existing profile/output as the destination. Ancestors are checked rather
than implicitly created or resolved through links.

The result contains:

| Path | Meaning |
| --- | --- |
| `content/` | Fresh copies of every file and directory in the verified XDVDFS inventory, with original names and exact bytes |
| `attempt.json` | Initial identity/configuration record; its `complete: false` remains a historical start record |
| `manifest.json` | Final complete manifest, published only after all checks; this is the completion record |
| `failure.json` | Diagnostic on a caught failure, if writing it is possible; a killed process may leave only the initial record |

A missing, partial or invalid final manifest is an incomplete attempt. Every
existing destination is refused, including a failed attempt. Pick a new name
after inspecting the failure; no automatic cleanup, retry, resume or partial
reuse occurs. A write/flush failure leaves its evidence in place. The final
manifest is not a promise of power-failure durability or protection against
later tampering; consumers must verify the recorded hashes when reusing data.

Treat `content/` as immutable input. Put writable profiles, saves, caches and
runtime outputs in separately owned roots. The preparation tool creates no
profile and never writes into a supplied source/install. It does not wire the
new directory into the active runtime lane or expand its import allowlist.

## Guards and provenance

Before creating an output, the tool verifies ISO size/SHA-256, inventories
through the bounded `Disc` reader, and verifies both exact root XEX identities
against the manifest, including declared execution metadata. Wrong/mixed,
modified, missing or differently cased executable identities fail. It validates
all relative names, parent relationships, extents and budgets first.

Names are not repaired or renamed. The common Windows/POSIX policy rejects
traversal, separators/streams/device syntax, reserved Windows names (including
superscript device aliases), trailing dots/spaces, control characters and
NFKC/casefold collisions. Tildes in disc entries are conservatively rejected as
unverified DOS short aliases. Operator paths may use existing short aliases
(for example a Windows runner's `RUNNER~1` temp parent); they still use the same
handle-relative opens, reparse checks and exclusive destination creation.
The owned supported image passes this policy; this does not
claim support for every other disc's valid filenames.

On Linux, directory/file access uses directory descriptors and `O_NOFOLLOW`,
with `O_EXCL` file creation. Windows uses handle-relative `NtCreateFile`,
`OBJ_DONT_REPARSE`, explicit reparse-attribute checks and create-only
dispositions; directory inventory uses `NtQueryDirectoryFile`. Every ancestor
is opened separately. The local drive anchor alone resolves the OS drive
mapping. Regular files must have a single hard link. Windows source handles
also deny writable/deletion sharing; opened directories deny deletion sharing.
No fallback follows a refused link, junction or reparse point. POSIX source
opens are nonblocking so a FIFO is rejected as non-regular without waiting.

These are original standard-library `ctypes` interface declarations based on
[Microsoft's file API documentation](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile),
not redistributed SDK headers or a guest-kernel implementation. See also the
[Windows filename rules](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file)
and [Python descriptor-relative APIs](https://docs.python.org/3.11/library/os.html).
Use a private parent under the operator's control; this is a content-preparation
tool, not an OS isolation boundary or a filesystem snapshot service.

Payload hashing/copying uses 1 MiB chunks. The reused parser retains its
16 MiB per-directory, 64 MiB aggregate directory-table and depth limits.
Inventory/manifest memory is proportional to the bounded entry count, not to
the total payload. Default limits are 100,000 entries and at most the declared
ISO size in copied file bytes. `--max-entries` can tighten the entry limit;
`--max-bytes` sets a payload-byte budget. Limits do not change title identity.

After streaming, the tool checks the exact prepared namespace (no extra or
missing entries), reopens every prepared file without following links, and
compares its size and fresh SHA-256 with the streamed copy hash. It then
checks the held source's identity/stat signature and full ISO hash again.
Only then does it exclusively write the final manifest. Each output file and
JSON record is flushed and synced before normal close.

The private manifest records all file paths, offsets, sizes and hashes,
directories, partition offset, source identity, the identity-manifest digest,
exact preparation/parser/guard source hashes, Python/platform and budgets.
It explicitly records no game execution or verified runtime support. Do not
commit or upload it, extracted bytes, private logs, SDKs or keys. Source
ownership and distribution permissions remain separate from hash matching.

## Validation — 2026-11-19

The original synthetic suite lives in `tests/content` and is discovered by
the existing game-free driver without changing shared tests/tools:

```sh
python -m unittest discover -s tests/content -v
python tools/check.py --config Release
python3 tools/check.py --config Release --sanitizers
```

Twenty content cases cover nested/empty files and directories, bounded
large payload reads, root executable/ISO identity failures, entry/byte
budgets, malformed extents, node/directory cycles, excessive depth, Windows
device names and normalization/case collisions, traversal, pre-existing
destinations, retained interrupted attempts, wrong copy-result mutations,
unexpected extra files, source mutation, hardlinks, nonblocking FIFO rejection
and real redirection cases. A separate operator-path test permits legitimate
tilde paths while still rejecting a tilde-named disc entry.

Native Windows passes the focused suite with an explicit unavailable-symlink
privilege skip and a POSIX-only FIFO skip. Actual directory-junction source/destination rejection and
held-directory rename rejection pass. Linux passes with its one explicit
Windows-only junction skip; actual symlink and mid-copy redirection cases run.
Neither platform's skipped case is represented as exercised. Windows Release
passes 138 Python tests with seven explicit skips (the content symlink case,
the POSIX-only FIFO case, one LLVM assembler/objcopy case and four earlier
symlink cases), and native CTest 1/1. Linux Release passes 138 Python tests with one Windows-only skip
and ASan/UBSan native CTest 1/1.

After source review and synthetic checks, native Windows prepared the exact
owner-supplied Rev 1 ISO into a new private D: directory. It verified **219
entries: 218 files and one directory**, totaling **8,112,921,882 file bytes**.
The complete inventory matches the earlier independent disc-inventory names;
the ordinary input verifier independently confirms both copied executable
fingerprints. Initial/final ISO SHA-256 agrees with
`f5531196d7c064a237791e2dc3e9434ee436aab2c4edb49f870f5a7fcda9d1d5`.

The final private content-manifest SHA-256 is
`c585d8136f87ad8ace1676ebe780bdd3fa5c6b50bd18e55cd222cd579533602c`.
The executed preparation source SHA-256 is
`cc535f1a79432f50089e41f721fede983c9f7461127a587cd8c4b2e7df4ff671`.
The owner's source ISO, prior two-XEX directory and writable profiles were
unchanged. Both an existing prepared directory and an existing extracted XEX
were refused by the real CLI; their manifest and executable hashes remain
unchanged. The private `.local/045-owned-index.json` handoff identifies the
local prepared root and receipt; no private path/file inventory is published.

The final native Windows preparation took 53.885 seconds including ISO hashing,
copying, file verification and final source hashing. This is an offline
preparation observation on one machine, with host/cache/concurrent-check effects uncontrolled;
it is not a gameplay/load-time or comparative throughput benchmark. No root
ISO extraction was repeated on Linux; its safety checks use original fixtures.
The earlier 43.701- and 56.579-second positive preparations remain retained
with their own receipt/source bindings; the final run binds both the POSIX
nonblocking guard and the operator-path alias correction.

The first Linux full-check attempt stopped before tests because Windows Git
had written an absolute Windows gitdir path into this task's checkout. Only
this worktree's local gitdir link was made relative; no shared code, checkout
or global Git configuration changed. Review is owner self-review, with no
independent reviewer claimed. A prepared content directory is not evidence of
file-service compatibility, later startup, rendering, audio or gameplay.

Initial Windows CI failed because the strict disc-name policy was also applied
to the hosted runner's short-form temporary path. The policy is now separated
for operator lookups, with a regression test; no reparse/exclusive-create guard
was relaxed. Those failed jobs remain recorded rather than relabelled passing.
