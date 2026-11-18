# SPDX-License-Identifier: GPL-3.0-only
"""Refuse stale/modified SDK receipts and validation-only code generation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
import prepare_runtime_memory as memory
import recompile as common


class MemoryPreparationGuards(unittest.TestCase):
    def fixture(self,root):
        sdk=root/"sdk";sdk.mkdir();(sdk/"original-inert.txt").write_text("original inert package, never executable\n")
        return dict(status="PASS",profile=json.loads(memory.LOCK.read_text())["profile"],
                    memory_lock_sha256=common.sha(memory.LOCK),script_sha256=common.sha(memory.__file__),
                    source=dict(original_fixture=True),sdk_prefix=str(sdk),sdk_files=memory.package_files(sdk),core_sanitizers=False)

    def test_stale_preparer_and_modified_artifact_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);receipt=self.fixture(root);path=root/"manifest.json"
            receipt["script_sha256"]="0"*64;path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,"unreviewed"),patch.object(memory,"source_identity") as source:
                memory.verify_prepared(root,path)
            source.assert_not_called()
            receipt["script_sha256"]=common.sha(memory.__file__);path.write_text(json.dumps(receipt))
            (root/"sdk/original-inert.txt").write_text("changed fixture")
            with patch.object(memory,"source_identity",return_value=receipt["source"]),self.assertRaisesRegex(ValueError,"artifact changed"):
                memory.verify_prepared(root,path)
            self.assertEqual((root/"sdk/original-inert.txt").read_text(),"changed fixture")

    def test_core_instrumented_package_cannot_generate_title_code(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);receipt=self.fixture(root);receipt["core_sanitizers"]=True
            path=root/"manifest.json";path.write_text(json.dumps(receipt))
            with patch.object(memory,"source_identity") as source,self.assertRaisesRegex(ValueError,"validation-only"):
                common.toolchain(root,path)
            source.assert_not_called()

    def test_modified_composed_patch_is_preserved_instead_of_repaired(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);output=root/"attempt";output.mkdir()
            path=output/"combined-memory.patch";path.write_bytes(b"changed original fixture")
            with self.assertRaisesRegex(ValueError,"recorded memory patch changed"):
                memory.source_identity(root,output,existing=True)
            self.assertEqual(path.read_bytes(),b"changed original fixture")

    def test_generator_cannot_load_an_older_external_sdk_library(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sdk=root/"sdk";sdk.mkdir();old=root/"librexkernel.so"
            old.write_text("original inert fixture, never loaded\n")
            listing=f"librexkernel.so => {old.as_posix()} (0x1234)\n"
            with patch.object(common.subprocess,"run",return_value=SimpleNamespace(stdout=listing)),self.assertRaisesRegex(ValueError,"outside the verified package"):
                common.sdk_system_libraries(sdk)


if __name__=="__main__":unittest.main()
