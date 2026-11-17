#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Read explicit owned files without copying, decrypting or modifying them."""
import argparse
import hashlib
import json
from pathlib import Path


def identify(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("input must be a regular, non-symlink file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        import os
        before = os.fstat(stream.fileno())
        magic = stream.read(4)
        digest.update(magic)
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("input changed while hashing; retry with an unchanged file")
    kind = "XEX2" if magic == b"XEX2" else "ELF" if magic == b"\x7fELF" else "PE-candidate" if magic[:2] == b"MZ" else "unknown"
    return {"name": path.name, "size": after.st_size, "sha256": digest.hexdigest(), "format": kind}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--label", default="xbox360-1.1-unverified")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        files = sorted((identify(p) for p in args.files), key=lambda x: (x["name"], x["sha256"]))
        if len({f["name"].casefold() for f in files}) != len(files):
            raise ValueError("duplicate basenames; inventory different builds separately")
        report = {"schema_version": 1, "label": args.label, "supported_build": False, "files": files}
        output = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            # Never overwrite an input, an existing report, or a symlink target.
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(output)
        else:
            print(output, end="")
        return 0
    except (OSError, ValueError) as error:
        parser.exit(1, f"inventory failed: {error}\n")


if __name__ == "__main__":
    main()
