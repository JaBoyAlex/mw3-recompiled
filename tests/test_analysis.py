# SPDX-License-Identifier: GPL-3.0-only
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("title_analysis", ROOT / "config/analysis/analyze.py")
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.metadata = dict(entry_point=0x1000, sections=[dict(code=True, address=0x1000, size=0x100), dict(code=False, address=0x2000, size=0x100)])
        self.tables = dict(switch=[dict(base=0x1010, r=3, labels=[0x1020, 0x1030])])

    def test_valid_table_counts(self):
        self.assertEqual(analysis.validate_switches(self.metadata, self.tables), dict(switch_tables=1, switch_targets=2))

    def test_entry_in_data_refused(self):
        self.metadata["entry_point"] = 0x2000
        with self.assertRaisesRegex(ValueError, "entry point"):
            analysis.validate_switches(self.metadata, self.tables)

    def test_targets_dispatch_and_duplicates_refused(self):
        for change in ("data-target", "eof-target", "dispatch", "duplicate", "register", "empty"):
            tables = copy.deepcopy(self.tables)
            if change == "data-target": tables["switch"][0]["labels"] = [0x2000]
            elif change == "eof-target": tables["switch"][0]["labels"] = [0x1100]
            elif change == "dispatch": tables["switch"][0]["base"] = 0x2000
            elif change == "duplicate": tables["switch"].append(copy.deepcopy(tables["switch"][0]))
            elif change == "register": tables["switch"][0]["r"] = 32
            else: tables["switch"][0]["labels"] = []
            with self.assertRaises(ValueError):
                analysis.validate_switches(self.metadata, tables)


if __name__ == "__main__":
    unittest.main()
