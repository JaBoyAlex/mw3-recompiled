# Join the project with Codex

**Friends can help with independent memory, CPU and thread-test lanes now. The game is not playable yet.** Private Linux probes execute bounded startup through one audited import. Windows/Linux game-free CI passes; the 41-task catalog includes the new kernel lanes.

## One-time setup

1. Give the project owner your GitHub username and accept the owner's private repository invitation.
2. Clone `https://github.com/JaBoyAlex/mw3-recompiled.git` into your own local folder and open that folder as a Codex project. Use your own GitHub/Codex account; do not share credentials.
3. For native builds, install Python 3.11+, CMake 3.25+ and Visual Studio 2022 Build Tools with Desktop C++ on Windows (or GCC/Clang and Ninja on Linux). Your agent can locate an existing installation. Research-only work can begin without the native compiler. Project Python tools need no pip packages.
4. Paste the prompt below into Codex. The agent should run the checks, find a ready disjoint task, and claim it using the documented GitHub workflow. If you lack workflow dispatch permission, the owner can reserve the task for you after verifying scope.
5. Work on your own branch/worktree, push a branch and submit a verified PR. Never commit game files. Most initial tasks require no MW3 files, Steam SDK or NVIDIA GPU.

## Copy this prompt

```text
You are contributing to JaBoyAlex/mw3-recompiled, the native MW3 (2011) project.
Read AGENTS.md, CONTRIBUTING.md, docs/STATUS.md and docs/FRIENDS-START-HERE.md.
Find installed Python/CMake/compiler tools and run python tools/check.py when available.
Run python tools/project.py list --ready and inspect the current GitHub issues/assignees.
Pick one high-priority independent task suited to this machine and available inputs.
Prefer a ready MW3-037 (memory), MW3-038 (PPC oracle) or MW3-039 (threads) test lane,
or MW3-004 if console-reference hardware is available. Match prerequisites to this machine;
the selected SDK currently builds on Linux/WSL and these test lanes need no game bytes.
The lead owns the guarded startup harness; coordinate shared interface or SDK repairs.
Confirm dependencies and scope, claim through task-admin, verify the assignment,
and use a codex/MW3-NNN-description branch in an isolated worktree.
Use python tools/project.py prompt MW3-NNN for the task's exact acceptance criteria.
Implement the task, run meaningful checks and submit a reviewable PR with actual evidence.
Document missing prerequisites and do useful independent work while blocked.
Do not claim gameplay, SDR or performance success from mocks or upstream statements.
Do not commit game bytes, generated game code, SDKs, keys or private logs.
Measure and consider performance in every architecture/implementation decision.
```

Suggested lanes: lead on startup/platform integration, friend A on the PPC oracle
(038), friend B on memory tests (037), then thread tests (039). With two people,
the friend selects one ready lane. See [the lane plan](engine/BRINGUP-PLAN.md).
Scopes are path reservations; changing shared interfaces needs coordination.
Use area/phase/priority labels and link a draft PR for progress. A later title
test needs that contributor's own legal files and isolated profiles. The owner's
ISO does not need to be uploaded or shared.
