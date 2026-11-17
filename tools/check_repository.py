#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Check tracked and candidate files for accidentally included game/SDK artifacts."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {".iso", ".xex", ".xexp", ".ff", ".pak", ".bik", ".dll", ".exe", ".dmp", ".cofr"}
FORBIDDEN_ROOTS = {"game", "generated", "private", ".local", "out", "build"}


def main():
    rows = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT).split(b"\0")
    errors = []
    for raw in rows:
        if not raw:
            continue
        name = raw.decode("utf-8")
        path = ROOT / name
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or Path(name).parts[0] in FORBIDDEN_ROOTS:
            errors.append(name)
        elif path.is_file():
            with path.open("rb") as stream:
                magic = stream.read(4)
            if magic in (b"XEX2", b"\x7fELF") or magic[:2] == b"MZ":
                errors.append(name)
    if errors:
        print("FAIL: prohibited artifact candidates:\n" + "\n".join(sorted(set(errors))))
        return 1
    print("PASS: repository artifact check (heuristic; manual provenance review still required)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
