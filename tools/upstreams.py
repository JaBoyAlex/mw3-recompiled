#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Fetch or verify pinned research checkouts. Never builds or executes upstream code."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", *map(str, args)], text=True, stderr=subprocess.PIPE).strip()


def verify(path, entry):
    if git("-C", path, "rev-parse", "HEAD") != entry["commit"]:
        raise ValueError(f"{entry['name']}: HEAD differs from lock")
    if git("-C", path, "status", "--porcelain", "--untracked-files=normal"):
        raise ValueError(f"{entry['name']}: dirty research checkout")
    for name, digest in entry["license_sha256"].items():
        if hashlib.sha256((path / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"{entry['name']}: license digest differs: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fetch", "verify"))
    parser.add_argument("--root", type=Path, default=ROOT / ".local" / "upstreams")
    args = parser.parse_args()
    try:
        entries = json.loads((ROOT / "config" / "upstreams.lock.json").read_text())["upstreams"]
        for entry in entries:
            path = args.root / entry["name"]
            if args.action == "fetch" and not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                git("clone", "--no-checkout", "--filter=blob:none", entry["url"], path)
                git("-C", path, "checkout", "--detach", entry["commit"])
            verify(path, entry)
            print(f"PASS {entry['name']} {entry['commit'][:12]}")
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        parser.exit(1, f"upstream verification failed: {e}\n")


if __name__ == "__main__":
    main()
