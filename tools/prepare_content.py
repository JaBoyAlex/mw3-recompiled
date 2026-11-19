#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Prepare exact owned disc content into a new private directory; never execute it."""
import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
import unicodedata

from disc import Disc
from verify_inputs import DEFAULT, validate_manifest

ROOT = Path(__file__).resolve().parents[1]
CHUNK = 1024 * 1024
MAX_ENTRIES = 100000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def component(name):
    """Conservative common Windows/POSIX namespace, without renaming content."""
    require(isinstance(name, str) and 0 < len(name) <= 255, "invalid name length")
    require(name not in (".", "..") and not name.endswith((".", " ")), "unsafe dot/space name")
    require(not any(c in '<>:"/\\|?*~' or unicodedata.category(c).startswith("C") for c in name),
            "unsafe name character or unverified DOS short alias")
    key = unicodedata.normalize("NFKC", name).casefold()
    require(not key.endswith((".", " ")), "unsafe normalized name")
    base = key.split(".")[0].rstrip(" ")
    require(base not in {"con", "prn", "aux", "nul", "conin$", "conout$"}
            and re.fullmatch(r"(?:com|lpt)[1-9]", base) is None, "Windows reserved name")
    return key


def absolute(path):
    path = Path(path)
    require(".." not in path.parts, "parent traversal in operator path")
    path = path.absolute()
    if os.name == "nt":
        require(re.fullmatch(r"[A-Za-z]:\\", path.anchor) is not None,
                "use a local drive path, not a device/UNC namespace")
    require(path.name != "", "expected a named file/directory")
    for name in path.parts[1:]:
        component(name)
    return path


