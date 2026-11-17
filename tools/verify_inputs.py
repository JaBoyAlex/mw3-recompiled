#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Match an owned SP/MP executable pair to the versioned identity manifest.

Fingerprint matching is not ownership verification, decryption or runtime support.
"""
import argparse
import json
from pathlib import Path
import re

from inventory import identify

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "config/titles/mw3-xbox360-rev1.json"
NAMES = {"default.xex", "default_mp.xex"}


def validate_manifest(manifest):
    if manifest.get("schema_version") != 1 or manifest.get("status") != "identified-not-runtime-supported":
        raise ValueError("expected an identified, not runtime-supported manifest")
    rows = manifest.get("executables")
    if not isinstance(rows, list) or len(rows) != 2 or {row.get("name") for row in rows} != NAMES:
        raise ValueError("manifest must specify exactly the two known root title executables")
    for row in rows:
        if row.get("format") != "XEX2" or type(row.get("size")) is not int or not 24 <= row["size"] <= 256 * 1024 * 1024:
            raise ValueError("invalid executable manifest format/size")
        if not re.fullmatch(r"[a-f0-9]{64}", row.get("sha256", "")):
            raise ValueError("invalid executable SHA-256")
    if not isinstance(manifest.get("id"), str) or not manifest["id"]:
        raise ValueError("missing manifest identity")


def verify(directory, manifest):
    validate_manifest(manifest)
    results = []
    for expected in manifest["executables"]:
        found = identify(Path(directory) / expected["name"])
        if any(found[key] != expected[key] for key in ("name", "format", "size", "sha256")):
            raise ValueError(f"{expected['name']}: fingerprint mismatch; wrong, mixed or modified build")
        results.append(found)
    return dict(schema_version=1, manifest_id=manifest["id"], fingerprint_match=True,
                runtime_supported=False, ownership_verified=False, executables=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        print(json.dumps(verify(args.directory, manifest), indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"input verification failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
