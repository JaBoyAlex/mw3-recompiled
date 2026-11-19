# Reference matrix and evidence contract — MW3-004

The original game's full functionality remains the target. This contribution
defines **37 provisional case contracts**, a pinned source ledger and an
executable evidence checker. It does not establish exact-build console
behavior or complete MW3-004. The owner reports no existing console
observations; the manual cross-check and named content inventories remain
outstanding. All committed reference results are **NOT_RUN**, with reasons.

The main native runtime/allocation lane is unchanged. A valid plan, matching
executable hashes, bounded startup or passing synthetic tests cannot stand in
for reference gameplay observations.

## Sources and identity

The publisher's [manual directory](https://support.activision.com/manuals)
links the English Xbox 360 manual under Modern Warfare 3. The actual
[publisher PDF](https://support.activision.com/servlet/servlet.FileDownload?file=00PU0000004Z7f9MAC&retURL=%2Fapex%2Fmanuals)
has 20 pages, metadata title `COL_360MAN_mb08-DIGI.indd`, and SHA-256
`c281bfbd9e5f5b9d4088fe763677b08a48ce8d803c5f8dd230733b7d795ceaca`.
The cover and PDF pages 3, 4 and 6 were rendered and visually checked, using
private PyMuPDF 1.26.7 tooling. PDF page indices are zero-based: menu content
is index 4 / printed page 3; pause/options is index 6 / printed page 5.
The PDF and rendered images remain private, outside Git.

In brief, the manual describes single-player Campaign, checkpoint saving,
mission replay, and Special Ops solo/co-op with local split-screen or online
play. It distinguishes Missions and Survival, and describes three Missions
difficulties. It documents Multiplayer continuing while its objectives menu
is open, plus configurable controls. These are **documented expectations**,
not observations of the owner's exact disc. Per-mission solo/co-op eligibility
must be recorded; the solo menu does not establish that every mission supports
solo play.

The baseline is bound to the existing
[Rev 1 identity manifest](../config/titles/mw3-xbox360-rev1.json), including the
ISO and both executable hashes. The owner-supplied USA/Korea label is not a
new region certification. `not_supplied` title-update/DLC metadata does not
mean an observed console installation has no update or DLC. Submitted executed
cases must explicitly identify the actual console/system/capture tool and
confirm the baseline update/content state. Other states need separately
fingerprinted reference work. Raw version `00000012` is not relabelled TU1.

## Separate mode and player-count coverage

| Reference mode | Documented basis | Exact Rev 1 observations still needed |
| --- | --- | --- |
| Campaign | Single-player mode | Actual join behavior, mission/difficulty/checkpoint lists, progress and replay |
| Spec Ops Missions | Advertised co-op with another player; solo option | Per-mission party eligibility, local/remote ceilings, independent inputs and rewards |
| Survival | Separate wave mode under Special Ops | Its own map list and local/remote ceilings; no inferred equality with Missions |
| Offline local MP | Local play described | Numeric limit and actual controller/viewport/profile ownership |
| Online MP | Online play described | Total capacity and local slots per console measured separately |
| System link | No numeric conclusion drawn here | Transport support and both total/per-console limits, independent of online limits |

The catalog deliberately does not promote the project's preliminary local-MP
four-player expectation into a measured fact. Separate local, online and
system-link values remain null. Four-player Survival is an owner-requested
**extension**, tracked by an optional extension case and MW3-033/034; it cannot
count as original retail parity or replace retail fallback checks.

## Case catalog and incomplete inventories

[`qa/reference/catalog.json`](../qa/reference/catalog.json) contains 23
facts (12 manual expectations, 10 unobserved quantities and one extension
requirement), ten inventory records and 37 stable case IDs. Cases cover:

- Campaign mission/difficulty enumeration, completion/retry, checkpoint
  enumeration/restoration, save/quit, replay and presentation transitions.
- Spec Ops per-mission solo/co-op eligibility and applicable difficulty
  combinations, local admission/ownership, authorized online limits.
- Survival map enumeration, solo/waves, local/online limits, revive/failure,
  restart, progression and profile ownership.
- Local/online/system-link MP counts, maps/game types, objectives-menu
  behavior and round/map transitions.
- Controller reconnect/control options, isolated saves, region/update/DLC
  identity and the separately scoped four-player extension.

Eight required inventories are still unknown: Campaign missions,
difficulties and checkpoints; Spec Ops Missions and difficulties; Survival
maps; baseline MP maps and game types. Other-region and licensed-DLC inputs
are separately `not_supplied`. Unknown inventories have explicit reasons
and no invented entries. An empty list cannot be marked complete. The
prepared disc's file names are not a verified selectable-content catalog.
Gameplay cases depending on an unresolved inventory cannot PASS.

This is a collection plan, not a claim that each mission/map has already been
enumerated or tested. Before freezing the full matrix, record named/stable
content IDs, per-item eligibility and supported transitions from the actual
console. Retain exclusions and locked content explicitly rather than omitting
it to make a coverage percentage pass.

## Commands and result meaning

```sh
python qa/reference/check.py
python qa/reference/check.py --require-console
python qa/reference/check.py --template "$PRIVATE_RESULTS"
python qa/reference/check.py --results "$PRIVATE_RESULTS" --artifacts "$PRIVATE_CAPTURES" --require-console
python -m unittest discover -s qa/reference -p 'test_*.py' -v
```

The first command validates the catalog only (exit 0). Today it reports 37
cases, ten unknown facts, eight unresolved required inventories and
`console_submission_complete: false`. `--require-console` returns **2** for
that incomplete state. Invalid JSON/contracts/evidence return **1**. A
template is exclusively created with all cases NOT_RUN; an existing file is
never replaced. Keep templates, captures and completed submissions private.

The submission binds the exact logical catalog digest and baseline identities.
It must include every case once; missing, duplicate, extra or stale cases are
rejected. An executed case requires a console context, explicit checks and
hash-matched relative-path artifacts. PASS also requires every planned check
true, typed observations matching reviewed expectations, and all of that
case's inventory dependencies resolved. FAIL is retained with a reason and
capture, while SKIP/NOT_RUN require explicit reasons. A timeout or unsuitable
session is not a passing result.

Declared synthetic work remains synthetic, even with realistic Xbox-shaped
metadata. Native-runtime, source-inspection and emulator evidence cannot be
labelled console-reference origins. An unknown quantity cannot pass by
supplying a plausible number; a reviewed console observation must first
resolve its catalog expectation. Update/DLC ambiguity cannot silently inherit
the baseline, and extension cases cannot satisfy required retail coverage.

Artifact checks validate bytes/paths, not their meaning or console authenticity.
The checker does not authenticate hardware, prove that a video depicts this
disc, or review image/audio/input behavior. Even a complete declared console
submission retains `semantic_review_required: true` and
`gameplay_certified: false`. Human provenance/behavior review remains necessary;
handwritten metadata or true booleans cannot manufacture that evidence.

## Verification and remaining handoff

The explicit QA suite has 20 original synthetic contracts: unknown facts,
source-class/page/pin mismatches, missing mode/case coverage, empty-complete
inventories, extension/retail confusion, wrong build/update/DLC contexts,
stale catalogs, duplicate/nonfinite/oversized JSON, missing/failed checks,
wrong value types, tampered/unsafe/redirected captures, retained failures and
exclusive templates. Synthetic fixtures are labelled and never console proof.

The QA suite passes 20 tests on Windows (one unavailable-symlink privilege
skip) and Linux (no skips). Root Windows Release checks pass 138 Python tests
with seven explicit platform/tool/privilege skips and native CTest 1/1. Root
Linux Release ASan/UBSan checks pass 138 Python tests with one Windows-only
skip and native CTest 1/1. Owner self-review is recorded; no independent review
or console execution is claimed.

Run this QA command explicitly: it lives in the reserved `qa/reference` scope
and is **not automatically discovered by the root `tests/` CI driver**. Root
game-free checks remain separately required; their green CI result does not
claim the QA suite or console cases ran. No shared CI/test interface was
changed without a separate task.

To complete MW3-004: capture the supported disc on an Xbox 360 with isolated
profiles; reconcile its actual update/content state; enumerate required
content and per-mission party restrictions; exercise and review the applicable
case contracts; update the ledger with exact console evidence and retained
disagreements. Online sessions require actual authorization and suitable
participants; this tool launches nothing and contacts no game service. Until
that evidence exists, leave task 004 open and its console validation blocked.
This does not block unrelated private native bring-up or represent a gameplay,
performance, release or network gate passing.
