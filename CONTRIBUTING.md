# Contributing with a small team

The first team is 2–3 humans with their own Codex agents. Each human remains responsible for their agent's changes. Clone the repository, read AGENTS.md, run `python tools/check.py`, and select a ready task. Tooling/docs work does not require game files, Steamworks access or an NVIDIA GPU.

## Tasks, ownership and parallel work

`tasks/MW3-NNN.json` is the versioned specification. Dependencies form a checked DAG; `python tools/project.py validate` refuses missing/cyclic dependencies and completed tasks whose dependencies are unfinished. `list --ready` only uses local catalog state; GitHub claims must also check current remote ownership and dependency issue closure. Never infer ownership from the local ready list alone.

Use the `task-admin` Actions workflow with action `claim` and the task ID. It assigns the actor only if dependencies are complete locally and closed remotely and no active path reservation overlaps. Use action `release` to relinquish your own claim. The workflow uses one concurrency group for sync and claims. GitHub may replace an older pending workflow when several requests arrive together; check that your run succeeded and retry a cancelled request. This is a cooperative workflow, not a server-enforced prohibition on manual issue edits. Contributors must not bypass it by directly assigning issues. Record blockers in the issue/PR; a claim is not a license to edit every subsystem.

Maintainers can dispatch for community contributors who do not have workflow permission. The initial implementation assigns the dispatching actor; for an outside contributor, a maintainer must serialize the reservation and manually assign that contributor after checking dependencies and overlap. Do not grant broad repository access simply to claim a task. Claims have no automatic expiry; post a handoff/release when unavailable and review dormant assignments at integration checkpoints.

Once claimed:

```powershell
git fetch origin
git worktree add ../mw3-MW3-006 -b codex/MW3-006-toolchain origin/main
cd ../mw3-MW3-006
python tools/project.py prompt MW3-006
```

Give the printed prompt to your Codex agent. Each task owns its declared paths. Ask the lead to split/agree a shared contract before overlapping work. Keep modifications to generated catalog summaries out of worker PRs. Only edit your task's JSON when acceptance changes or completes. Track live progress in the issue and linked draft PR; `in_progress` in the catalog is optional and must not replace the GitHub claim.

Suggested initial lanes: lead handles integration and the runtime bakeoff; developer 2 builds the pinned toolchain and CPU tests; developer 3 builds reference scenarios and performance tooling. With two developers, combine QA/tooling and serialize game-heavy runs. Later divide gameplay by mission/map/case using a stable harness. Do not have three agents simultaneously change the job scheduler or rendering interfaces.

## Verification and review

Run `python tools/check.py` plus task-specific tests. Use `python tools/check.py --config Release` when optimized behavior matters; Linux `--sanitizers` adds ASan/UBSan. Keep screenshots/captures local unless approved and rights-reviewed. Include reproducible case IDs, hashes, compiler, GPU/driver and actual observations. Mark unavailable checks `NOT RUN` or `SKIP` with a reason.

Open a PR against `main` with the supplied template and a closing reference to the task issue. Set that task to `done` with evidence only when all acceptance is satisfied; do not close dependencies manually to unlock work. Independent review is preferred, especially kernel, networking, SDK and binary-distribution changes. Lead integrates one green change at a time and reruns affected suites. Until branch rules are configured, review/check requirements are a documented convention; do not claim they are technically enforced.

## Provision the GitHub backlog

`python tools/project.py export .local/issues` produces copyable issue bodies offline. Maintainers can preview `python tools/project.py github-sync --repo JaBoyAlex/mw3-recompiled` and publish with `--apply` using a narrowly scoped GH_TOKEN (or the `task-admin` workflow's token). The sync is idempotent and refuses duplicate task markers; it updates generated scope, preserving existing assignees and open/closed state. **Generated issue bodies are replaced**: keep live progress in comments/PRs, not edited acceptance checkboxes. Close already-verified bootstrap task issues only after their evidence is published. Labels support searches such as `is:issue is:open label:area:gpu`, `label:phase:2`, `label:priority:P0`, and `assignee:@me`.

Never put tokens in prompts, commits or command arguments. Fork PR CI uses no game/SDK secrets. Owned-title integration runs only on a trusted isolated runner after review; untrusted PR code must never execute against game files or Steam credentials.
