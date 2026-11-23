# SPDX-License-Identifier: GPL-3.0-only
"""Game-free contract/protocol mutations; these do not demonstrate title execution."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import verify_kernel_gate as driver


class AllocationContractGuards(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(driver.ALLOCATION_CONTRACT.read_text())
        self.identity = {"executables": [{"name": name, "sha256": self.contract["roles"][role]["executable_sha256"]}
                                        for role, name in (("sp", "default.xex"), ("mp", "default_mp.xex"))]}

    def metadata(self, role):
        row = self.contract["roles"][role]
        return {"flow_scan": {"immediate_calls": [{"site": row["lr"] - 4, "target": row["import_address"]}]},
                "import_audit": {"libraries": [{"records": [{"type": 1, "export_name": "NtAllocateVirtualMemory",
                    "ordinal": 204, "export_kind": "kFunction", "address": row["import_address"]}]}]}}

    def validate(self, contract, role="sp", identity=None, metadata=None, digest=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "contract.json"
            path.write_text(json.dumps(contract))
            return driver.inspect_contract(path, digest or driver.common.sha(path), role,
                                           identity or self.identity, metadata or self.metadata(role),
                                           self.contract["generation_sha256"])

    def test_each_role_requires_exact_identity_and_explicit_digest(self):
        for role in ("sp", "mp"):
            self.assertEqual(self.validate(self.contract, role), self.contract["roles"][role])
        with self.assertRaises(ValueError):
            self.validate(self.contract, digest="0" * 64)
        for target in ("executable_sha256",):
            changed = copy.deepcopy(self.identity)
            changed["executables"][0]["sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                self.validate(self.contract, identity=changed)

    def test_policy_and_argument_mutations_fail_even_with_matching_file_digest(self):
        mutations = [("schema_version", True), ("phase", "inspect"), ("allow_allocation", 1),
                     ("call_budget", True), ("call_budget", 2), ("max_requested_bytes", 0),
                     ("max_requested_bytes", 1024), ("max_requested_bytes", 16777217),
                     ("generation_sha256", "0" * 64), ("unexpected", 1)]
        for key, value in mutations:
            changed = copy.deepcopy(self.contract)
            changed[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.validate(changed)
        for key, value in (("lr", True), ("lr", 3), ("ordinal", 205), ("base_pointer_r31_offset", 84),
                           ("size_pointer_r31_offset", 320), ("allocation_type", 0x1000), ("protection", 2),
                           ("region_source_gpr", 3), ("initial_base", 65536), ("initial_size", 65536),
                           ("region", 1), ("original_callsite_words_sha256", "bad"), ("extra", 1)):
            changed = copy.deepcopy(self.contract)
            changed["roles"]["sp"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(changed)

    def test_independent_import_and_caller_bindings_cannot_be_substituted(self):
        for kind in ("caller", "target", "address", "ordinal", "export_kind", "duplicate", "missing"):
            changed = self.metadata("sp")
            record = changed["import_audit"]["libraries"][0]["records"][0]
            if kind in ("caller", "target"):
                changed["flow_scan"]["immediate_calls"][0]["site" if kind == "caller" else "target"] += 4
            elif kind == "duplicate":
                changed["import_audit"]["libraries"][0]["records"].append(dict(record))
            elif kind == "missing":
                record["type"] = 0
            else:
                record[kind] = "kVariable" if kind == "export_kind" else record[kind] + 4
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.validate(self.contract, metadata=changed)

    def test_outputs_cannot_overlap_owned_or_verified_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            owned, sdk, metadata, gen = (root / name for name in ("owned", "sdk", "metadata", "generation"))
            for path in (owned, sdk, metadata, gen):
                path.mkdir()
            receipt = root / "receipts" / "manifest.json"
            for protected in (owned, sdk, metadata, gen, receipt.parent, root / "sources", driver.HOST,
                              driver.ROOT / "tools", driver.ROOT / "config"):
                for requested in (protected, protected / "child", protected.parent):
                    with self.subTest(requested=requested), self.assertRaises(ValueError):
                        driver.probe_output(requested, owned, root, sdk, receipt, metadata, gen / "generation.json")
            output = driver.probe_output(root / "private-output", owned, root, sdk, receipt, metadata, gen / "generation.json")
            self.assertEqual(output.parent, root / "private-output")
            self.assertFalse(output.exists())


class AllocationProtocolGuards(unittest.TestCase):
    nonce = "ab" * 16
    selected = json.loads(driver.ALLOCATION_CONTRACT.read_text())["roles"]["sp"]

    def cleanup(self, code=86, complete=True):
        lines = [f"MW3_LIFECYCLE_THREAD_STOPPED:exit={code} queries=1",
                 "MW3_LIFECYCLE_UNLOADED:reservation_released=1",
                 "MW3_LIFECYCLE_MAPPING_RELEASED:bytes=4831838208",
                 "MW3_LIFECYCLE_SHUTDOWN:result=0 threads_before=3 threads_after=3"]
        if complete:
            lines.append(f"MW3_LIFECYCLE_COMPLETE:exit={code}")
        return lines

    def fixture(self, case="positive-0"):
        mode = "positive" if case.startswith("positive") else case
        lines = [f"MW3_CHECKPOINT_RUN:case={mode} nonce={self.nonce}"]
        if case in ("bad-binding", "allocation-bad-binding"):
            return 87, "\n".join(lines + ["MW3_LIFECYCLE_REJECT:function binding verification"] + self.cleanup(87)[1:])
        lines += ["MW3_HEADER_ORACLE_CASE_PASS:synthetic"] * 4 + ["MW3_HEADER_QUERY_PASS:synthetic",
                  f"MW3_ALLOCATION_ARMED:nonce={self.nonce}"]
        if case == "allocation-bad-pointer":
            return 87, "\n".join(lines + [f"MW3_ALLOCATION_MUTATION:{case} nonce={self.nonce}",
                "MW3_LIFECYCLE_REJECT:allocation pointer setup differs from audited PPC"] + self.cleanup(87))
        lines += [f"MW3_ALLOCATION_INPUT:lr={self.selected['lr']:08x} r1=700cfa10 r31=700cfa10 base_word=700cfa60 size_word=700cfb54 base=00000000 size=00100000 type=60002000 protect=00000004 region=00000000 nonce={self.nonce}",
                  f"MW3_ALLOCATION_CALL:nonce={self.nonce}",
                  f"MW3_ALLOCATION_RETURN:status=00000000 base=40000000 size=00100000 nonce={self.nonce}",
                  f"MW3_ALLOCATION_CHECK_PASS:bytes=00100000 reserved=1 committed=0 neighbours=1 nonce={self.nonce}"]
        if case.startswith("allocation-"):
            lines.append(f"MW3_ALLOCATION_MUTATION:{case} nonce={self.nonce}")
        if case == "allocation-late":
            return -999, "\n".join(lines)
        if case == "allocation-bad-oracle":
            return 87, "\n".join(lines + ["MW3_LIFECYCLE_REJECT:intentional allocation oracle mismatch"] + self.cleanup(87))
        lines += [f"MW3_ALLOCATION_STOP:before_guest_return=1 nonce={self.nonce}"] + self.cleanup(complete=case != "allocation-incomplete")
        return 86, "\n".join(lines)

    def accepted(self, case, code, text):
        return driver.classify_allocation(case, code, text, self.nonce, self.selected)

    def test_complete_positive_and_intentional_controls(self):
        for case in ("positive-0", "positive-1", "positive-2", "bad-binding", *driver.ALLOCATION_CASES[7:]):
            code, text = self.fixture(case)
            self.assertTrue(self.accepted(case, code, text), case)
            self.assertFalse(self.accepted(case, code, text.replace(self.nonce, "cd" * 16)), case)
            self.assertFalse(self.accepted(case, code, text + "\nCrash report: synthetic"), case)

    def test_partial_duplicate_reordered_stale_and_wrong_result_evidence_fails(self):
        code, text = self.fixture()
        for line in text.splitlines():
            with self.subTest(line=line):
                self.assertFalse(self.accepted("positive-0", code, text.replace(line, "", 1)))
                self.assertFalse(self.accepted("positive-0", code, text + "\n" + line))
        for before, after in (("base=40000000", "base=40000001"), ("base=40000000", "base=00000000"),
                              ("status=00000000", "status=c000000d"), ("size=00100000", "size=00000010"),
                              ("r31=700cfa10", "r31=fffffffc"), ("base_word=700cfa60", "base_word=700cfa64"),
                              ("threads_after=3", "threads_after=4"), ("committed=0", "committed=1")):
            self.assertFalse(self.accepted("positive-0", code, text.replace(before, after)))
        self.assertFalse(self.accepted("positive-0", code, "\n".join(reversed(text.splitlines()))))
        self.assertFalse(self.accepted("positive-0", -999, text))
        self.assertFalse(self.accepted("positive-0", code, text + "\nMW3_PROBE_UNREVIEWED_IMPORT:AnotherImport lr=0"))

    def test_controls_require_their_real_baseline_and_expected_failure(self):
        for case in ("allocation-bad-oracle", "allocation-incomplete", "allocation-late"):
            code, text = self.fixture(case)
            self.assertFalse(self.accepted(case, code, text.replace("MW3_ALLOCATION_CHECK_PASS:", "omitted:")))
            self.assertFalse(self.accepted(case, code, text.replace("MW3_ALLOCATION_CALL:", "omitted:")))
            self.assertFalse(self.accepted("positive-0", code, text))

    def test_header_rejection_is_bound_to_this_checkpoint_nonce(self):
        lines = [f"MW3_CHECKPOINT_RUN:case=bad-pointer nonce={self.nonce}",
                 "MW3_LIFECYCLE_REJECT:unexpected header pointer", *self.cleanup(87)]
        text = "\n".join(lines)
        self.assertTrue(self.accepted("bad-pointer", 87, text))
        self.assertFalse(self.accepted("bad-pointer", 87, text.replace(self.nonce, "cd" * 16)))
        self.assertFalse(self.accepted("bad-pointer", 87, "\n".join(lines[1:])))

    def test_read_only_capture_never_accepts_an_allocation_call(self):
        _, text = self.fixture()
        lines = text.splitlines()
        captured = "\n".join(lines[:8] + ["MW3_PROBE_UNREVIEWED_IMPORT:NtAllocateVirtualMemory lr=1234"] + self.cleanup())
        self.assertTrue(driver.classify_allocation("positive-0", 86, captured, self.nonce, self.selected, inspect=True))
        self.assertFalse(driver.classify_allocation("positive-0", 86, text, self.nonce, self.selected, inspect=True))

    def test_cleanup_cannot_precede_call_oracle_or_rejection(self):
        for case in ("positive-0", "allocation-bad-oracle", "allocation-incomplete"):
            code, text = self.fixture(case)
            lines = text.splitlines()
            moved = [lines[0]] + [line for line in lines[1:] if line.startswith("MW3_LIFECYCLE_")]
            moved += [line for line in lines[1:] if not line.startswith("MW3_LIFECYCLE_")]
            self.assertFalse(self.accepted(case, code, "\n".join(moved)))
        for case in ("bad-binding", "allocation-bad-binding", "allocation-bad-pointer"):
            code, text = self.fixture(case)
            self.assertFalse(self.accepted(case, code, text + "\nMW3_PROBE_UNREVIEWED_IMPORT:OtherImport lr=0"))
            lines = text.splitlines()
            rejection = next(line for line in lines if line.startswith("MW3_LIFECYCLE_REJECT:"))
            moved = [line for line in lines if line != rejection] + [rejection]
            self.assertFalse(self.accepted(case, code, "\n".join(moved)))
        code, text = self.fixture("allocation-incomplete")
        self.assertFalse(self.accepted("allocation-incomplete", code, text + "\nMW3_LIFECYCLE_COMPLETE:exit=86"))
        code, text = self.fixture("allocation-late")
        self.assertFalse(self.accepted("allocation-late", code, text + "\nMW3_LIFECYCLE_COMPLETE:exit=86"))


if __name__ == "__main__":
    unittest.main()
