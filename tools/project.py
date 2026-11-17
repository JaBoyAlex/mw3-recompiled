#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Dependency-aware task catalog and GitHub issue provisioning (standard library only)."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STATES = {"todo", "in_progress", "blocked", "done"}


def load_tasks(root=ROOT):
    tasks = {}
    for path in sorted((root / "tasks").glob("MW3-*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        ident = task.get("id", "")
        if not re.fullmatch(r"MW3-\d{3}", ident) or path.stem != ident or ident in tasks:
            raise ValueError(f"invalid or duplicate task id in {path.name}")
        for key in ("title", "area", "goal", "size"):
            if not isinstance(task.get(key), str) or not task[key].strip():
                raise ValueError(f"{ident}: missing {key}")
        if task.get("status") not in STATES or type(task.get("phase")) is not int or not 1 <= task["phase"] <= 6:
            raise ValueError(f"{ident}: invalid status or phase")
        if type(task.get("priority")) is not int or not 0 <= task["priority"] <= 3:
            raise ValueError(f"{ident}: priority must be 0..3")
        for key in ("depends_on", "paths", "acceptance", "validation"):
            if not isinstance(task.get(key), list) or not all(isinstance(v, str) and v for v in task[key]):
                raise ValueError(f"{ident}: invalid {key}")
            if key != "depends_on" and not task[key]:
                raise ValueError(f"{ident}: {key} must not be empty")
        if len(task["depends_on"]) != len(set(task["depends_on"])):
            raise ValueError(f"{ident}: repeated dependency")
        if task["status"] == "done" and not task.get("evidence"):
            raise ValueError(f"{ident}: done requires evidence")
        tasks[ident] = task
    if not tasks:
        raise ValueError("empty task catalog")
    visiting, visited = set(), set()

    def visit(ident):
        if ident not in tasks:
            raise ValueError(f"unknown dependency {ident}")
        if ident in visiting:
            raise ValueError(f"dependency cycle at {ident}")
        if ident in visited:
            return
        visiting.add(ident)
        for dep in tasks[ident]["depends_on"]:
            visit(dep)
            if tasks[ident]["status"] == "done" and tasks[dep]["status"] != "done":
                raise ValueError(f"{ident}: completed before dependency {dep}")
        visiting.remove(ident)
        visited.add(ident)
    for ident in tasks:
        visit(ident)
    return tasks


def blockers(task, tasks):
    return [dep for dep in task["depends_on"] if tasks[dep]["status"] != "done"]


def prompt(task):
    return (f"Work on {task['id']}: {task['title']}. Read AGENTS.md, CONTRIBUTING.md and docs/STATUS.md.\n"
            f"Goal: {task['goal']}\nDependencies: {', '.join(task['depends_on']) or 'none'}. Confirm they are done.\n"
            f"Own these paths: {', '.join(task['paths'])}. Coordinate before changing shared interfaces.\n"
            "Acceptance:\n" + "\n".join(f"- {x}" for x in task["acceptance"]) +
            "\nValidation:\n" + "\n".join(f"- {x}" for x in task["validation"]) +
            "\nUse an isolated branch/worktree. Claim the issue before implementation. Record actual evidence, "
            "limitations and commands in the PR; update only this task's status/evidence when acceptance is met. "
            "Do not commit game bytes, generated game code, keys, SDKs, or private logs.\n")


def issue_body(task, numbers=None):
    numbers = numbers or {}
    deps = ", ".join(f"#{numbers[d]} ({d})" if d in numbers else d for d in task["depends_on"]) or "none"
    return (f"<!-- mw3-task:{task['id']} -->\n{task['goal']}\n\n"
            f"Phase: {task['phase']} | Area: {task['area']} | Size: {task['size']} | Priority: P{task['priority']}\n\n"
            f"Dependencies: {deps}\n\nPaths: " + ", ".join(f"`{p}`" for p in task["paths"]) +
            "\n\nAcceptance criteria:\n" + "\n".join(f"- [ ] {v}" for v in task["acceptance"]) +
            "\n\nCopyable agent prompt:\n```text\n" + prompt(task) + "```\n\n"
            "Catalog defines scope; issue assignee is the current owner. Completed work needs a merged, verified PR.\n")


class GitHub:
    def __init__(self, repo, token=None):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ValueError("repository must be OWNER/REPO")
        self.base = f"https://api.github.com/repos/{repo}"
        self.token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    def call(self, method, path, data=None):
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "mw3-project-tools"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if method != "GET" and not self.token:
            raise ValueError("GitHub write requires GH_TOKEN or GITHUB_TOKEN")
        body = json.dumps(data).encode() if data is not None else None
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                return json.loads(payload) if payload else None
        except urllib.error.HTTPError as e:
            # Do not print response bodies, tokens or request headers.
            raise ValueError(f"GitHub {method} {path.split('?')[0]} returned HTTP {e.code}") from None

    def issues(self):
        items = {}
        page = 1
        while True:
            rows = self.call("GET", f"/issues?state=all&labels=mw3-task&per_page=100&page={page}")
            for row in rows:
                if "pull_request" in row:
                    continue
                match = re.match(r"<!-- mw3-task:(MW3-\d{3}) -->", row.get("body") or "")
                if match:
                    ident = match[1]
                    if ident in items:
                        raise ValueError(f"duplicate remote task {ident}; resolve before proceeding")
                    items[ident] = row
            if len(rows) < 100:
                break
            page += 1
        return items


def sync(tasks, github, apply=False):
    remote = github.issues()
    labels = {"mw3-task"}
    for t in tasks.values():
        labels.update((f"area:{t['area']}", f"phase:{t['phase']}", f"priority:P{t['priority']}"))
    if apply:
        existing = set()
        page = 1
        while True:
            rows = github.call("GET", f"/labels?per_page=100&page={page}")
            existing.update(row["name"] for row in rows)
            if len(rows) < 100:
                break
            page += 1
        for label in sorted(labels - existing):
            github.call("POST", "/labels", {"name": label, "color": "355C7D"})
    for ident, task in tasks.items():
        if ident not in remote:
            print(f"create {ident}: {task['title']}")
            if apply:
                remote[ident] = github.call("POST", "/issues", {"title": f"[{ident}] {task['title']}", "body": issue_body(task),
                    "labels": ["mw3-task", f"area:{task['area']}", f"phase:{task['phase']}", f"priority:P{task['priority']}"]})
    numbers = {i: row["number"] for i, row in remote.items()}
    for ident, task in tasks.items():
        if ident in remote:
            row = remote[ident]
            # Preserve assignees, state and manually managed progress; only update generated scope.
            body = issue_body(task, numbers)
            title = f"[{ident}] {task['title']}"
            if row["body"] != body or row["title"] != title:
                print(f"update {ident} scope")
                if apply:
                    github.call("PATCH", f"/issues/{row['number']}", {"title": title, "body": body})
    if not apply:
        print("Dry run; no writes. Pass --apply to publish catalog issues.")


def claim(tasks, github, ident, owner, action="claim", apply=False):
    if ident not in tasks or not re.fullmatch(r"[A-Za-z0-9-]{1,39}", owner):
        raise ValueError("invalid task or GitHub login")
    if apply and os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("claim mutations run only in the serialized task-admin GitHub workflow")
    remote = github.issues()
    if ident not in remote:
        raise ValueError("task issue has not been published")
    row = remote[ident]
    owners = [a["login"] for a in row["assignees"]]
    if row["state"] != "open" or tasks[ident]["status"] == "done":
        raise ValueError("task is already complete")
    if action == "claim":
        if tasks[ident]["status"] == "blocked":
            raise ValueError("task is explicitly blocked; lead must record blocker resolution")
        missing = [d for d in tasks[ident]["depends_on"] if tasks[d]["status"] != "done" or d not in remote or remote[d]["state"] != "closed"]
        if missing:
            raise ValueError("unfinished dependencies: " + ", ".join(missing))
        if owners and owners != [owner]:
            raise ValueError("task already assigned to " + ", ".join(owners))
        # Reject overlapping scopes with other active claims. Broad root paths conflict intentionally.
        for other, issue in remote.items():
            if other == ident or other not in tasks or issue["state"] != "open" or not issue["assignees"]:
                continue
            for a in tasks[ident]["paths"]:
                for b in tasks[other]["paths"]:
                    if a.rstrip("/") == b.rstrip("/") or a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/"):
                        raise ValueError(f"scope conflicts with assigned task {other}: {a} / {b}")
        print(f"claim {ident} for {owner}")
        if apply:
            github.call("POST", f"/issues/{row['number']}/assignees", {"assignees": [owner]})
    else:
        if owners != [owner]:
            raise ValueError("only the current sole assignee can release this claim")
        print(f"release {ident} from {owner}")
        if apply:
            github.call("DELETE", f"/issues/{row['number']}/assignees", {"assignees": [owner]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    listing = sub.add_parser("list")
    listing.add_argument("--ready", action="store_true")
    listing.add_argument("--area")
    listing.add_argument("--query", default="")
    sub.add_parser("prompt").add_argument("id")
    sub.add_parser("export").add_argument("directory", type=Path)
    for name in ("github-sync", "github-claim", "github-release"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--repo", required=True)
        cmd.add_argument("--apply", action="store_true")
        if name != "github-sync":
            cmd.add_argument("id")
            cmd.add_argument("--owner", required=True)
    args = parser.parse_args()
    try:
        tasks = load_tasks()
        if args.command == "validate":
            print(f"PASS: {len(tasks)} tasks; valid dependency DAG")
        elif args.command == "list":
            for t in sorted(tasks.values(), key=lambda t: (t["priority"], t["phase"], t["id"])):
                waiting = blockers(t, tasks)
                ready = t["status"] == "todo" and not waiting
                if args.ready and not ready or args.area and t["area"] != args.area or args.query.casefold() not in json.dumps(t).casefold():
                    continue
                status = "ready" if ready else t["status"] if not waiting else "waiting:" + ",".join(waiting)
                print(f"{t['id']} P{t['priority']} phase:{t['phase']} {t['area']} [{status}] {t['title']}")
        elif args.command == "prompt":
            print(prompt(tasks[args.id]))
        elif args.command == "export":
            args.directory.mkdir(parents=True, exist_ok=True)
            for ident, task in tasks.items():
                (args.directory / f"{ident}.md").write_text(issue_body(task), encoding="utf-8")
            print(f"Exported {len(tasks)} issue bodies")
        elif args.command == "github-sync":
            sync(tasks, GitHub(args.repo), args.apply)
        else:
            claim(tasks, GitHub(args.repo), args.id, args.owner, "release" if args.command == "github-release" else "claim", args.apply)
    except (ValueError, KeyError, OSError, urllib.error.URLError) as e:
        parser.exit(1, f"project tool failed: {e}\n")


if __name__ == "__main__":
    main()
