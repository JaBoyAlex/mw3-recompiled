# Owner-supplied baseline identity

Read-only inspection on 2026-11-17. Owner-selected filename describes USA/Korea **Rev 1**. This is not proof of a separate title update or the meaning of informal "1.1". No separate update package was supplied. Header identity and hashes are recorded in `config/titles/mw3-xbox360-rev1.json`; no executable/content bytes are included there.

| Input | Size | SHA-256 |
| --- | ---: | --- |
| Supplied ISO | 8,738,846,720 | `f5531196d7c064a237791e2dc3e9434ee436aab2c4edb49f870f5a7fcda9d1d5` |
| `default.xex` | 6,082,560 | `f59be1342c2fc664e2a2e7322d024028a0ca7216d279ed32fef6e114d8c37c30` |
| `default_mp.xex` | 6,705,152 | `ba1bc57af4c4f75934a106b3d470559b356252b9e100d98e335bcfd0e574806a` |

The XDVDFS reader found 219 entries and both root title executables. Both XEX execution-info records report title ID `415608cb`, media ID `3b46ae32`, raw version/base-version `00000012` and disc 1 of 1. Do not relabel those raw values as retail "1.1" or TU1. The source filename's region designation has not been independently certified by a catalog or full content audit.

The independent native XEX inspector agrees with the Python reader on container layout: SP module flags 1, image offset `0x5000`, security offset `0xa0`, 17 optional entries; MP flags 1, image offset `0x5000`, security offset `0xa8`, 18 entries. The entry-point optional values are SP `0x82459e58`, MP `0x824dbae0`; these are observed metadata, not validated function maps or hook addresses. Neither tool decrypts or executes the title.

The ISO was opened read-only and streamed for hashing. Only the two root executables were copied to ignored private workspace storage using exclusive output creation. Reports retain file basenames and hashes, not the owner's absolute paths. A hash identifies these exact supplied bytes; it does not prove ownership, authenticity, runtime compatibility or online matchmaking stability. The manifest remains **identified-not-runtime-supported** until later analysis and execution gates pass. Unsupported builds must be rejected by the eventual preparation/runtime pipeline; the current inspectors merely report metadata.

## Preparation input verification

`python tools/verify_inputs.py <private executable directory>` now requires both exact root executable fingerprints from the versioned manifest. Missing, swapped/mixed, modified and wrong-format inputs fail before a preparation tool should consume them. A matching pair returns `fingerprint_match: true` while explicitly returning `runtime_supported: false` and `ownership_verified: false`. The supplied pair passed this check; no additional title-update package was supplied or silently downloaded. Other regions/revisions and user-modified executables remain unrecognized rather than inheriting this manifest's identity.

Synthetic regression cases verify matching pairs, modified bytes, swapped executables, a non-XEX platform candidate, missing files and malformed/path-traversing manifests. They use original synthetic data, not game bytes. This completes baseline identification and a reusable input guard; it does not claim that the entire ISO is authentic or that this build runs.
