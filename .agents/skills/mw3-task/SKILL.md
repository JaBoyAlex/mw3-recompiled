---
name: mw3-task
description: Select and implement a scoped mw3-recompiled backlog task with dependency checks, ownership isolation and review evidence.
---

Read root AGENTS.md, CONTRIBUTING.md and docs/STATUS.md. Run `python tools/project.py list --ready` and generate a prompt for the selected task. Read its JSON and current GitHub issue; local readiness does not establish remote availability.

Claim via task-admin before implementation and verify the successful run/assignee. Use an isolated worktree and only the reserved paths. Split an epic before claiming. Coordinate a shared interface before changing another lane's contract. Keep game inputs, writable profiles and process ownership isolated.

Implement to observable acceptance criteria. Run `python tools/check.py` and task-specific validation. Distinguish synthetic/mocked checks from owned-title execution and two-machine results. Unknown imports or missing peers cannot pass by fallback.

Update only this task's JSON with evidence when complete. Submit a reviewable PR with commands, results, failures/skips, performance impact and limitations. If blocked, preserve a concrete handoff and select independent work; do not mark unfinished acceptance done.
