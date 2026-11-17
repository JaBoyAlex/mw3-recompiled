# SPDX-License-Identifier: GPL-3.0-only
import io
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from disc import Disc, MAGIC, SECTOR


def disc_fixture(name=b"default.xex"):
    data = bytearray(44 * SECTOR)
    descriptor = 32 * SECTOR
    data[descriptor:descriptor + 20] = MAGIC
    data[descriptor + SECTOR - 20:descriptor + SECTOR] = MAGIC
    struct.pack_into("<II", data, descriptor + 20, 40, 128)
    struct.pack_into("<HHIIBB", data, 40 * SECTOR, 0, 0, 41, 128, 0, len(name))
    data[40 * SECTOR + 14:40 * SECTOR + 14 + len(name)] = name
    start = 41 * SECTOR
    data[start:start + 4] = b"XEX2"
    struct.pack_into(">I", data, start + 20, 1)
    struct.pack_into(">II", data, start + 24, 0x40006, 32)
    struct.pack_into(">IIII", data, start + 32, 0x12345678, 18, 18, 0x12340000)
    data[start + 50:start + 52] = bytes([1, 1])
    return data


class DiscTests(unittest.TestCase):
    def parse(self, data):
        return Disc(io.BytesIO(data), len(data))

    def test_synthetic_disc_identity(self):
        disc = self.parse(disc_fixture())
        entries = disc.entries()
        self.assertEqual(len(entries), 1)
        info = disc.executable(entries[0])
        self.assertEqual(info["execution"]["title_id"], "12340000")
        self.assertEqual(info["execution"]["version_raw"], "00000012")
        self.assertEqual(len(info["sha256"]), 64)

    def test_descriptor_and_extent_rejection(self):
        with self.assertRaisesRegex(ValueError, "descriptor"):
            self.parse(bytes(100))
        data = disc_fixture()
        struct.pack_into("<I", data, 40 * SECTOR + 4, 0xffffffff)
        with self.assertRaisesRegex(ValueError, "outside image"):
            self.parse(data).entries()

    def test_path_traversal_rejected(self):
        for name in (b"..", b"../default.xex", b"a\\b", b"D:evil", b"a\x00b"):
            with self.assertRaisesRegex(ValueError, "unsafe"):
                self.parse(disc_fixture(name)).entries()

    def test_node_cycle_rejected(self):
        data = disc_fixture()
        # Root points at node 8; node 8 points at itself.
        struct.pack_into("<H", data, 40 * SECTOR + 2, 8)
        struct.pack_into("<HHIIBB", data, 40 * SECTOR + 32, 0, 8, 41, 1, 0, 1)
        data[40 * SECTOR + 46] = ord("b")
        with self.assertRaisesRegex(ValueError, "cyclic"):
            self.parse(data).entries()

    def test_directory_budget_rejected_before_read(self):
        data = disc_fixture()
        struct.pack_into("<I", data, 32 * SECTOR + 24, 0xffffffff)
        with self.assertRaisesRegex(ValueError, "budget"):
            self.parse(data).entries()

    def test_xex_table_and_execution_identity_bounds(self):
        data = disc_fixture()
        struct.pack_into(">I", data, 41 * SECTOR + 20, 0xffffffff)
        disc = self.parse(data)
        with self.assertRaisesRegex(ValueError, "optional table"):
            disc.executable(disc.entries()[0])
        data = disc_fixture()
        struct.pack_into(">I", data, 41 * SECTOR + 28, 125)
        disc = self.parse(data)
        with self.assertRaisesRegex(ValueError, "outside bounded"):
            disc.executable(disc.entries()[0])


if __name__ == "__main__":
    unittest.main()
