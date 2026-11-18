# SPDX-License-Identifier: GPL-3.0-only
"""Game-free package selection/fingerprint guards; no compiler download in CI."""
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import prepare_windows_runtime as windows


class WindowsPreparationTests(unittest.TestCase):
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
