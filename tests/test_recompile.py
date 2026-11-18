# SPDX-License-Identifier: GPL-3.0-only
"""Game-free corruption/concurrency/privacy guards for private generation."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import recompile as r


class GenerationGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recipe = json.loads(r.RECIPE.read_text())

    def symlink(self, source, destination, *, directory=False):
        try:
            destination.symlink_to(source, target_is_directory=directory)
        except OSError:
            self.skipTest("symlink privilege unavailable")

    def test_recipe_rejects_unknown_targets_and_silent_fast_math(self):
        r.validate_recipe(self.recipe)
        for key, value in (("manual_code_targets", [0x82000000]), ("register_locals", True),
                           ("forward_stack_stores", True), ("max_resolve_iterations", True),
                           ("include", "unreviewed.toml"), ("schema_version", True)):
            changed = copy.deepcopy(self.recipe)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                r.validate_recipe(changed)
        for key in r.VECTOR_KEYS:
            changed = copy.deepcopy(self.recipe)
            changed["vector_math"][key] = "fast"
            with self.subTest(key=key), self.assertRaises(ValueError):
                r.validate_recipe(changed)

    def test_all_identity_inputs_affect_key_without_dictionary_order_noise(self):
        identity = dict(title="a", toolchain="b", recipe="c", patch="d", driver="e")
        self.assertEqual(r.digest(identity), r.digest(dict(reversed(list(identity.items())))))
        for key in identity:
            self.assertNotEqual(r.digest(identity), r.digest(dict(identity, **{key: "changed"})))

    def test_lock_refuses_another_writer_and_preserves_its_ownership(self):
        with r.writer_lock(self.root, "key"):
            stamp = (self.root / "key.lock").read_bytes()
            with self.assertRaises(FileExistsError):
                with r.writer_lock(self.root, "key"):
                    self.fail("second writer admitted")
            self.assertEqual((self.root / "key.lock").read_bytes(), stamp)
        self.assertFalse((self.root / "key.lock").exists())
        with self.assertRaisesRegex(RuntimeError, "fixture"):
            with r.writer_lock(self.root, "key"):
                raise RuntimeError("fixture")
        self.assertFalse((self.root / "key.lock").exists())

    def cache_fixture(self):
        directory = self.root / "cache"
        payload = directory / "payload"
        payload.mkdir(parents=True)
        (payload / "original.cpp").write_text("// Original synthetic fixture, no game content.\n")
        (payload / "log.txt").write_text("synthetic observation\n")
        files = r.snapshot(payload)
        value = dict(schema_version=1, key="key", inputs={"title": "fixture"}, files=files,
                     code_manifest={n: v for n, v in files.items() if n.endswith(".cpp")},
                     guest_executed=False, runtime_supported=False, release_package=False)
        (directory / "manifest.json").write_text(json.dumps(value))
        return directory, value

    def test_cache_rehash_refuses_modified_missing_extra_and_wrong_identity(self):
        directory, value = self.cache_fixture()
        self.assertEqual(r.read_cache(directory, "key", value["inputs"]), value)
        for field, changed in (("guest_executed", True), ("schema_version", True), ("unknown", "value")):
            (directory / "manifest.json").write_text(json.dumps(dict(value, **{field: changed})))
            with self.subTest(field=field), self.assertRaises(ValueError):
                r.read_cache(directory, "key", value["inputs"])
        (directory / "manifest.json").write_text(json.dumps(value))
        for key, inputs in (("wrong", value["inputs"]), ("key", {"title": "wrong"})):
            with self.assertRaises(ValueError):
                r.read_cache(directory, key, inputs)
        source = directory / "payload/original.cpp"
        original = source.read_bytes()
        source.write_bytes(b"changed")
        with self.assertRaises(ValueError):r.read_cache(directory, "key", value["inputs"])
        source.unlink()
        with self.assertRaises(ValueError):r.read_cache(directory, "key", value["inputs"])
        source.write_bytes(original)
        extra = directory / "payload/extra.cpp"
        extra.write_text("original extra fixture")
        with self.assertRaises(ValueError):r.read_cache(directory, "key", value["inputs"])
        extra.unlink()
        (directory / "unexpected").write_text("x")
        with self.assertRaises(ValueError):r.read_cache(directory, "key", value["inputs"])

    def test_output_must_be_ignored_and_never_overlap_owned_inputs(self):
        repo = self.root / "repo"
        subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
        (repo / ".gitignore").write_text(".local/\n")
        owned = self.root / "owned"
        owned.mkdir()
        self.assertEqual(r.private_cache(repo / ".local/generated", owned), repo / ".local/generated")
        for output in (repo / "public", owned / "cache", self.root):
            with self.subTest(output=output), self.assertRaises(ValueError):
                r.private_cache(output, owned)

    def test_redirected_cache_and_payload_are_refused(self):
        directory, value = self.cache_fixture()
        alias = self.root / "alias"
        self.symlink(directory, alias, directory=True)
        with self.assertRaises(ValueError):r.read_cache(alias, "key", value["inputs"])
        target = self.root / "target"
        target.mkdir()
        redirected = self.root / "redirected"
        redirected.mkdir()
        self.symlink(target, redirected / "payload", directory=True)
        with self.assertRaises(ValueError):r.snapshot(redirected / "payload")

    def test_sdk_links_must_resolve_to_files_inside_package(self):
        sdk = self.root / "sdk"
        sdk.mkdir()
        (sdk / "library").write_text("synthetic library fixture")
        self.symlink(sdk / "library", sdk / "alias")
        self.assertIn("link", r.snapshot(sdk, internal_links=True)["alias"])
        with self.assertRaises(ValueError):r.snapshot(sdk)
        outside = self.root / "outside"
        outside.write_text("fixture")
        self.symlink(outside, sdk / "escape")
        with self.assertRaises(ValueError):r.snapshot(sdk, internal_links=True)

    def test_wrong_owned_pair_refuses_before_toolchain_or_cache_write(self):
        owned = self.root / "owned"
        owned.mkdir()
        for name in ("default.xex", "default_mp.xex"):
            (owned / name).write_bytes(b"XEX2" + bytes(24))
        cache = self.root / "new-cache"
        arguments = ["recompile.py", "--owned", str(owned), "--cache", str(cache),
                     "--bakeoff-root", str(self.root / "missing"), "--sdk-report", str(self.root / "missing-report")]
        with patch.object(sys, "argv", arguments), patch.object(r.platform, "system", return_value="Linux"), \
             patch.object(r.platform, "machine", return_value="x86_64"), patch.object(r, "toolchain") as tool, \
             patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
            r.main()
        tool.assert_not_called()
        self.assertFalse(cache.exists())


if __name__ == "__main__":
    unittest.main()
