# Join the project with Codex

**The foundation is ready for friends to help with tooling, research and test design now. The game is not playable yet.** Initial CI has passed on Windows/Linux Debug/Release and Linux sanitizers; the 35-task issue catalog is published.

## One-time setup

1. Give the project owner your GitHub username and accept the private repository invitation once sent. No invitation has been sent automatically.
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
Prefer MW3-004 (reference gameplay/test matrix) or MW3-005 (measurement/evidence tooling)
for initial parallel work; the lead owns integration and toolchain decisions.
Confirm dependencies and scope, claim through task-admin, verify the assignment,
and use a codex/MW3-NNN-description branch in an isolated worktree.
Use python tools/project.py prompt MW3-NNN for the task's exact acceptance criteria.
Implement the task, run meaningful checks and submit a reviewable PR with actual evidence.
Document missing prerequisites and do useful independent work while blocked.
Do not claim gameplay, SDR or performance success from mocks or upstream statements.
Do not commit game bytes, generated game code, SDKs, keys or private logs.
Measure and consider performance in every architecture/implementation decision.
```

Suggested lanes for three humans: lead on toolchain/runtime integration; friend A on MW3-004; friend B on MW3-005. For two humans, the friend takes either independent task. Scope is reserved by the task; changing common interfaces needs coordination first. Use issue labels for area/phase/priority and link your draft PR for progress. A later game-testing lane needs an owned copy and isolated profiles on that contributor's machine; you do not need to upload the owner's ISO anywhere.
