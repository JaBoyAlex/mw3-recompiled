# SPDX-License-Identifier: GPL-3.0-only
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import verify_inputs


class InputTests(unittest.TestCase):
    def fixture(self, directory):
        rows = []
        for i, name in enumerate(sorted(verify_inputs.NAMES)):
            data = b"XEX2" + bytes([i]) * 28
            (directory / name).write_bytes(data)
            rows.append(dict(name=name, format="XEX2", size=len(data), sha256=hashlib.sha256(data).hexdigest()))
        return dict(schema_version=1, id="synthetic-pair", status="identified-not-runtime-supported", executables=rows)

    def test_matching_pair_is_not_runtime_or_ownership_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.fixture(Path(directory))
            result = verify_inputs.verify(directory, manifest)
            self.assertTrue(result["fingerprint_match"])
            self.assertFalse(result["runtime_supported"])
            self.assertFalse(result["ownership_verified"])
            self.assertNotIn(directory, str(result))

    def test_modified_mixed_wrong_platform_and_missing_input_fail(self):
        for change in ("modified", "mixed", "platform", "missing"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = self.fixture(root)
                path = root / "default.xex"
                if change == "modified":
                    data = path.read_bytes()
                    path.write_bytes(data[:-1] + b"x")
                elif change == "mixed":
                    path.write_bytes((root / "default_mp.xex").read_bytes())
                elif change == "platform":
                    path.write_bytes(b"\x7fELF" + bytes(28))
                else:
                    path.unlink()
                with self.assertRaises(ValueError):
                    verify_inputs.verify(root, manifest)

    def test_manifest_cannot_traverse_or_silently_omit_a_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.fixture(Path(directory))
            for replacement in ("../default.xex", "D:default.xex", "default_mp.xex"):
                bad = copy.deepcopy(manifest)
                bad["executables"][0]["name"] = replacement
                with self.assertRaises(ValueError):
                    verify_inputs.validate_manifest(bad)
            manifest["executables"].pop()
            with self.assertRaises(ValueError):
                verify_inputs.validate_manifest(manifest)

    def test_false_runtime_supported_manifest_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.fixture(Path(directory))
            manifest["status"] = "runtime-supported"
            with self.assertRaises(ValueError):
                verify_inputs.verify(directory, manifest)


if __name__ == "__main__":
    unittest.main()
