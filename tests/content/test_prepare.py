# SPDX-License-Identifier: GPL-3.0-only
"""Original XDVDFS fixtures; no game/SDK input, downloads, or guest execution."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import prepare_content as prep
from disc import MAGIC, SECTOR


def xex(tag):
    result = bytearray(128)
    result[:4] = b"XEX2"
    result[24:] = bytes([tag]) * 104
    return bytes(result)


PAIR = [("default.xex", xex(1)), ("default_mp.xex", xex(2))]


def image(extra=()):
    """Small source-owned directory tables, right-linked fixed-size nodes."""
    data = bytearray(40 * SECTOR)
    def allocate(value):
        sector = len(data) // SECTOR
        data.extend(value)
        data.extend(bytes((-len(data)) % SECTOR))
        return sector
    def table(entries):
        if not entries:
            return len(data) // SECTOR, 0
        body = bytearray(len(entries) * 288)
        sector = allocate(body)
        for i, (name, value) in enumerate(entries):
            directory = isinstance(value, list)
            start, length = table(value) if directory else (allocate(value), len(value))
            encoded = name.encode("latin-1")
            at = i * 288
            struct.pack_into("<HHIIBB", body, at, 0, (i + 1) * 72 if i + 1 < len(entries) else 0,
                             start, length, 0x10 if directory else 0, len(encoded))
            body[at + 14:at + 14 + len(encoded)] = encoded
        data[sector * SECTOR:sector * SECTOR + len(body)] = body
        return sector, len(body)
    sector, length = table(PAIR + list(extra))
    at = 32 * SECTOR
    data[at:at + 20] = data[at + SECTOR - 20:at + SECTOR] = MAGIC
    struct.pack_into("<II", data, at + 20, sector, length)
    return data


def identity(data):
    return dict(schema_version=1, id="original-synthetic-content", status="identified-not-runtime-supported",
                iso=dict(size=len(data), sha256=hashlib.sha256(data).hexdigest()),
                executables=[dict(name=name, size=len(value), format="XEX2",
                                  sha256=hashlib.sha256(value).hexdigest()) for name, value in PAIR])


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.iso, self.output = self.root / "owned.iso", self.root / "prepared"

    def run_prepare(self, data=None, **kwargs):
        if data is not None:
            self.iso.write_bytes(data)
        else:
            data = self.iso.read_bytes()
        with redirect_stdout(io.StringIO()):
            return prep.prepare(self.iso, self.output, manifest=identity(data), **kwargs)

    def rejected_before_output(self, data, pattern, **kwargs):
        with self.assertRaisesRegex((ValueError, OSError), pattern):
            self.run_prepare(data, **kwargs)
        self.assertFalse(self.output.exists())

    def test_nested_empty_content_complete_hashes_and_source_preservation(self):
        data = image([("folder", [("zero", b""), ("payload.bin", b"original-data")]), ("empty", [])])
        report = self.run_prepare(data)
        self.assertTrue(report["complete"] and report["source_unchanged"])
        self.assertFalse(report["game_executed"] or report["runtime_supported"])
        self.assertEqual(self.iso.read_bytes(), data)
        self.assertEqual(report["entries"], 6)
        self.assertEqual(len(report["files"]), 4)
        for row in report["files"]:
            output = self.output / "content" / row["name"]
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), row["sha256"])
            self.assertEqual(output.read_bytes(), data[row["offset"]:row["offset"] + row["size"]])
        self.assertEqual(report["total_bytes"], sum(r["size"] for r in report["files"]))
        self.assertTrue((self.output / "content/empty").is_dir())
        self.assertFalse((self.output / "profiles").exists())
        self.assertEqual(json.loads((self.output / "manifest.json").read_text()), report)

    def test_operator_path_tilde_is_allowed_but_disc_alias_is_not(self):
        # Hosted Windows runners can expose their temp parent as RUNNER~1.
        parent = self.root / "operator~1"
        parent.mkdir()
        self.iso, self.output = parent / "owned~1.iso", parent / "prepared~1"
        report = self.run_prepare(image())
        self.assertTrue(report["complete"])
        self.output = parent / "another"
        self.rejected_before_output(image([("disc~1", b"x")]), "unsafe")

    def test_streamed_payload_reads_are_chunk_bounded(self):
        largest = []
        real = prep.hash_range
        def bounded(stream, offset, size):
            original = stream.read
            def read(amount=-1):
                largest.append(amount)
                self.assertGreaterEqual(amount, 0)
                self.assertLessEqual(amount, prep.CHUNK)
                return original(amount)
            with patch.object(stream, "read", read):
                return real(stream, offset, size)
        with patch.object(prep, "hash_range", bounded):
            self.run_prepare(image([("large", b"\x5a" * (prep.CHUNK * 2 + 17))]))
        self.assertIn(prep.CHUNK, largest)

    def test_wrong_iso_or_executable_identity_makes_no_output(self):
        data = image()
        self.iso.write_bytes(data)
        manifest = identity(data)
        for target in (manifest["iso"], *manifest["executables"]):
            old = target["sha256"]
            target["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "ISO hash|executable identity"), redirect_stdout(io.StringIO()):
                prep.prepare(self.iso, self.output, manifest=manifest)
            self.assertFalse(self.output.exists())
            target["sha256"] = old

    def test_entry_and_byte_budgets_reject_without_writes(self):
        data = image([("a", b"content")])
        self.rejected_before_output(data, "entry budget", max_entries=2)
        self.rejected_before_output(data, "byte budget", max_bytes=255)
        self.rejected_before_output(data, "invalid budgets", max_entries=0)

    def test_windows_names_traversal_and_normalization_collisions(self):
        for name in ("..", "../x", "x\\y", "CON.txt", "aux", "com\xb2.log", "LPT9", "a.", "a ",
                     "x:y", "bad?name", "bad|name", "a\x00b", "bad~1", "\x85"):
            with self.subTest(name=name):
                self.rejected_before_output(image([(name, b"x")]), "unsafe|reserved")
        self.rejected_before_output(image([("a b", b"x"), ("a\xa0b", b"y")]), "collision")
        self.rejected_before_output(image([("Case", b"x"), ("case", b"y")]), "duplicate|collision")

    def test_invalid_extents_cycles_and_directory_budget(self):
        data = image()
        sector = struct.unpack_from("<I", data, 32 * SECTOR + 20)[0]
        struct.pack_into("<I", data, sector * SECTOR + 4, 0xffffffff)
        self.rejected_before_output(data, "outside image")
        data = image()
        struct.pack_into("<H", data, sector * SECTOR + 288 + 2, 72)
        self.rejected_before_output(data, "cyclic")
        data = image([("cycle", [])])
        length = struct.unpack_from("<I", data, 32 * SECTOR + 24)[0]
        struct.pack_into("<II", data, sector * SECTOR + 576 + 4, sector, length)
        self.rejected_before_output(data, "cyclic")
        data = image()
        struct.pack_into("<I", data, 32 * SECTOR + 24, 0xffffffff)
        self.rejected_before_output(data, "budget")

    def test_missing_case_changed_and_swapped_executables(self):
        data = image()
        sector = struct.unpack_from("<I", data, 32 * SECTOR + 20)[0]
        data[sector * SECTOR + 14:sector * SECTOR + 25] = b"DEFAULT.XEX"
        self.rejected_before_output(data, "exact root executable")
        data = image()
        first = struct.unpack_from("<II", data, sector * SECTOR + 4)
        second = struct.unpack_from("<II", data, sector * SECTOR + 288 + 4)
        struct.pack_into("<II", data, sector * SECTOR + 4, *second)
        struct.pack_into("<II", data, sector * SECTOR + 288 + 4, *first)
        self.rejected_before_output(data, "executable identity")

    def test_deep_directory_chain_rejected_before_output(self):
        value = [("leaf", b"x")]
        for i in range(34):
            value = [(f"depth{i}", value)]
        self.rejected_before_output(image(value), "deep")

    def test_preexisting_file_or_directory_unchanged(self):
        self.iso.write_bytes(image())
        self.output.write_bytes(b"sentinel")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_prepare()
        self.assertEqual(self.output.read_bytes(), b"sentinel")
        self.output.unlink()
        self.output.mkdir()
        sentinel = self.output / "keep"
        sentinel.write_bytes(b"private-save")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_prepare()
        self.assertEqual(list(self.output.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"private-save")

    def test_operator_paths_overlap_missing_parent_and_public_tree_refused(self):
        data = image()
        self.iso.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "overlaps"):
            prep.prepare(self.iso, self.iso, manifest=identity(data))
        with self.assertRaisesRegex(ValueError, "parent traversal"):
            prep.prepare(self.iso, self.root / "missing/../prepared", manifest=identity(data))
        self.output = self.root / "missing/prepared"
        self.rejected_before_output(data, ".")
        with self.assertRaisesRegex(ValueError, "private"):
            prep.prepare(self.iso, ROOT / "must-not-create", manifest=identity(data))

    def test_failed_attempt_is_retained_and_not_reused(self):
        original = prep.copy_file
        def fail(source, row, output):
            original(source, row, output)
            raise RuntimeError("deliberate interrupted copy")
        with patch.object(prep, "copy_file", fail), self.assertRaisesRegex(RuntimeError, "deliberate"):
            self.run_prepare(image())
        self.assertTrue((self.output / "attempt.json").is_file())
        self.assertTrue((self.output / "failure.json").is_file())
        self.assertFalse((self.output / "manifest.json").exists())
        first = (self.output / "content/default.xex").read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_prepare()
        self.assertEqual((self.output / "content/default.xex").read_bytes(), first)

    def test_wrong_copy_result_and_extra_entry_cannot_publish_manifest(self):
        real = prep.copy_file
        def mutate(source, row, output):
            real(source, row, output)
            return "0" * 64
        with patch.object(prep, "copy_file", mutate), self.assertRaisesRegex(ValueError, "prepared hash"):
            self.run_prepare(image())
        self.assertFalse((self.output / "manifest.json").exists())
        self.output = self.root / "extra-attempt"
        def extra(source, row, output):
            result = real(source, row, output)
            if row["name"] == "default.xex":
                with output.file("extra.bin", create=True) as stream:
                    stream.write(b"unexpected")
            return result
        with patch.object(prep, "copy_file", extra), self.assertRaisesRegex(ValueError, "unexpected"):
            self.run_prepare(image())
        self.assertFalse((self.output / "manifest.json").exists())

    def test_changed_source_during_copy_never_completes(self):
        real = prep.copy_file
        def change(source, row, output):
            result = real(source, row, output)
            # On Windows the held source handle denies another writable open.
            # On POSIX the final stat/hash guards detect the synthetic mutation.
            with self.iso.open("r+b") as other:
                other.seek(0)
                other.write(b"!")
            return result
        with patch.object(prep, "copy_file", change), self.assertRaises((ValueError, OSError)):
            self.run_prepare(image())
        self.assertFalse((self.output / "manifest.json").exists())

    def test_source_hardlink_refused(self):
        self.iso.write_bytes(image())
        try:
            os.link(self.iso, self.root / "alias.iso")
        except OSError as error:
            self.skipTest(f"hardlink unavailable: {error}")
        with self.assertRaisesRegex(ValueError, "unlinked"):
            self.run_prepare()
        self.assertFalse(self.output.exists())

    def make_link(self, link, target, junction=False):
        if junction and os.name == "nt":
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode:
                self.skipTest("native directory junction unavailable")
        else:
            try:
                link.symlink_to(target, target_is_directory=target.is_dir())
            except OSError:
                self.skipTest("host symlink privilege unavailable")

    def test_real_symlink_source_leaf_or_destination_ancestor_refused(self):
        data = image()
        self.iso.write_bytes(data)
        alias = self.root / "alias.iso"
        self.make_link(alias, self.iso)
        with self.assertRaises((ValueError, OSError)):
            prep.prepare(alias, self.output, manifest=identity(data))
        outside = self.root / "outside"
        outside.mkdir()
        link = self.root / "redirect"
        self.make_link(link, outside)
        self.output = link / "prepared"
        with self.assertRaises((ValueError, OSError)):
            self.run_prepare()
        self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_real_windows_junction_destination_and_source_refused(self):
        data = image()
        self.iso.write_bytes(data)
        outside = self.root / "outside"
        outside.mkdir()
        link = self.root / "junction"
        self.make_link(link, outside, junction=True)
        self.output = link / "prepared"
        with self.assertRaises((ValueError, OSError)):
            self.run_prepare()
        self.assertEqual(list(outside.iterdir()), [])
        (outside / "owned.iso").write_bytes(data)
        with self.assertRaises((ValueError, OSError)):
            prep.prepare(link / "owned.iso", self.root / "new-output", manifest=identity(data))

    def test_redirected_created_directory_cannot_write_outside(self):
        outside = self.root / "outside"
        outside.mkdir()
        sentinel = outside / "payload"
        sentinel.write_bytes(b"unchanged")
        real = prep.copy_file
        def redirect(source, row, output):
            if row["name"] == "folder/payload":
                folder = self.output / "content/folder"
                # Windows can deny rename while the directory handle is held.
                folder.rename(self.output / "content/held")
                self.make_link(folder, outside, junction=True)
            return real(source, row, output)
        with patch.object(prep, "copy_file", redirect), self.assertRaises((ValueError, OSError)):
            self.run_prepare(image([("folder", [("payload", b"new")])]))
        self.assertEqual(sentinel.read_bytes(), b"unchanged")
        self.assertEqual(list(outside.iterdir()), [sentinel])
        self.assertFalse((self.output / "manifest.json").exists())

    def test_cli_cannot_substitute_a_synthetic_identity(self):
        self.iso.write_bytes(image())
        result = subprocess.run([sys.executable, str(ROOT / "tools/prepare_content.py"),
                                 str(self.iso), str(self.output)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ISO size mismatch", result.stderr)
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO contract")
    def test_nonregular_source_is_rejected_without_blocking(self):
        os.mkfifo(self.iso, 0o600)
        result = subprocess.run([sys.executable, str(ROOT / "tools/prepare_content.py"),
                                 str(self.iso), str(self.output)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn("regular", result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
