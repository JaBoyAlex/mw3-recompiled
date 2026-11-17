# SPDX-License-Identifier: GPL-3.0-only
"""Game-free negative checks for experiment source identity and private logs."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runtime_prepare", HERE / "prepare.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PreparationTests(unittest.TestCase):
    def make_repo(self, root):
        def git(*args):
            return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.STDOUT, text=True)
        git("init")
        (root / "original.txt").write_text("original fixture\n")
        git("add", "original.txt")
        git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "original fixture")
        return dict(name="original-fixture", commit=git("rev-parse", "HEAD").strip())

    def test_source_pin_and_tracked_modification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); entry = self.make_repo(root)
            self.assertEqual(prepare.verify_source(root, entry)["commit"], entry["commit"])
            with self.assertRaisesRegex(ValueError, "identity"):
                prepare.verify_source(root, dict(entry, commit="0"*40))
            (root / "original.txt").write_text("changed fixture\n")
            with self.assertRaisesRegex(ValueError, "cleanliness"):
                prepare.verify_source(root, entry)

    def test_untracked_source_is_not_silently_built(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); entry = self.make_repo(root)
            (root / "untracked.cpp").write_text("// original fixture\n")
            with self.assertRaisesRegex(ValueError, "cleanliness"):
                prepare.verify_source(root, entry)

    def test_private_log_keeps_failure_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "original.log"
            with self.assertRaisesRegex(ValueError, "original.log"):
                prepare.run([sys.executable, "-c", "print('original failure fixture'); raise SystemExit(3)"], log=log)
            self.assertIn("original failure fixture", log.read_text())

    def test_invalid_worker_count_does_not_fetch_or_build(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, str(HERE / "prepare.py"), "--root", temp, "--jobs", "0"], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(Path(temp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