class Directory:
    """Handle-relative, no-follow opens. Windows uses documented native file APIs.

    Files are exclusively created, never opened for replacement. Every parent
    is opened separately and checked; a symlink/junction cannot redirect a
    later pathname open. No ancestor is created implicitly.
    """
    def __init__(self, handle):
        self.handle = handle

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()

    def close(self):
        if self.handle is not None:
            if os.name == "nt":
                _win().CloseHandle(self.handle)
            else:
                os.close(self.handle)
            self.handle = None

    @classmethod
    def anchor(cls, path):
        if os.name == "nt":
            handle = _nt_open(None, "\\??\\" + path.anchor, directory=True, root=True)
        else:
            handle = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        return cls(handle)

    def child(self, name, create=False):
        component(name)
        if os.name == "nt":
            return Directory(_nt_open(self.handle, name, directory=True, create=create))
        if create:
            os.mkdir(name, mode=0o700, dir_fd=self.handle)
        return Directory(os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.handle))

    def file(self, name, create=False):
        component(name)
        if os.name == "nt":
            import msvcrt
            handle = _nt_open(self.handle, name, directory=False, create=create)
            try:
                fd = msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_RDWR if create else os.O_RDONLY))
            except BaseException:
                _win().CloseHandle(handle)
                raise
        else:
            # A named pipe must be rejected by fstat without waiting for a writer.
            flags = os.O_NOFOLLOW | (os.O_RDWR | os.O_CREAT | os.O_EXCL if create else os.O_RDONLY | os.O_NONBLOCK)
            fd = os.open(name, flags, 0o600, dir_fd=self.handle)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "expected regular unlinked file")
            return os.fdopen(fd, "w+b" if create else "rb")
        except BaseException:
            os.close(fd)
            raise

    def exists(self, name):
        component(name)
        try:
            if os.name == "nt":
                handle = _nt_open(self.handle, name, directory=None)
                _win().CloseHandle(handle)
            else:
                os.stat(name, dir_fd=self.handle, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False

    def names(self):
        if os.name != "nt":
            return os.listdir(self.handle)
        import struct
        api = _win()
        c, w, _, _, IoStatus, _ = api.types
        names, restart = [], True
        while True:
            buffer, ios = c.create_string_buffer(65536), IoStatus()
            status = api.query(self.handle, None, None, None, c.byref(ios), buffer,
                               len(buffer), 12, False, None, restart)
            restart = False
            if status & 0xffffffff == 0x80000006:  # STATUS_NO_MORE_FILES
                return names
            if status < 0:
                raise c.WinError(api.error(status))
            require(0 < ios.Information <= len(buffer), "invalid directory query size")
            at = 0
            while True:
                require(at + 12 <= ios.Information, "truncated directory query")
                following, _, length = struct.unpack_from("<III", buffer, at)
                require(length % 2 == 0 and at + 12 + length <= ios.Information, "invalid directory query name")
                name = buffer.raw[at + 12:at + 12 + length].decode("utf-16-le")
                if name not in (".", ".."):
                    names.append(name)
                if not following:
                    break
                require(following >= 12 + length and at + following < ios.Information,
                        "invalid directory query offset")
                at += following

    @contextmanager
    def descend(self, parts):
        with ExitStack() as stack:
            current = self
            for name in parts:
                current = stack.enter_context(current.child(name))
            yield current


_WINDOWS = None


def _win():
    global _WINDOWS
    if _WINDOWS is None:
        import ctypes as c
        from ctypes import wintypes as w
        # Interface layouts from Microsoft NtCreateFile/OBJECT_ATTRIBUTES and
        # IO_STATUS_BLOCK documentation; no SDK headers or implementation copied.
        class UnicodeString(c.Structure):
            _fields_ = [("Length", w.USHORT), ("MaximumLength", w.USHORT), ("Buffer", w.LPWSTR)]
        class ObjectAttributes(c.Structure):
            _fields_ = [("Length", w.ULONG), ("RootDirectory", w.HANDLE),
                        ("ObjectName", c.POINTER(UnicodeString)), ("Attributes", w.ULONG),
                        ("SecurityDescriptor", c.c_void_p), ("SecurityQualityOfService", c.c_void_p)]
        class IoStatus(c.Structure):
            _fields_ = [("StatusOrPointer", c.c_void_p), ("Information", c.c_size_t)]
        class AttributeTag(c.Structure):
            _fields_ = [("Attributes", w.DWORD), ("Tag", w.DWORD)]
        class Windows:
            pass
        api = Windows()
        api.types = c, w, UnicodeString, ObjectAttributes, IoStatus, AttributeTag
        api.kernel = c.WinDLL("kernel32", use_last_error=True)
        api.native = c.WinDLL("ntdll")
        api.CloseHandle = api.kernel.CloseHandle
        api.CloseHandle.argtypes, api.CloseHandle.restype = [w.HANDLE], w.BOOL
        api.info = api.kernel.GetFileInformationByHandleEx
        api.info.argtypes, api.info.restype = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL
        api.open = api.native.NtCreateFile
        api.open.argtypes = [c.POINTER(w.HANDLE), w.ULONG, c.POINTER(ObjectAttributes),
                            c.POINTER(IoStatus), c.c_void_p, w.ULONG, w.ULONG, w.ULONG,
                            w.ULONG, c.c_void_p, w.ULONG]
        api.open.restype = w.LONG
        api.query = api.native.NtQueryDirectoryFile
        api.query.argtypes = [w.HANDLE, w.HANDLE, c.c_void_p, c.c_void_p, c.POINTER(IoStatus),
                             c.c_void_p, w.ULONG, c.c_int, c.c_ubyte, c.c_void_p, c.c_ubyte]
        api.query.restype = w.LONG
        api.error = api.native.RtlNtStatusToDosError
        api.error.argtypes, api.error.restype = [w.LONG], w.ULONG
        _WINDOWS = api
    return _WINDOWS


def _nt_open(parent, name, *, directory, create=False, root=False):
    api = _win()
    c, w, UnicodeString, ObjectAttributes, IoStatus, AttributeTag = api.types
    buffer = c.create_unicode_buffer(name)
    length = len(name.encode("utf-16-le"))
    text = UnicodeString(length, length + 2, c.cast(buffer, w.LPWSTR))
    # OBJ_DONT_REPARSE for every handle-relative lookup. The trusted local
    # drive anchor alone must resolve the OS's DOS drive-to-volume mapping.
    attrs = ObjectAttributes(c.sizeof(ObjectAttributes), parent, c.pointer(text),
                             0x40 | (0 if root else 0x1000), None, None)
    handle, ios = w.HANDLE(), IoStatus()
    access = 0x1000A1 if directory is True else 0x100080 if directory is None else (
        0xC0100080 if create else 0x80100080)
    options = 0x200020 | (1 if directory is True else 0x40 if directory is False else 0)
    status = api.open(c.byref(handle), access, c.byref(attrs), c.byref(ios), None,
                      0x80, 1 if directory is not True else 3, 2 if create else 1, options, None, 0)
    if status < 0:
        raise c.WinError(api.error(status))
    try:
        info = AttributeTag()
        if not api.info(handle, 9, c.byref(info), c.sizeof(info)):
            raise c.WinError(c.get_last_error())
        require(not info.Attributes & 0x400, "reparse redirection is refused")
        if directory is not None:
            require(bool(info.Attributes & 0x10) == directory, "wrong filesystem object type")
        return handle.value
    except BaseException:
        api.CloseHandle(handle)
        raise


@contextmanager
def parent_of(path):
    with Directory.anchor(path) as root:
        with root.descend(path.parts[1:-1]) as parent:
            yield parent


def signature(stream):
    value = os.fstat(stream.fileno())
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def hash_range(stream, offset, size):
    stream.seek(offset)
    result = hashlib.sha256()
    for at in range(0, size, CHUNK):
        block = stream.read(min(CHUNK, size - at))
        require(len(block) == min(CHUNK, size - at), "truncated streamed input")
        result.update(block)
    return result.hexdigest()


def preflight(rows, image_size, max_entries, max_bytes):
    require(0 < max_entries <= MAX_ENTRIES and 0 <= max_bytes, "invalid budgets")
    require(len(rows) <= max_entries, "entry budget exceeded")
    names, total = {}, 0
    for row in rows:
        require(isinstance(row["name"], str), "invalid entry name")
        parts = row["name"].split("/")
        key = tuple(component(part) for part in parts)
        require(key not in names, "normalized/case path collision")
        names[key] = row
        require(type(row["directory"]) is bool, "invalid directory flag")
        require(all(type(row[k]) is int and 0 <= row[k] <= image_size for k in ("offset", "size"))
                and row["size"] <= image_size - row["offset"], "entry extent outside image")
        if not row["directory"]:
            total += row["size"]
            require(total <= max_bytes, "content byte budget exceeded")
    for key in names:
        for depth in range(1, len(key)):
            require(key[:depth] in names and names[key[:depth]]["directory"], "missing or non-directory parent")
    return total


def write_json(directory, name, value):
    with directory.file(name, create=True) as stream:
        stream.write((json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())


def copy_file(source, row, output):
    digest = hashlib.sha256()
    with output.file(row["name"].split("/")[-1], create=True) as dest:
        source.seek(row["offset"])
        for at in range(0, row["size"], CHUNK):
            block = source.read(min(CHUNK, row["size"] - at))
            require(len(block) == min(CHUNK, row["size"] - at), "truncated content")
            require(dest.write(block) == len(block), "short output write")
            digest.update(block)
        dest.flush()
        os.fsync(dest.fileno())
    return digest.hexdigest()


def verify_names(content, rows):
    children = {(): set()}
    for row in rows:
        parts = tuple(row["name"].split("/"))
        children.setdefault(parts[:-1], set()).add(parts[-1])
        if row["directory"]:
            children.setdefault(parts, set())
    for parts, expected in children.items():
        with content.descend(parts) as directory:
            require(set(directory.names()) == expected, "unexpected or missing prepared entry")


def prepare(iso, output, *, manifest=None, max_entries=MAX_ENTRIES, max_bytes=None):
    """Tests may supply an original synthetic identity; CLI always uses DEFAULT."""
    iso, output = absolute(iso), absolute(output)
    manifest = json.loads(DEFAULT.read_text(encoding="utf-8")) if manifest is None else manifest
    validate_manifest(manifest)
    identity = manifest["iso"]
    require(type(identity["size"]) is int and identity["size"] > 0
            and re.fullmatch(r"[a-f0-9]{64}", identity["sha256"]) is not None, "invalid ISO identity")
    max_bytes = identity["size"] if max_bytes is None else max_bytes
    require(output != iso and output not in iso.parents, "output overlaps source")
    require(not output.is_relative_to(ROOT) or ".local" in output.relative_to(ROOT).parts,
            "private output must be outside the worktree or under .local")
    for ancestor in output.parents:
        if (ancestor / ".git").exists():
            require(".local" in output.relative_to(ancestor).parts, "output inside non-private Git tree")
    with parent_of(iso) as source_parent, parent_of(output) as output_parent:
        require(not output_parent.exists(output.name), "destination already exists")
        with source_parent.file(iso.name) as source:
            before = signature(source)
            require(before[2] == identity["size"], "ISO size mismatch")
            print("Verifying source ISO and executable pair", flush=True)
            require(hash_range(source, 0, before[2]) == identity["sha256"], "ISO hash mismatch")
            disc = Disc(source, before[2])
            rows = disc.entries()
            total = preflight(rows, before[2], max_entries, max_bytes)
            for expected in manifest["executables"]:
                matches = [r for r in rows if r["name"] == expected["name"] and not r["directory"]]
                require(len(matches) == 1, "missing exact root executable")
                observed = disc.executable(matches[0])
                require(all(observed.get(k) == v for k, v in expected.items()), "executable identity mismatch")
            require(signature(source) == before, "source changed during preflight")
            tools = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in (Path(__file__), ROOT / "tools/disc.py", ROOT / "tools/verify_inputs.py")}
            binding = dict(manifest_id=manifest["id"], iso=identity,
                           manifest_sha256=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
                           tools=tools, python=sys.version, platform=platform.platform(),
                           chunk_bytes=CHUNK, max_entries=max_entries, max_bytes=max_bytes)
            with output_parent.child(output.name, create=True) as attempt:
                try:
                    write_json(attempt, "attempt.json", dict(schema_version=1, complete=False, binding=binding))
                    with attempt.child("content", create=True) as content:
                        directories = sorted((r for r in rows if r["directory"]),
                                             key=lambda r: (r["name"].count("/"), r["name"]))
                        for row in directories:
                            parts = row["name"].split("/")
                            with content.descend(parts[:-1]) as parent:
                                with parent.child(parts[-1], create=True):
                                    pass
                        print(f"Streaming {len(rows)} entries, {total} content bytes", flush=True)
                        copied = {}
                        for row in rows:
                            if not row["directory"]:
                                with content.descend(row["name"].split("/")[:-1]) as parent:
                                    copied[row["name"]] = copy_file(source, row, parent)
                        print("Reconciling every prepared file and unchanged source", flush=True)
                        verify_names(content, rows)
                        require(set(attempt.names()) == {"content", "attempt.json"}, "unexpected attempt entry")
                        files = []
                        for row in rows:
                            if row["directory"]:
                                continue
                            parts = row["name"].split("/")
                            expected_hash = copied[row["name"]]
                            with content.descend(parts[:-1]) as parent, parent.file(parts[-1]) as dest:
                                require(signature(dest)[2] == row["size"], "prepared size mismatch")
                                require(hash_range(dest, 0, row["size"]) == expected_hash, "prepared hash mismatch")
                            files.append(dict(name=row["name"], size=row["size"], offset=row["offset"], sha256=expected_hash))
                        require(signature(source) == before and hash_range(source, 0, before[2]) == identity["sha256"]
                                and signature(source) == before, "source changed during preparation")
                        report = dict(schema_version=1, complete=True, binding=binding,
                                      partition_offset=disc.base, entries=len(rows), total_bytes=total,
                                      directories=[r["name"] for r in directories], files=files,
                                      source_unchanged=True, game_executed=False, runtime_supported=False)
                        write_json(attempt, "manifest.json", report)
                        return report
                except BaseException as failure:
                    # Never remove a partial attempt or touch an existing destination.
                    try:
                        write_json(attempt, "failure.json", dict(complete=False, error=type(failure).__name__,
                                                                 message=str(failure)))
                    except OSError:
                        pass
                    raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("output", type=Path, help="fresh private directory; its parent must already exist")
    parser.add_argument("--max-entries", type=int, default=MAX_ENTRIES)
    parser.add_argument("--max-bytes", type=int)
    args = parser.parse_args()
    try:
        result = prepare(args.iso, args.output, max_entries=args.max_entries, max_bytes=args.max_bytes)
    except (OSError, ValueError, KeyError, TypeError) as failure:
        parser.exit(1, f"content preparation failed: {failure}\n")
    print(f"PASS: {len(result['files'])} files verified; private content only, no game execution")


if __name__ == "__main__":
    main()
