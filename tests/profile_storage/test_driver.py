# SPDX-License-Identifier: GPL-3.0-only
"""Evidence-accounting controls, not mocked evidence of filesystem isolation."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("profile_storage_driver", ROOT / "tools/test_profile_storage.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def result(status="PASS", failures=0, skips=0):
    return ("MW3_STORAGE_LIBRARY:/private/librexfilesystem.so\n"
            f"MW3_STORAGE_CASE:name=profiles status={status} microseconds=50\n"
            f"MW3_STORAGE_COMPLETE:count=1 failures={failures} skips={skips} threads_before=0 threads_after=0\n")


class ResultGuards(unittest.TestCase):
    def test_approved_receipt_and_all_package_bytes_are_required(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            sdk = root / "sdk"
            sdk.mkdir()
            (sdk / "module").write_text("original synthetic package")
            lock = root / "lock.json"
            lock.write_text(json.dumps(dict(profile="synthetic-original")))
            receipt = root / "receipt.json"
            receipt.write_text(json.dumps(dict(status="PASS", profile="synthetic-original", core_sanitizers=False,
                sdk_prefix=str(sdk), xma_lock_sha256=driver.common.sha(lock),
                script_sha256=driver.common.sha(driver.xma.__file__), sdk_files=driver.memory.package_files(sdk),
                source=dict(synthetic=True), compiler=dict(synthetic=True))))
            validation = root / "approval.json"
            validation.write_text(json.dumps(dict(status="PASS", sdk_preparations=[
                dict(receipt_sha256=driver.common.sha(receipt), core_sanitizers=False)])))
            # Windows CI may spell Temp with RUNNER~1; compare canonical paths.
            self.assertEqual(driver.verify_package(receipt, validation, lock)[0], sdk.resolve())
            (sdk / "module").write_text("modified")
            with self.assertRaisesRegex(ValueError, "package changed"):
                driver.verify_package(receipt, validation, lock)
            (sdk / "module").write_text("original synthetic package")
            receipt.write_text(receipt.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "not an approved"):
                driver.verify_package(receipt, validation, lock)

    def test_missing_duplicate_reordered_and_late_cannot_pass(self):
        valid = result()
        self.assertEqual(driver.classify(("profiles",), 0, valid), "PASS")
        for text in ("", valid + valid, valid.replace("name=profiles", "name=relative"),
                     valid.replace("count=1", "count=2"), valid.replace("threads_after=0", "threads_after=1")):
            self.assertEqual(driver.classify(("profiles",), 0, text), "FAIL")
        self.assertEqual(driver.classify(("profiles",), -999, valid), "FAIL")
        self.assertEqual(driver.classify(("profiles",), 2, valid), "FAIL")

    def test_sdk_failure_and_sanitizer_never_pass_as_expected_control(self):
        failed = result("FAIL", 1) + "MW3_STORAGE_FAILURE:case=profiles reason=wrong-profile-a\n"
        self.assertEqual(driver.classify(("profiles",), 42, failed), "FAIL")
        self.assertEqual(driver.classify(("profiles",), 42, failed, mutation=True), "FAIL")
        self.assertEqual(driver.classify(("profiles",), 0, result() + "ERROR: AddressSanitizer: bad\n"), "FAIL")

    def test_mutation_requires_exact_case_exception_and_cleanup(self):
        control = (result("FAIL", 1) + "MW3_STORAGE_FAILURE:case=profiles reason=deliberate-wrong-profile\n"
                   "MW3_STORAGE_MUTATION:wrong-profile\n")
        self.assertEqual(driver.classify(("profiles",), 42, control, mutation=True), "PASS")
        for text in (control.replace("reason=deliberate-wrong-profile", "reason=unrelated"),
                     control + "runtime error: bad\n", control.replace("threads_after=0", "threads_after=2")):
            self.assertEqual(driver.classify(("profiles",), 42, text, mutation=True), "FAIL")

    def test_skip_is_only_allowed_for_link_capability(self):
        skipped = result("SKIP", 0, 1)
        self.assertEqual(driver.classify(("profiles",), 0, skipped), "FAIL")
        skipped = skipped.replace("name=profiles", "name=file-link")
        self.assertEqual(driver.classify(("file-link",), 0, skipped), "FAIL")
        skipped += "MW3_STORAGE_SKIP:case=file-link reason=host-link-permission-or-unsupported\n"
        self.assertEqual(driver.classify(("file-link",), 0, skipped), "SKIP")

    def test_incomplete_control_cannot_hide_normal_completion(self):
        control = "MW3_STORAGE_LIBRARY:/private/librexfilesystem.so\nMW3_STORAGE_INCOMPLETE:armed\n"
        self.assertEqual(driver.classify((), 43, control, incomplete=True), "PASS")
        self.assertEqual(driver.classify(("profiles",), 43, control), "FAIL")
        self.assertEqual(driver.classify((), 43, control + result(), incomplete=True), "FAIL")

    def test_artifacts_record_internal_links_and_refuse_external_links(self):
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside:
            root = Path(raw)
            (root / "canary").mkdir()
            (root / "canary/data").write_text("private")
            try:
                (root / "link").symlink_to(root / "canary", target_is_directory=True)
            except OSError:
                self.skipTest("host link privilege unavailable")
            observed = driver.artifact_snapshot(root)
            self.assertTrue(observed["link"]["directory"])
            self.assertNotIn("link/data", observed)
            (root / "external").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "leaves private attempt"):
                driver.artifact_snapshot(root)


if __name__ == "__main__":
    unittest.main()
