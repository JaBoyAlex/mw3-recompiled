# SPDX-License-Identifier: GPL-3.0-only
"""Exercise output must never add files to a source, build or prepared SDK."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("memory_import_exercise", Path(__file__).with_name("exercise.py"))
exercise = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exercise)


class OutputIsolation(unittest.TestCase):
    def test_outputs_are_rejected_before_creation_when_they_overlap_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "cache"
            root.mkdir()
            receipt = root / "memory-imports-preparations/attempt/manifest.json"
            sdk = receipt.parent / "sdk"
            sdk.mkdir(parents=True)
            original = {p.relative_to(root) for p in root.rglob("*")}
            for requested in (root, root.parent, sdk, sdk / "runs", receipt.parent,
                              root / "sources/child", root / "build/child", root / "install/child",
                              root / "memory-preparations/child", root / "stop-preparations/child",
                              root / "xma-preparations/child", exercise.SOURCE / "runs",
                              exercise.ROOT / "tools/runs", exercise.ROOT / "config/runs"):
                with self.subTest(path=requested), self.assertRaises(ValueError):
                    exercise.output_directory(root, sdk, receipt, requested)
            self.assertEqual({p.relative_to(root) for p in root.rglob("*")}, original)
            requested = root / "isolated-contract-runs"
            output = exercise.output_directory(root, sdk, receipt, requested)
            self.assertEqual(output.parent, requested.resolve())
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
