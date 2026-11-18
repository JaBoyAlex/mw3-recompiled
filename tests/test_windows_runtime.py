# SPDX-License-Identifier: GPL-3.0-only
"""Game-free package selection/fingerprint guards; no compiler download in CI."""
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import prepare_windows_runtime as windows


class WindowsPreparationTests(unittest.TestCase):
    def reference_fixture(self,root):
        common=windows.common
        pins=json.loads((common.EXPERIMENT/"pins.json").read_text())
        base=pins["rexglue_memory_derivative"]
        identity=dict(manifest_id="original-inert-fixture")
        inputs=dict(title=identity,recipe=json.loads(common.RECIPE.read_text()),recipe_sha256=common.sha(common.RECIPE),
                    driver_sha256=common.sha(common.__file__),title_manifest_sha256=common.sha(common.DEFAULT),
                    helper_sha256={n:common.sha(common.EXPERIMENT/n) for n in ("prepare.py","mw2_tools.py","inspect_owned.py")},
                    toolchain=dict(source=dict(commit=base["commit"]),derivative=dict(base_commit=base["commit"],patch_sha256=base["patch_sha256"])))
        key=common.digest(inputs)
        source=root/key
        (source/"payload").mkdir(parents=True)
        (source/"payload/original.cpp").write_text("// Original inert fixture; never compiled or executed.\n")
        files=common.snapshot(source/"payload")
        receipt=dict(schema_version=1,key=key,inputs=inputs,files=files,code_manifest=files,
                     guest_executed=False,runtime_supported=False,release_package=False)
        (source/"manifest.json").write_text(json.dumps(receipt))
        return source,identity,common.sha(source/"manifest.json")

    def test_reference_staging_checks_receipt_identity_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source,identity,sha=self.reference_fixture(root/"source")
            target=root/"staged"/source.name
            for expected,who in (("0"*64,identity),(sha,dict(manifest_id="wrong"))):
                with self.assertRaises(ValueError):windows.stage_reference(source,target,who,expected)
                self.assertFalse(target.exists())
            with self.assertRaises(ValueError):windows.stage_reference(source,source/"nested",identity,sha)
            self.assertFalse((source/"nested").exists())
            staged,_=windows.stage_reference(source,target,identity,sha)
            self.assertEqual(staged,target.resolve())
            self.assertEqual(windows.common.sha(source/"manifest.json"),sha)
            self.assertEqual(windows.common.snapshot(source/"payload"),windows.common.snapshot(target/"payload"))

    def test_mutated_reference_or_staged_cache_is_never_repaired_silently(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source,identity,sha=self.reference_fixture(root/"source")
            target=root/"staged"/source.name
            original=(source/"payload/original.cpp").read_bytes()
            (source/"payload/original.cpp").write_bytes(b"corrupted original fixture")
            with self.assertRaises(ValueError):windows.stage_reference(source,target,identity,sha)
            self.assertFalse(target.exists())
            (source/"payload/original.cpp").write_bytes(original)
            windows.stage_reference(source,target,identity,sha)
            (target/"payload/original.cpp").write_bytes(b"corrupted staged fixture")
            with self.assertRaises(ValueError):windows.stage_reference(source,target,identity,sha)
            self.assertEqual((target/"payload/original.cpp").read_bytes(),b"corrupted staged fixture")

    def test_package_selection_refuses_escape_and_keeps_only_required_inputs(self):
        root="original-synthetic-compiler"
        for name in ("bin/clang++.exe","bin/runtime.dll","lib/clang/20/include/stddef.h","LICENSE.TXT"):
            self.assertEqual(windows.selected_member(root+"/"+name,root),name)
        for name in ("lib/unneeded-static.lib","bin/unneeded-tool.exe","share/doc/a"):
            self.assertIsNone(windows.selected_member(root+"/"+name,root))
        for name in ("/absolute",root+"/../escape",root+"/C:/escape",root+"/bin\\escape","wrong/bin/clang.exe"):
            with self.subTest(name=name),self.assertRaises(ValueError):windows.selected_member(name,root)

    def fixture(self,path,*,link=False):
        root="original-synthetic-compiler"
        with tarfile.open(path,"w:xz") as archive:
            for name in ("clang.exe","clang++.exe","clang-cl.exe","lld-link.exe","llvm-dlltool.exe","llvm-readobj.exe"):
                entry=tarfile.TarInfo(root+"/bin/"+name)
                if link and name=="clang++.exe":
                    entry.type=tarfile.SYMTYPE;entry.linkname="../../outside"
                    archive.addfile(entry)
                else:
                    value=b"original inert compiler fixture; never executed\n";entry.size=len(value)
                    archive.addfile(entry,io.BytesIO(value))
        return dict(archive_root=root,size=path.stat().st_size,sha256=windows.common.sha(path))

    def test_changed_archive_and_selected_symlink_are_refused(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);archive=root/"fixture.tar.xz";output=root/"output";output.mkdir()
            entry=self.fixture(archive)
            with self.assertRaises(ValueError):windows.extract_compiler(archive,output,dict(entry,sha256="0"*64))
            self.assertEqual(list(output.iterdir()),[])
            entry=self.fixture(archive,link=True)
            with self.assertRaises(ValueError):windows.extract_compiler(archive,output,entry)
            self.assertFalse((root/"outside").exists())

    def test_extracted_file_manifest_is_complete_without_executing_fixture(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);archive=root/"fixture.tar.xz";output=root/"output";output.mkdir()
            entry=self.fixture(archive)
            files=windows.extract_compiler(archive,output,entry)
            self.assertEqual(len(files),6)
            self.assertIn("bin/clang++.exe",files)
            self.assertTrue((output/"compiler-files.json").is_file())


if __name__=="__main__":unittest.main()
