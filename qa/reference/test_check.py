# SPDX-License-Identifier: GPL-3.0-only
"""Original evidence fixtures; they are never retail-console observations."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check


class ReferenceContractTests(unittest.TestCase):
    def setUp(self):
        self.catalog = check.load(check.HERE / "catalog.json")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.capture = self.root / "original.bin"
        self.capture.write_bytes(b"Original synthetic reference artifact, not game output.")

    def fixture(self, ident="REF-SYS-IDENTITY", status="PASS"):
        result = check.template(self.catalog)
        result.update(synthetic=True, origin="synthetic", console=dict(platform="xbox360", model="synthetic",
                      system_version="fixture-1", title_update_state="confirmed_absent", dlc_state="baseline_only",
                      profile_id="synthetic-only", capture_tool="original-test-fixture-1"))
        plan = next(c for c in self.catalog["cases"] if c["id"] == ident)
        row = next(c for c in result["cases"] if c["case_id"] == ident)
        row.update(status=status, reason="" if status == "PASS" else "Deliberate observed failure fixture.",
                   checks={key: status == "PASS" for key in plan["checks"]},
                   observed={key: next(f["value"] for f in self.catalog["facts"] if f["id"] == key) for key in plan["facts"]},
                   artifacts=[dict(path=self.capture.name, sha256=hashlib.sha256(self.capture.read_bytes()).hexdigest())])
        return result, row

    def validate(self, result):
        return check.validate_submission(self.catalog, result, self.root)

    def test_default_plan_preserves_unknowns_and_separate_topologies(self):
        _, facts, inventories, cases = check.validate_catalog(self.catalog)
        self.assertEqual(len(cases), 37)
        self.assertEqual(sum(f["basis"] == "unobserved" for f in facts.values()), 10)
        self.assertEqual(sum(i["required"] and i["state"] != "complete" for i in inventories.values()), 8)
        self.assertTrue(all(c["status"] == "NOT_RUN" and c["reason"] for c in cases.values()))
        self.assertIsNone(facts["mp.online_local"]["value"])
        self.assertIsNone(facts["mp.local_limit"]["value"])
        self.assertEqual(facts["ops.advertised_coop"]["value"], 2)
        self.assertIsNone(facts["sur.local_limit"]["value"])

    def test_unknown_value_cannot_become_a_documented_fact(self):
        fact = next(f for f in self.catalog["facts"] if f["basis"] == "unobserved")
        fact["value"] = 4
        with self.assertRaisesRegex(ValueError, "unknown fact"):
            check.validate_catalog(self.catalog)

    def test_metadata_cannot_substitute_for_manual_or_console_source(self):
        fact = self.catalog["facts"][0]
        fact["source"] = "OWNED-IDENTITY"
        with self.assertRaisesRegex(ValueError, "source class"):
            check.validate_catalog(self.catalog)
        fact["basis"] = "console"
        with self.assertRaisesRegex(ValueError, "source class"):
            check.validate_catalog(self.catalog)

    def test_source_pin_and_pdf_page_are_checked(self):
        copy = deepcopy(self.catalog)
        copy["sources"][1]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source pin"):
            check.validate_catalog(copy)
        self.catalog["facts"][0]["pdf_page"] = 20
        with self.assertRaisesRegex(ValueError, "PDF page"):
            check.validate_catalog(self.catalog)

    def test_extension_cannot_be_required_or_count_as_retail(self):
        case = next(c for c in self.catalog["cases"] if c["scope"] == "extension")
        case["required"] = True
        with self.assertRaisesRegex(ValueError, "extension"):
            check.validate_catalog(self.catalog)
        case.update(required=False, scope="retail", mode="survival")
        with self.assertRaisesRegex(ValueError, "extension"):
            check.validate_catalog(self.catalog)

    def test_missing_mode_or_optional_only_mode_is_rejected(self):
        self.catalog["cases"] = [c for c in self.catalog["cases"] if c["mode"] != "multiplayer_online"]
        with self.assertRaisesRegex(ValueError, "baseline mode"):
            check.validate_catalog(self.catalog)

    def test_empty_inventory_cannot_mean_complete(self):
        self.catalog["inventories"][0]["state"] = "complete"
        self.catalog["inventories"][0]["reason"] = ""
        with self.assertRaisesRegex(ValueError, "empty inventory"):
            check.validate_catalog(self.catalog)

    def test_duplicate_identifiers_and_dangling_dependencies_rejected(self):
        copy = deepcopy(self.catalog)
        copy["cases"].append(deepcopy(copy["cases"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate identifier"):
            check.validate_catalog(copy)
        self.catalog["cases"][0]["inventories"] = ["unknown_inventory"]
        with self.assertRaisesRegex(ValueError, "dangling"):
            check.validate_catalog(self.catalog)

    def test_duplicate_json_nonfinite_and_oversized_input_rejected(self):
        path = self.root / "input.json"
        for content, pattern in ((b'{"x":1,"x":2}', "duplicate JSON"),
                                  (b'{"x":NaN}', "nonfinite"), (b" " * (2 * 1024 * 1024 + 1), "byte budget")):
            path.write_bytes(content)
            with self.assertRaisesRegex(ValueError, pattern):
                check.load(path)

    def test_template_is_valid_but_incomplete(self):
        report = self.validate(check.template(self.catalog))
        self.assertEqual(report["counts"]["NOT_RUN"], 37)
        self.assertFalse(report["console_submission_complete"] or report["gameplay_certified"])

    def test_synthetic_capture_is_accepted_only_as_synthetic(self):
        result, _ = self.fixture()
        report = self.validate(result)
        self.assertEqual(report["counts"]["PASS"], 1)
        self.assertTrue(report["synthetic"] and report["semantic_review_required"])
        self.assertFalse(report["console_submission_complete"] or report["gameplay_certified"])
        result["origin"] = "owned_console"
        with self.assertRaisesRegex(ValueError, "contradictory synthetic"):
            self.validate(result)

    def test_native_runtime_or_emulator_is_not_console_reference(self):
        for origin in ("native_runtime", "emulator", "source_inspection"):
            result, _ = self.fixture()
            result.update(origin=origin, synthetic=False)
            with self.assertRaisesRegex(ValueError, "not a console-reference"):
                self.validate(result)

    def test_wrong_build_update_dlc_and_stale_catalog_rejected(self):
        result, _ = self.fixture()
        for field in ("iso_sha256", "title_update", "dlc"):
            altered = deepcopy(result)
            altered["baseline"][field] = "changed"
            with self.assertRaisesRegex(ValueError, "context"):
                self.validate(altered)
        result["console"]["title_update_state"] = "unknown"
        with self.assertRaisesRegex(ValueError, "unverified update"):
            self.validate(result)
        result, _ = self.fixture()
        result["catalog_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "changed catalog"):
            self.validate(result)

    def test_missing_extra_and_duplicate_results_rejected(self):
        result, _ = self.fixture()
        for action in ("remove", "extra", "duplicate"):
            altered = deepcopy(result)
            if action == "remove":
                altered["cases"].pop()
            else:
                row = deepcopy(altered["cases"][0])
                if action == "extra":row["case_id"] = "REF-EXTRA"
                altered["cases"].append(row)
            with self.assertRaisesRegex(ValueError, "case results|duplicate identifier"):
                self.validate(altered)

    def test_missing_checks_unknown_expectations_and_inventory_block_pass(self):
        result, row = self.fixture()
        row["checks"].pop(next(iter(row["checks"])))
        with self.assertRaisesRegex(ValueError, "missing/failed"):
            self.validate(result)
        result, row = self.fixture("REF-MP-LOCAL-LIMIT")
        row["observed"]["mp.local_limit"] = 4
        with self.assertRaisesRegex(ValueError, "unknown or mismatched"):
            self.validate(result)
        result, row = self.fixture("REF-CAM-PLAY")
        with self.assertRaisesRegex(ValueError, "unresolved case inventory"):
            self.validate(result)

    def test_boolean_cannot_substitute_for_count(self):
        # Resolve only the synthetic fixture's inventory to reach the typed assertion.
        for inventory in self.catalog["inventories"]:
            if inventory["id"] in ("campaign_missions", "campaign_difficulties"):
                inventory.update(state="complete", items=["synthetic-only"], reason="")
        result, row = self.fixture("REF-CAM-PLAY")
        row["observed"]["cam.single_player"] = True
        with self.assertRaisesRegex(ValueError, "mismatched reference"):
            self.validate(result)

    def test_tampered_missing_or_unsafe_artifact_rejected(self):
        result, row = self.fixture()
        self.capture.write_bytes(b"deliberate mutation")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.validate(result)
        for path in ("../outside", "/absolute", "C:outside", "folder\\escape"):
            row["artifacts"][0]["path"] = path
            with self.assertRaisesRegex(ValueError, "unsafe artifact"):
                self.validate(result)
        row["artifacts"] = []
        with self.assertRaisesRegex(ValueError, "retained evidence"):
            self.validate(result)

    def test_real_artifact_symlink_rejected(self):
        link = self.root / "alias.bin"
        try:
            link.symlink_to(self.capture)
        except OSError:
            self.skipTest("host symlink privilege unavailable")
        result, row = self.fixture()
        row["artifacts"][0]["path"] = link.name
        with self.assertRaisesRegex(ValueError, "redirected artifact"):
            self.validate(result)

    def test_failure_is_retained_and_nonpassing_reason_required(self):
        result, _ = self.fixture(status="FAIL")
        report = self.validate(result)
        self.assertEqual(report["counts"]["FAIL"], 1)
        result["cases"][-1]["reason"] = ""
        with self.assertRaisesRegex(ValueError, "explicit reason"):
            self.validate(result)

    def test_cli_explicit_incomplete_exit_and_exclusive_template(self):
        command = [sys.executable, str(check.HERE / "check.py")]
        result = subprocess.run(command + ["--require-console"], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["console_submission_complete"])
        path = self.root / "template.json"
        result = subprocess.run(command + ["--template", str(path)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        before = path.read_bytes()
        result = subprocess.run(command + ["--template", str(path)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
