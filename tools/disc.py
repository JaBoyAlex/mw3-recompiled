#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Bounded, read-only XDVDFS inventory and executable identity inspection.

Directory format and partition probing adapted from PaulCombal/mw2-recompiled
tools/xdvdfs.py at b3aa7d8ef184de8ec1f0d2fe7fa0e19a4c92b68b (GPL-3.0-only).
Bounds, budgets, identity reporting and exclusive extraction added for this project.
No decryption or game execution is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

SECTOR = 2048
MAGIC = b"MICROSOFT*XBOX*MEDIA"
PARTITIONS = (0, 0xFD90000, 0x2080000, 0x18300000, 0x18310000)


class Disc:
    def __init__(self, stream, size):
        self.stream, self.size = stream, size
        self.base = None
        for offset in PARTITIONS:
            if offset + 33 * SECTOR <= size:
                descriptor = self.read(offset + 32 * SECTOR, SECTOR)
                if descriptor[:20] == MAGIC and descriptor[-20:] == MAGIC:
                    self.base = offset
                    self.root_sector, self.root_size = struct.unpack_from("<II", descriptor, 20)
                    break
        if self.base is None:
            raise ValueError("XDVDFS descriptor not found at supported partition offsets")

    def read(self, offset, size):
        if offset < 0 or size < 0 or offset > self.size or size > self.size - offset:
            raise ValueError("disc extent outside image")
        self.stream.seek(offset)
        data = self.stream.read(size)
        if len(data) != size:
            raise ValueError("truncated disc read")
        return data

    def entries(self):
        output, directories, names = [], set(), set()
        total_directory_bytes = 0

        def walk(sector, size, prefix, depth):
            nonlocal total_directory_bytes
            if depth > 32 or (sector, size) in directories:
                raise ValueError("cyclic or excessively deep directories")
            if size == 0:
                return
            directories.add((sector, size))
            total_directory_bytes += size
            if size > 16 * 1024 * 1024 or total_directory_bytes > 64 * 1024 * 1024:
                raise ValueError("directory byte budget exceeded")
            data = self.read(self.base + sector * SECTOR, size)
            pending, seen = [0], set()
            while pending:
                index = pending.pop()
                if index in seen:
                    raise ValueError("cyclic directory tree")
                seen.add(index)
                at = index * 4
                if at + 14 > len(data):
                    raise ValueError("directory node outside table")
                left, right, start, length, flags, nlen = struct.unpack_from("<HHIIBB", data, at)
                if left == 0xFFFF:
                    continue
                if nlen == 0 or at + 14 + nlen > len(data):
                    raise ValueError("invalid directory name extent")
                name = data[at + 14:at + 14 + nlen].decode("latin-1")
                if name in (".", "..") or any(c in name for c in "/\\:\x00") or any(ord(c) < 32 for c in name):
                    raise ValueError("unsafe disc name")
                for child in (left, right):
                    if child:
                        pending.append(child)
                offset = self.base + start * SECTOR
                if offset > self.size or length > self.size - offset:
                    raise ValueError("file extent outside image")
                full = prefix + name
                if full.casefold() in names:
                    raise ValueError("duplicate disc path")
                names.add(full.casefold())
                row = dict(name=full, offset=offset, size=length, directory=bool(flags & 0x10))
                output.append(row)
                if len(output) > 100000:
                    raise ValueError("directory entry budget exceeded")
                if row["directory"]:
                    walk(start, length, full + "/", depth + 1)
        walk(self.root_sector, self.root_size, "", 0)
        return sorted(output, key=lambda row: row["name"].casefold())

    def executable(self, entry):
        if entry["size"] < 24 or entry["size"] > 256 * 1024 * 1024:
            raise ValueError("unsupported executable size")
        # Only metadata prefix in memory; stream the executable hash.
        prefix = self.read(entry["offset"], min(entry["size"], 1024 * 1024))
        if prefix[:4] != b"XEX2":
            raise ValueError("expected XEX2 executable")
        count = struct.unpack_from(">I", prefix, 20)[0]
        if count > (len(prefix) - 24) // 8:
            raise ValueError("invalid XEX optional table")
        digest = hashlib.sha256()
        for at in range(0, entry["size"], 1024 * 1024):
            digest.update(self.read(entry["offset"] + at, min(1024 * 1024, entry["size"] - at)))
        result = dict(name=entry["name"], size=entry["size"], sha256=digest.hexdigest(), format="XEX2")
        for i in range(count):
            key, value = struct.unpack_from(">II", prefix, 24 + i * 8)
            if key == 0x40006:
                if value < 24 + count * 8 or value + 24 > len(prefix):
                    raise ValueError("execution identity outside bounded metadata prefix")
                media, version, base, title = struct.unpack_from(">IIII", prefix, value)
                result["execution"] = dict(media_id=f"{media:08x}", version_raw=f"{version:08x}", base_version_raw=f"{base:08x}",
                                           title_id=f"{title:08x}", platform=prefix[value + 16], executable_type=prefix[value + 17],
                                           disc_number=prefix[value + 18], disc_count=prefix[value + 19])
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extract-executables", type=Path, help="optional private directory; only root default*.xex; never overwrites")
    args = parser.parse_args()
    try:
        if args.iso.is_symlink() or not args.iso.is_file():
            raise ValueError("expected regular non-symlink ISO")
        with args.iso.open("rb") as stream:
            disc = Disc(stream, args.iso.stat().st_size)
            entries = disc.entries()
            binaries = [row for row in entries if not row["directory"] and row["name"].casefold() in ("default.xex", "default_mp.xex")]
            if not binaries:
                raise ValueError("no root default.xex/default_mp.xex found")
            report = dict(schema_version=1, supported_build=False, partition_offset=disc.base, entries=len(entries),
                          executables=[disc.executable(row) for row in binaries],
                          file_names=[row["name"] for row in entries if not row["directory"]])
            # Preflight output before optionally extracting private inputs.
            if args.output.exists() or args.output.is_symlink():
                raise ValueError("report already exists; choose a new name")
            if args.extract_executables:
                args.extract_executables.mkdir(parents=True, exist_ok=True)
                for row in binaries:
                    dest = args.extract_executables / row["name"]
                    with dest.open("xb") as out:
                        for at in range(0, row["size"], 1024 * 1024):
                            out.write(disc.read(row["offset"] + at, min(1024 * 1024, row["size"] - at)))
            with args.output.open("x", encoding="utf-8") as output:
                json.dump(report, output, indent=2, sort_keys=True)
                output.write("\n")
            print(f"Inspected {len(entries)} entries and {len(binaries)} executable(s); no title execution")
    except (OSError, ValueError) as e:
        parser.exit(1, f"disc inspection failed: {e}\n")


if __name__ == "__main__":
    main()
