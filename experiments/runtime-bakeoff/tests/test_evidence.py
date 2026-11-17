# SPDX-License-Identifier: GPL-3.0-only
"""Original fixtures for fail-closed experiment reporting and import stops."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host_checks import summarize
from inspect_owned import generator_errors
from rexglue_probe import make_traps
from prepare import outside_owned


def metadata(name="OriginalFixture", address=0x1000):
    return {"import_audit": {"libraries": [{"records": [
        {"type": 0, "export_kind": "kVariable", "export_name": "OriginalVariable", "address": 0x2000},
        {"type": 1, "export_kind": "kFunction", "export_name": name, "address": address}]}]}}


class EvidenceTests(unittest.TestCase):
    def test_output_cannot_land_in_owned_tree_or_symlink_into_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            owned = root / "owned"
            owned.mkdir()
            with self.assertRaisesRegex(ValueError, "overlaps"):
                outside_owned(owned / "runs/fixture", owned)
            outside_owned(root / "private/runs/fixture", owned)
            alias = root / "alias"
            try:
                alias.symlink_to(owned, target_is_directory=True)
            except OSError:
                self.skipTest("direct guard passed; symlink privilege unavailable")
            with self.assertRaisesRegex(ValueError, "overlaps"):
                outside_owned(alias / "fixture", owned)

    def test_error_text_cannot_pass_by_exit_zero(self):
        self.assertEqual(generator_errors("progress\nERROR: original fixture\n  ERROR: another\n"), 2)
        self.assertEqual(generator_errors("Failed: fixture\n"), 1)
        self.assertEqual(generator_errors("warning\nprogress 100%\n"), 0)

    def test_xml_keeps_no_assertion_case_and_failure(self):
        # Catch2's JUnit reporter omits a selected case with no assertions;
        # its native XML retains the case and its pass/fail outcome.
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "result.xml"
            path.write_text('<Catch2TestRun><TestCase name="original"><OverallResult success="true"/></TestCase></Catch2TestRun>')
            self.assertEqual(summarize(path)["cases"], 1)
            self.assertEqual(summarize(path)["failed"], [])
            path.write_text('<Catch2TestRun><TestCase name="original"><OverallResult success="false"/></TestCase></Catch2TestRun>')
            self.assertEqual(summarize(path)["failed"], ["original"])

    def test_import_stop_and_binding_guard_are_both_emitted(self):
        source = make_traps(metadata(), "original_fixture")
        self.assertIn("std::_Exit(86)", source)
        self.assertIn("runtime.FindFunction(0x1000)", source)
        self.assertIn("*fn != &__imp__OriginalFixture", source)
        self.assertNotIn("__imp__OriginalVariable", source)
        self.assertEqual(source.count("std::_Exit(86)"), 1)
        self.assertNotIn('Fixture\n"', source)

    def test_untrusted_identifiers_and_addresses_are_rejected(self):
        for name, address in [('bad";code', 0x1000), ("ok", 0x1001), ("ok", 2**32), ("ok", -4)]:
            with self.subTest(name=name, address=address), self.assertRaises(ValueError):
                make_traps(metadata(name, address), "original_fixture")
        with self.assertRaises(ValueError):
            make_traps(metadata(), "../bad")
        duplicate = metadata()
        duplicate["import_audit"]["libraries"][0]["records"].append(
            duplicate["import_audit"]["libraries"][0]["records"][1].copy())
        with self.assertRaisesRegex(ValueError, "duplicate"):
            make_traps(duplicate, "original_fixture")
        unknown = metadata()
        unknown["import_audit"]["libraries"][0]["records"][1]["export_kind"] = None
        with self.assertRaisesRegex(ValueError, "cannot be skipped"):
            make_traps(unknown, "original_fixture")


if __name__ == "__main__":
    unittest.main()
