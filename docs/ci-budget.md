# Conserve Actions usage without weakening verification — MW3-049

The owner reported 1,800 of 2,000 included Actions minutes used. This routing
change avoids repeated work; it does not change a platform test, action pin,
permission, compiler setting or product feature. No paid allowance, repository
visibility or runner service is configured by this task.

## Which events run checks

| Event | Public checks | Host-toolchain preparation |
| --- | --- | --- |
| Feature-branch push | No duplicate run; open/update its PR for validation. | No duplicate run. |
| Pull request | Existing Windows/Linux Debug/Release plus Linux sanitizers. | Existing build/independent rebuild only for relevant paths below. |
| Main push | Same full public matrix, including integrated changes. | Relevant paths only. |
| Explicit manual dispatch | Same full public matrix on the selected ref. | Explicit preparation request, independent of path filters. |

Ordinary CI uses a workflow-specific concurrency group keyed by PR number or
ref, cancelling superseded runs in that group. Different PRs do not share a
group simply because their source branches have the same name. A cancelled run
is not a successful check; the reviewed head still needs completed validation.
The separately serialized `task-admin` workflow is unchanged and must not be
cancelled as part of this policy.

The host-toolchain filter now covers the actual inputs of
`tools/prepare_toolchain.py`: that script, `config/toolchains/lock.json`, original
`fixtures/**`, the `smoke/**` project, `cmake/toolchains/**` integration and its
workflow. Changes confined to SDK profiles such as `rexglue-memory`,
`rexglue-input-snapshot` or `rexglue-conditional-so` do not rebuild unrelated CPU
and shader host tools. They still receive the public PR checks, and their own
private acceptance suites remain required. If the preparation tool gains another
input, update this allowlist in the same reviewed change.

## Local work when hosted usage is scarce

Development, Git commits and local checks do not require an Actions runner.
Run relevant task suites with the installed tools and retain their commands,
source/configuration/binary identities, failures and logs. For the public suite:

```text
# Native Windows with CMake/CTest and MSVC installed/on PATH
python tools/check.py --config Debug
python tools/check.py --config Release

# Native Linux or WSL, using its installed compiler/CMake/Ninja
python3 tools/check.py --config Debug
python3 tools/check.py --config Release
python3 tools/check.py --sanitizers
```

Windows and WSL on one machine are useful platform checks, not two independent
machines. Keep private SDK/title suites local and isolated; public CI does not
obtain game bytes, SDKs or credentials. Local passing results do not certify an
unrun hosted job, actual gameplay or another machine's hardware.

For a long local development cycle, hold intermediate pushes or explicitly mark
work-in-progress commits with GitHub's documented `[skip ci]` instruction. At a
finished revision, either allow normal PR validation or deliberately dispatch
`game-free-ci` once against that exact branch/head. Do not request a manual copy
of an already running automatic matrix. Record the exact SHA, workflow run and
all five job results before treating that head as verified.

Skip instructions apply to push/PR triggers, not manual dispatch. Skipped
required checks can remain pending and block a merge. Never manufacture a green
status or label a skipped/queued/cancelled check as passed. If quota prevents a
required run, document hosted validation as **NOT RUN: Actions allowance** and
keep the review/integration gate outstanding. The owner can decide any policy
exception explicitly; this document does not create one.

Claims still go through serialized `task-admin`, including when ordinary CI is
deferred. If it cannot run, do not bypass ownership by assigning issues manually;
continue useful work within an existing claim and record the blocker. Do not
cancel another contributor's unrelated runs or change their branch/profile.

This task's metadata-only scope used a skip-marked commit plus one explicit
five-job dispatch, with no duplicate push/PR runs. Its catalog-only squash kept
the skip marker to avoid repeating that already completed verification. Normal
main validation remains available under the workflow; a code integration still
needs honest evidence for its final integrated state.

GitHub's current documentation covers [skip/pending behavior](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs),
[event/path filters](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
and [concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).
Billing terms can change; this policy makes no promise that self-hosted Actions
will be free on a particular plan. It relies on local CLI validation and reduced
hosted work, without a new financial commitment.

## Verification and limits

The Windows/Linux Debug/Release matrix, sanitizer command, job timeouts,
permissions and pinned action versions are unchanged. The complete `jobs:`
sections of both workflows must remain byte-identical to the pre-change base.
Only event routing, ordinary-CI concurrency and toolchain path filters change.

Review positive paths (script, root lock, original fixture, smoke project,
CMake integration and workflow) and negative paths (SDK profiles, docs and task
metadata) for both PR and main-push routing. Feature pushes are excluded; manual
dispatch remains explicit. Workflow lint verifies YAML/expressions; this is
routing verification, not a new full host-toolchain performance comparison.

Removing a feature-push matrix eliminates one redundant matrix when the same
revision is also submitted through a PR. Actual billed savings depend on job
duration, platform accounting, rounding and workload; no unmeasured minute or
percentage saving is claimed. Main integration checks and serialized ownership
work still consume hosted allowance. Product performance/quality is unchanged.
Self-review only; no independent review is represented.

Local verification on the unchanged application/test code passes 246 Python
tests on each host: Windows Release has eight explicit skips and parser CTest
1/1; Linux Release with ASan/UBSan has two Windows-only skips and parser 1/1.
Both changed workflows pass actionlint 1.7.12 with optional shellcheck/pyflakes
integrations disabled (no shell/Python step changed). Its published archive
checksum was verified; executable SHA-256 is
`54ca21be3de4c7cfa26914aa8b61bd76bf573ef3caac5f80d110558cdf241718`.

The pre-change comparison base is
`c80d20d13506506262d60b2d1afbf797e7b02e71`. Byte-identical `jobs:` section
SHA-256 values are `a87aeaba7265900c155b5e50bf9b00d89a5138639b366af770e0446c17b30e2c`
for public CI and `3e7f0a81f99c5e99705fa1993a010a07c4d7250648fe6506169f6797dc59ad23`
for host-toolchain preparation. Eight positive and six negative declared-path
examples were reviewed; this static review is not a simulated GitHub event run.
The scope's actual single hosted run is
[44505161813](https://github.com/JaBoyAlex/mw3-recompiled/actions/runs/44505161813)
at head `7bdab8385b83d881f983725983014c9dd1bc4430`, with all five jobs successful.
Final implementation-head results are attached to its PR before integration.
