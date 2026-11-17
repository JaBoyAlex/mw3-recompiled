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
sys.path.insert(0, str(HERE))
mw2_spec = importlib.util.spec_from_file_location("runtime_mw2_tools", HERE / "mw2_tools.py")
mw2_tools = importlib.util.module_from_spec(mw2_spec)
mw2_spec.loader.exec_module(mw2_tools)


class PreparationTests(unittest.TestCase):
    def make_repo(self, root):
        def git(*args):
            return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.STDOUT, text=True)
        git("init")
        git("config", "core.autocrlf", "false")
        (root / "original.txt").write_text("original fixture\n", newline="\n")
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

    def test_reviewed_derivative_handles_added_files_and_preserves_other_edits(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp); root = parent / "source"; root.mkdir()
            pin = self.make_repo(root)
            patch = parent / "original.patch"
            patch.write_text("diff --git a/original.txt b/original.txt\n--- a/original.txt\n+++ b/original.txt\n@@ -1 +1 @@\n-original fixture\n+updated original fixture\n"
                             "diff --git a/added.cpp b/added.cpp\nnew file mode 100644\n--- /dev/null\n+++ b/added.cpp\n@@ -0,0 +1 @@\n+// original added fixture\n", newline="\n")
            pin["patch_sha256"] = prepare.sha(patch)
            first = mw2_tools.derive(root, patch, pin)
            self.assertEqual(mw2_tools.derive(root, patch, pin)["derived_tree"], first["derived_tree"])
            self.assertEqual((root / "added.cpp").read_text(), "// original added fixture\n")
            (root / "added.cpp").write_text("// contributor edit\n")
            with self.assertRaisesRegex(ValueError, "edits preserved"):
                mw2_tools.derive(root, patch, pin)
            self.assertEqual((root / "added.cpp").read_text(), "// contributor edit\n")

    def test_wrong_patch_hash_is_refused_before_mutating_source(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp); root = parent / "source"; root.mkdir()
            pin = self.make_repo(root); pin["patch_sha256"] = "0"*64
            patch = parent / "original.patch"; patch.write_text("original invalid patch fixture\n")
            with self.assertRaisesRegex(ValueError, "identity"):
                mw2_tools.derive(root, patch, pin)
            self.assertEqual((root / "original.txt").read_text(), "original fixture\n")


if __name__ == "__main__":
    unittest.main()
