# SPDX-License-Identifier: GPL-3.0-only
"""Original synthetic continuation-contract tests; no title or SDK required."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import verify_kernel_gate as driver


class StartupContractTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads(driver.STARTUP_CONTRACT.read_text(encoding="utf-8"))
        self.first = json.loads(driver.ALLOCATION_CONTRACT.read_text(encoding="utf-8"))

    def metadata(self, role):
        row = self.policy["roles"][role]
        return {"import_audit": {"libraries": [{"records": [{"type": 1, "export_name": "KeGetCurrentProcessType",
                "address": row["next_import"], "ordinal": 102, "export_kind": "kFunction"}]}]},
                "flow_scan": {"immediate_calls": [{"site": row["commit_lr"] - 4, "target": row["commit_import"]},
                                                  {"site": row["next_lr"] - 4, "target": row["next_import"]}]}}

    def inspect(self, policy, role="sp", metadata=None, digest=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "startup.json"
            path.write_text(json.dumps(policy), encoding="utf-8")
            return driver.inspect_startup(path, digest or driver.common.sha(path), role, self.first["roles"][role],
                                          metadata or self.metadata(role), self.first["generation_sha256"])

    def test_roles_and_caller_metadata_are_bound(self):
        for role in ("sp", "mp"):
            row, limit = self.inspect(self.policy, role)
            self.assertEqual(row, self.policy["roles"][role])
            self.assertGreaterEqual(limit, 65536)
        for key in ("site", "target"):
            metadata = self.metadata("sp")
            metadata["flow_scan"]["immediate_calls"][0][key] += 4
            with self.assertRaises(ValueError):
                self.inspect(self.policy, metadata=metadata)
        with self.assertRaises(ValueError):
            self.inspect(self.policy, digest="0" * 64)

    def test_changed_policy_or_call_contract_is_refused(self):
        for key, value in (("schema_version", True), ("phase", "unreviewed"), ("allow_commit", False),
                           ("call_budget", 3), ("max_commit_bytes", 1048577),
                           ("allocation_contract_sha256", "0" * 64), ("generation_sha256", "0" * 64)):
            changed = copy.deepcopy(self.policy)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(changed)

    def test_boolean_budget_context_and_evidence_substitutions_fail(self):
        for key, value in (("call_budget", True), ("max_commit_bytes", True), ("max_commit_bytes", 131072),
                           ("allocation_contract_sha256", "0" * 64), ("generation_sha256", "0" * 64),
                           ("source_audit_manifest_sha256", "bad"), ("extra", 1)):
            changed = copy.deepcopy(self.policy)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(changed)
        for key, value in (("commit_size", True), ("commit_size", 131072), ("hint", 0), ("flags", 3),
                           ("extra", 0), ("field", 0), ("next_ordinal", 103),
                           ("precall_capture_manifest_sha256", "bad"), ("metadata_sha256", "0" * 64)):
            changed = copy.deepcopy(self.policy)
            changed["roles"]["sp"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(changed)

    def test_next_import_cannot_change_kind_ordinal_address_or_multiplicity(self):
        for key in ("export_kind", "ordinal", "address", "duplicate", "missing"):
            metadata = self.metadata("sp")
            records = metadata["import_audit"]["libraries"][0]["records"]
            if key == "duplicate":
                records.append(dict(records[0]))
            elif key == "missing":
                records.clear()
            else:
                records[0][key] = "kVariable" if key == "export_kind" else records[0][key] + 4
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(self.policy, metadata=metadata)
        for key, value in (("first_lr", 4), ("commit_lr", 4), ("next_lr", 4), ("next_ordinal", 103),
                           ("global_base", True), ("global_address", 3), ("global_value", 1),
                           ("original_words_sha256", "unbound"), ("executable_sha256", "0" * 64)):
            changed = copy.deepcopy(self.policy)
            changed["roles"]["sp"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(changed)


class StartupCaptureTests(unittest.TestCase):
    nonce = "cd" * 16
    first = json.loads(driver.ALLOCATION_CONTRACT.read_text(encoding="utf-8"))["roles"]["sp"]
    selected = json.loads(driver.STARTUP_CONTRACT.read_text(encoding="utf-8"))["roles"]["sp"]

    def fixture(self):
        n = self.nonce
        return "\n".join([
            f"MW3_CHECKPOINT_RUN:case=positive nonce={n}",
            "MW3_MODULE_HEADER_AUDIT_PASS:synthetic",
            *["MW3_HEADER_ORACLE_CASE_PASS:synthetic"] * 4, "MW3_HEADER_QUERY_PASS:synthetic",
            f"MW3_ALLOCATION_ARMED:nonce={n}",
            f"MW3_ALLOCATION_INPUT:lr={self.first['lr']:08x} r1=700cfa10 r31=700cfa10 base_word=700cfa60 size_word=700cfb54 base=00000000 size=00100000 type=60002000 protect=00000004 region=00000000 nonce={n}",
            f"MW3_ALLOCATION_CALL:nonce={n}",
            f"MW3_ALLOCATION_RETURN:status=00000000 base=40000000 size=00100000 nonce={n}",
            f"MW3_ALLOCATION_CHECK_PASS:bytes=00100000 reserved=1 committed=0 neighbours=1 nonce={n}",
            f"MW3_STARTUP_RESUME:reserved=40000000 hint=00000000 page=00010000 flags=00000000 extra=00000000 field=00000000 global={self.selected['global_address']:08x} value=00000000 nonce={n}",
            f"MW3_STARTUP_INPUT:lr={self.selected['commit_lr']:08x} r31=700cfa10 base_word=700cfa64 size_word=700cfb5c base=40000000 size=00010000 type=60001000 protect=00000004 region=00000000 nonce={n}",
            f"MW3_STARTUP_STOP:before_commit=1 nonce={n}",
            "MW3_LIFECYCLE_THREAD_STOPPED:exit=86 queries=1", "MW3_LIFECYCLE_UNLOADED:reservation_released=1",
            "MW3_LIFECYCLE_MAPPING_RELEASED:bytes=4831838208",
            "MW3_LIFECYCLE_SHUTDOWN:result=0 threads_before=2 threads_after=2", "MW3_LIFECYCLE_COMPLETE:exit=86"])

    def accepted(self, text, code=86, nonce=None):
        return driver.classify_startup_inspect("positive-0", code, text, nonce or self.nonce, self.first, self.selected)

    def test_capture_requires_actual_reservation_and_no_commit(self):
        text = self.fixture()
        self.assertTrue(self.accepted(text))
        for before, after in (("status=00000000", "status=c000000d"), ("size=00010000", "size=00200000"),
                              ("base_word=700cfa64", "base_word=700cfa65"), ("type=60001000", "type=60003000")):
            self.assertFalse(self.accepted(text.replace(before, after)))
        self.assertFalse(self.accepted(text + "\nMW3_STARTUP_COMMIT_CALL:unexpected"))
        self.assertFalse(self.accepted(text + "\nMW3_PROBE_UNREVIEWED_IMPORT:OtherImport lr=0"))

    def test_stale_partial_duplicate_or_crashed_capture_fails(self):
        text = self.fixture()
        self.assertFalse(self.accepted(text.replace(self.nonce, "ef" * 16)))
        self.assertFalse(self.accepted(text, code=-999))
        self.assertFalse(self.accepted(text + "\nAddressSanitizer: synthetic"))
        for line in text.splitlines():
            if line.startswith(("MW3_ALLOCATION_", "MW3_STARTUP_", "MW3_LIFECYCLE_")):
                with self.subTest(line=line):
                    self.assertFalse(self.accepted(text.replace(line, "", 1)))
                    self.assertFalse(self.accepted(text + "\n" + line))

    def test_capture_rejects_frame_nonce_and_order_substitution(self):
        text = self.fixture()
        second = next(line for line in text.splitlines() if line.startswith("MW3_STARTUP_INPUT:"))
        changed = second.replace("700cfa10", "700dfa10").replace("700cfa64", "700dfa64").replace("700cfb5c", "700dfb5c")
        self.assertFalse(self.accepted(text.replace(second, changed)))
        self.assertFalse(self.accepted(text + "\nMW3_CHECKPOINT_RUN:case=positive nonce=" + "ef" * 16))
        self.assertFalse(self.accepted(text.replace(self.nonce, "zz" * 16), nonce="zz" * 16))
        header = next(line for line in text.splitlines() if line.startswith("MW3_HEADER_ORACLE_CASE_PASS:"))
        self.assertFalse(self.accepted(text.replace(header + "\n", "", 1) + "\n" + header))
        footer = "MW3_LIFECYCLE_UNLOADED:reservation_released=1"
        self.assertFalse(self.accepted(footer + "\n" + text.replace(footer, "")))


class StartupExecutionTests(unittest.TestCase):
    nonce = StartupCaptureTests.nonce
    first = StartupCaptureTests.first
    selected = StartupCaptureTests.selected

    def fixture(self, case="positive-0"):
        n = self.nonce
        text = StartupCaptureTests().fixture()
        text = text.replace("hint=00000000", "hint=00010000").replace("flags=00000000", "flags=00000002")
        text = text.replace("extra=00000000", "extra=000005b4").replace("field=00000000", "field=0000ffff")
        stop = f"MW3_STARTUP_STOP:before_commit=1 nonce={n}"
        ending = [f"MW3_STARTUP_COMMIT_CALL:nonce={n}",
                  f"MW3_STARTUP_COMMIT_RETURN:status=00000000 base=40000000 size=00010000 nonce={n}",
                  f"MW3_STARTUP_COMMIT_CHECK_PASS:bytes=00010000 pages=16 zero=1 neighbours=1 tail_reserved=1 nonce={n}",
                  f"MW3_STARTUP_HEAP_CHECK_PASS:markers=1 links=8 global=1 nonce={n}",
                  f"MW3_STARTUP_STOP:service=KeGetCurrentProcessType lr={self.selected['next_lr']:08x} before_call=1 nonce={n}"]
        text = text.replace(stop, "\n".join(ending))
        if case.startswith("positive"):
            return text
        text = text.replace("case=positive", f"case={case}")
        lines = text.splitlines()
        reasons = {"startup-bad-caller": "startup commit caller mismatch",
                   "startup-bad-pointer": "startup commit pointer setup mismatch",
                   "startup-bad-value": "startup commit value setup mismatch",
                   "startup-bad-oracle": "intentional startup commit oracle mismatch",
                   "startup-bad-heap": "intentional startup heap oracle mismatch"}
        before = "MW3_STARTUP_INPUT:" if case in ("startup-bad-caller", "startup-bad-pointer", "startup-bad-value") else (
                 "MW3_STARTUP_HEAP_CHECK_PASS:" if case == "startup-bad-oracle" else "MW3_STARTUP_STOP:")
        cut = next(i for i, line in enumerate(lines) if line.startswith(before))
        tail = lines[next(i for i, line in enumerate(lines) if line.startswith("MW3_LIFECYCLE_THREAD_STOPPED:")):]
        lines = lines[:cut] + [f"MW3_STARTUP_MUTATION:{case} nonce={n}"]
        if case == "startup-late":
            return "\n".join(lines)
        if case in reasons:
            lines += ["MW3_LIFECYCLE_REJECT:" + reasons[case]]
            tail = [line.replace("exit=86", "exit=87") for line in tail]
        else:
            lines += [ending[-1]]
            tail = tail[:-1]
        return "\n".join(lines + tail)

    def accepted(self, text, case="positive-0", code=86):
        return driver.classify_startup(case, code, text, self.nonce, self.first, self.selected)

    def test_actual_call_proof_heap_boundary_and_recovery_are_required(self):
        text = self.fixture()
        self.assertTrue(self.accepted(text))
        self.assertFalse(driver.classify_startup_inspect("positive-0", 86, text, self.nonce, self.first, self.selected))
        for line in text.splitlines():
            if line.startswith(("MW3_STARTUP_", "MW3_ALLOCATION_", "MW3_LIFECYCLE_")):
                with self.subTest(line=line):
                    self.assertFalse(self.accepted(text.replace(line, "", 1)))
                    self.assertFalse(self.accepted(text + "\n" + line))

    def test_result_access_accounting_and_boundary_mutations_fail(self):
        text = self.fixture()
        for before, after in (("pages=16", "pages=15"), ("zero=1", "zero=0"), ("neighbours=1", "neighbours=0"),
                              ("links=8", "links=7"), ("tail_reserved=1", "tail_reserved=0"), ("before_call=1", "before_call=0"),
                              ("status=00000000", "status=c0000017"), ("size=00010000", "size=00020000"),
                              ("flags=00000002", "flags=00000003"), ("hint=00010000", "hint=00000000"),
                              ("KeGetCurrentProcessType", "RtlInitializeCriticalSection"),
                              (f"lr={self.selected['next_lr']:08x}", "lr=00000000")):
            with self.subTest(before=before):
                self.assertFalse(self.accepted(text.replace(before, after)))

    def test_each_negative_control_requires_its_valid_baseline_and_exact_rejection(self):
        for case in driver.STARTUP_CASES:
            if not case.startswith("startup-"):
                continue
            code = -999 if case == "startup-late" else 86 if case == "startup-incomplete" else 87
            text = self.fixture(case)
            with self.subTest(case=case):
                self.assertTrue(self.accepted(text, case, code))
                self.assertFalse(self.accepted(text.replace("MW3_STARTUP_RESUME:", "MISSING:"), case, code))
                self.assertFalse(self.accepted(text.replace("MW3_STARTUP_MUTATION:", "MISSING:"), case, code))
                self.assertFalse(self.accepted(text, case, code=90))
                self.assertFalse(self.accepted(text + "\nAddressSanitizer: bad", case, code))
                if case in ("startup-bad-oracle", "startup-bad-heap", "startup-incomplete", "startup-late"):
                    self.assertFalse(self.accepted(text.replace("MW3_STARTUP_COMMIT_CHECK_PASS:", "MISSING:"), case, code))

    def test_order_stale_and_recovery_substitutions_fail(self):
        text = self.fixture()
        lines = text.splitlines()
        for a, b in ((7, 8), (13, 14), (14, 15), (16, 17), (-1, -2)):
            changed = list(lines)
            changed[a], changed[b] = changed[b], changed[a]
            self.assertFalse(self.accepted("\n".join(changed)))
        self.assertFalse(self.accepted(text.replace(self.nonce, "ef" * 16)))
        self.assertFalse(self.accepted(text.replace("threads_after=2", "threads_after=3")))
        self.assertFalse(self.accepted(text + "\nMW3_PROBE_UNREVIEWED_IMPORT:Other lr=0"))
        self.assertFalse(self.accepted(text.replace("MW3_MODULE_HEADER_AUDIT_PASS:", "MISSING:")))
        self.assertFalse(self.accepted(text + "\nMW3_MODULE_HEADER_AUDIT_PASS:duplicate"))
