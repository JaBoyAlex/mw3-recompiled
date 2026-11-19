# Join the project with Codex

**Contributors can complete independent code, testing and research tasks now.
The game is not playable yet.** Native Windows/Linux bounded startup and
controlled teardown are verified; original gameplay and rendering remain ahead.

## One-time setup

1. Give the owner your GitHub username and accept the private repository invitation.
2. Clone `https://github.com/JaBoyAlex/mw3-recompiled.git` into your own folder
   and open that folder in Codex. Use your own accounts and credentials.
3. Install or locate Python 3.11+, CMake 3.25+ and Visual Studio 2022 Desktop
   C++ tools on Windows, or GCC/Clang and Ninja on Linux. Python tooling uses
   the standard library. SDK-facing diagnostics have additional documented
   pinned toolchain requirements; research/fixture work can start without them.
4. Paste the prompt below. Check live GitHub ownership even when the local
   backlog says ready. Ask the owner to serialize a reservation if your account
   cannot dispatch task-admin; do not bypass claims by self-assigning manually.
5. Work in your own branch/worktree and submit verified PRs. Do not upload or
   share the owner's ISO. Later title validation needs legal local inputs.

## Copy this prompt

```text
You are contributing to JaBoyAlex/mw3-recompiled, the native MW3 (2011) project.
Read AGENTS.md, CONTRIBUTING.md, docs/STATUS.md, docs/ARCHITECTURE.md,
docs/ROADMAP.md and docs/FRIENDS-START-HERE.md. Apply the relevant project skills.
Fetch current main without overwriting local work. Locate the installed tools
and run python tools/check.py with the actual available CMake/CTest paths.
Run python tools/project.py list --ready and check current GitHub issues,
dependencies, assignees, path reservations and active draft PRs.
Pick a high-priority ready independent task suited to this machine and inputs.
Use the live catalog; do not reopen completed memory/CPU/thread/research tasks.
The lead owns current startup integration and SDK repairs. Coordinate any shared
interface before implementation. Never change another lane's files or processes.
Claim through task-admin, verify success/assignment, and use an isolated
codex/MW3-NNN-description branch and worktree. Different chats sharing one account
must identify their task and branch; an account's other claims are not this chat's.
Generate python tools/project.py prompt MW3-NNN and implement its exact acceptance.
Run meaningful positive/negative and supported sanitizer/platform checks.
Open a reviewable PR with actual evidence, performance impact and limitations.
Update only the task's completion metadata and reserved subsystem documents.
Propose new ideas as scoped tasks with dependencies and acceptance criteria;
do not silently broaden implementation or bypass feature gates.
After a verified merge, refresh the backlog and select another independent task
while authorized to keep working. Preserve an actionable handoff for blockers.
Do not claim gameplay, SDR or performance success from mocks/upstream statements.
Do not commit game bytes, generated game code, SDKs, keys or private traces.
Measure correctness, stability and performance when choosing implementations.
```

## Useful current lanes

The lead handles 041/010 lifecycle acceptance and later bounded service admission.
MW3-045 supplies complete, safe private content preparation and can begin with
Python-only synthetic disc fixtures. MW3-046 tests the actual allocation import
ABI using a verified open-source SDK; it needs no game bytes or GPU. These paths
are disjoint from each other and the lead's harness. Check readiness and claims
again before choosing either task: this paragraph is guidance, not a reservation.

Owned-input acceptance can be verified by the owner after reviewing a game-free
tooling PR; do not mark it complete before that evidence exists. With two people,
the friend chooses one ready lane. With three, use two independent lanes while
the lead integrates. Keep heavy builds and real-game/GPU runs within the recorded
machine budgets. Each lane owns its output, profiles, ports and process handles.

Use area/phase/priority issue labels and linked draft PRs for progress. Each human
remains responsible for their agent's changes. Independent new ideas are welcome
within the documented task/architecture workflow; gameplay balance and other
creative changes beyond the requested scope need an owner decision.
