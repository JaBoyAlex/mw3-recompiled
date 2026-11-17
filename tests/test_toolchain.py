# SPDX-License-Identifier: GPL-3.0-only
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_toolchain", ROOT / "tools/prepare_toolchain.py")
toolchain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(toolchain)


class ToolchainTests(unittest.TestCase):
    def test_archive_traversal_and_platform_paths(self):
        for name in ("../escape", "/absolute", "a/../../escape", "C:escape", "a\\escape"):
            with self.assertRaises(ValueError):
                toolchain.safe_member(name)
        self.assertEqual(str(toolchain.safe_member("./bin/dxc")), "bin/dxc")

    def test_package_refuses_mutated_cache_and_extracted_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "dxc.tar.gz"
            with tarfile.open(archive, "w:gz") as package:
                content = b"original-synthetic-tool"
                entry = tarfile.TarInfo("bin/dxc")
                entry.size = len(content)
                entry.mode = 0o755
                package.addfile(entry, io.BytesIO(content))
            metadata = dict(url="https://github.com/microsoft/DirectXShaderCompiler/releases/download/synthetic/tool.tar.gz",
                            sha256=toolchain.sha256(archive))
            dest = toolchain.dxc_package(root, metadata)
            self.assertEqual((dest / "bin/dxc").read_bytes(), content)
            (dest / "bin/dxc").write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "extracted DXC file differs"):
                toolchain.dxc_package(root, metadata)
            archive.write_bytes(b"modified-archive")
            with self.assertRaisesRegex(ValueError, "cached DXC archive checksum"):
                toolchain.dxc_package(root, metadata)

    def test_archive_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "dxc.tar.gz"
            with tarfile.open(archive, "w:gz") as package:
                entry = tarfile.TarInfo("link")
                entry.type = tarfile.SYMTYPE
                entry.linkname = "../escape"
                package.addfile(entry)
            with self.assertRaisesRegex(ValueError, "non-regular"):
                toolchain.dxc_package(root, dict(url="pinned.tar.gz", sha256=toolchain.sha256(archive)))

    def test_source_change_is_refused(self):
        lock = dict(sources=[dict(name="cpu", commit="expected", submodules=[])])
        with patch.object(toolchain, "git", return_value="wrong"):
            with self.assertRaisesRegex(ValueError, "revision differs"):
                toolchain.verify_sources(Path("."), lock)
        with patch.object(toolchain, "git", side_effect=["expected", " M source.cpp"]):
            with self.assertRaisesRegex(ValueError, "dirty source"):
                toolchain.verify_sources(Path("."), lock)

    def test_synthetic_elf_has_correct_endian_code_and_distinct_sections(self):
        code = bytes.fromhex("7c6322144e800020")
        elf = toolchain.synthetic_elf(code)
        header = struct.unpack_from(">16sHHIIIIIHHHHHH", elf)
        self.assertEqual(header[0][:7], b"\x7fELF\x01\x02\x01")
        self.assertEqual(header[2], 20)  # EM_PPC
        table = header[6]
        text = struct.unpack_from(">IIIIIIIIII", elf, table + 40)
        names = struct.unpack_from(">IIIIIIIIII", elf, table + 80)
        self.assertNotEqual(text[3], names[3])
        self.assertEqual(elf[text[4]:text[4] + text[5]], code)

    def test_reproducibility_refuses_changed_inputs_or_outputs(self):
        report = dict(host="linux", compiler="pinned", lock_sha256="a", preparation_sha256={"script": "script-a"}, fixture_sha256={"fixture": "b"},
                      generated_sha256={"translated.cpp": "c"}, ppc_checks=547, mutation_rejected=True, tools={"tool": "binary-a"})
        other = copy.deepcopy(report)
        other["tools"]["tool"] = "binary-b"
        toolchain.compare_reports(report, other)
        for key in ("fixture_sha256", "preparation_sha256", "generated_sha256", "compiler", "lock_sha256", "ppc_checks", "mutation_rejected"):
            other = copy.deepcopy(report)
            other[key] = "changed"
            with self.assertRaisesRegex(ValueError, key):
                toolchain.compare_reports(report, other)


if __name__ == "__main__":
    unittest.main()
