# SPDX-License-Identifier: GPL-3.0-only
"""Generation staging binds the current memory patch instead of a profile name alone."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
import prepare_runtime_memory as memory
import prepare_windows_runtime as windows


class MemoryStagingGuards(unittest.TestCase):
    def test_repaired_profile_stages_only_with_current_lock_and_composition(self):
        common=windows.common
        pins=json.loads((common.EXPERIMENT/"pins.json").read_text());base=pins["rexglue_memory_derivative"]
        patch,lock=memory.composition(False)
        identity=dict(original_inert_fixture=True)
        inputs=dict(title=identity,recipe=json.loads(common.RECIPE.read_text()),recipe_sha256=common.sha(common.RECIPE),
                    driver_sha256=common.sha(common.__file__),title_manifest_sha256=common.sha(common.DEFAULT),
                    helper_sha256={n:common.sha(common.EXPERIMENT/n) for n in ("prepare.py","mw2_tools.py","inspect_owned.py")},
                    toolchain=dict(source=dict(commit=base["commit"]),memory_profile=lock["profile"],
                                   memory_lock_sha256=common.sha(memory.LOCK),
                                   derivative=dict(base_commit=base["commit"],patch_sha256=hashlib.sha256(patch).hexdigest())))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for wrong in (False,True):
                inputs["toolchain"]["memory_lock_sha256"]="0"*64 if wrong else common.sha(memory.LOCK)
                key=common.digest(inputs);source=root/key;(source/"payload").mkdir(parents=True)
                (source/"payload/original.txt").write_text("inert fixture, never executed\n")
                files=common.snapshot(source/"payload")
                receipt=dict(key=key,inputs=inputs,files=files,code_manifest=files)
                (source/"manifest.json").write_text(json.dumps(receipt))
                target=root/"staged"/key
                if wrong:
                    with self.assertRaisesRegex(ValueError,"unreviewed reference memory profile"):
                        windows.stage_reference(source,target,identity,common.sha(source/"manifest.json"))
                    self.assertFalse(target.exists())
                else:
                    staged,_=windows.stage_reference(source,target,identity,common.sha(source/"manifest.json"))
                    self.assertTrue(staged.is_dir())


if __name__=="__main__":unittest.main()
