# SPDX-License-Identifier: GPL-3.0-only
import copy
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
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

    def test_helper_ambiguities_are_reported_and_decoder_required(self):
        metadata = dict(helpers=[dict(family=operation+family, candidates=[0x1000], decoder_checked=True,
                                     stride=4, first_register=14, last_register=31)
                                for operation in ("save", "rest") for family in ("gprlr_14", "fpr_14", "vmx_14", "vmx_64")],
                        pdata=dict(entries=0, functions=[], type_counts=[0, 0, 0, 0], covered_code_bytes=0, code_bytes=256),
                        flow_scan=dict(immediate_calls=[], unresolved_indirect_sites=[]), resolved_import_symbols=[])
        metadata["helpers"][0]["candidates"] = []
        metadata["helpers"][1]["candidates"] = [0x1000, 0x2000]
        summary = analysis.summarize_mapping(metadata)
        self.assertEqual((summary["unique_helper_families"], summary["missing_helper_families"], summary["ambiguous_helper_families"]), (6, 1, 1))
        metadata["helpers"][0]["decoder_checked"] = False
        with self.assertRaisesRegex(ValueError, "decoder"):
            analysis.summarize_mapping(metadata)

    def test_repeat_compares_full_metadata_identity(self):
        report = {key: "original" for key in ("schema_version", "identity", "analyzer_sha256", "analysis_source_sha256",
                  "loader_static_library_sha256", "decoder_static_library_sha256", "compiler", "probe_sanitizers", "titles")}
        analysis.compare_reports(report, copy.deepcopy(report))
        for key in report:
            changed = copy.deepcopy(report)
            changed[key] = "mutated"
            with self.assertRaisesRegex(ValueError, key):
                analysis.compare_reports(report, changed)


class NativeScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cmake = shutil.which("cmake")
        if not cmake:
            raise unittest.SkipTest("CMake unavailable on PATH; run standalone config/analysis/probe scan tests")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.build = Path(cls.temp.name) / "build"
        configure = [cmake, "-S", str(ROOT / "config/analysis/probe"), "-B", str(cls.build),
                     "-DMW3_SCAN_TESTS_ONLY=ON", "-DCMAKE_BUILD_TYPE=Debug"]
        if os.name != "nt":
            configure += ["-DMW3_SCAN_SANITIZERS=ON"]
        subprocess.run(configure, check=True, capture_output=True)
        subprocess.run([cmake, "--build", str(cls.build), "--config", "Debug", "--parallel", "2"], check=True, capture_output=True)
        cls.binary = cls.build / ("Debug/mw3-scan-tests.exe" if os.name == "nt" else "mw3-scan-tests")

    def test_bounded_scans_and_negative_cases(self):
        result = subprocess.run([str(self.binary)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("metadata scan checks", result.stdout)

    def test_llvm_assembled_standard_helpers(self):
        mc = shutil.which("llvm-mc-18") or shutil.which("llvm-mc")
        objcopy = shutil.which("llvm-objcopy-18") or shutil.which("llvm-objcopy")
        if not mc or not objcopy:
            self.skipTest("LLVM assembler/objcopy unavailable; owned-title decoder verification is a separate private check")
        # Assemble independently from mnemonic ABI descriptions. No scanner
        # encodings and no title instructions are used to construct this oracle.
        lines = [".text"]
        for family in ("gpr", "fpr", "vmx"):
            for save in (False, True):
                for reg in range(14, 32):
                    if family == "gpr":
                        lines.append(f"{'std' if save else 'ld'} {reg},{-8*(33-reg)}(1)")
                    elif family == "fpr":
                        lines.append(f"{'stfd' if save else 'lfd'} {reg},{-8*(32-reg)}(12)")
                    else:
                        lines.extend([f"li 11,{-16*(32-reg)}", f"{'stvx' if save else 'lvx'} {reg},11,12"])
                if family == "gpr":
                    lines.append(f"{'stw' if save else 'lwz'} 12,-8(1)")
                    if not save: lines.append("mtlr 12")
                lines.append("blr")
        folder = Path(self.temp.name)
        source, obj, binary = (folder / name for name in ("oracle.s", "oracle.o", "oracle.bin"))
        source.write_text("\n".join(lines) + "\n")
        subprocess.run([mc, "-triple=powerpc64-unknown-linux-gnu", "-mattr=+altivec", "-filetype=obj", str(source), "-o", str(obj)], check=True, capture_output=True)
        subprocess.run([objcopy, "--dump-section", f".text={binary}", str(obj)], check=True, capture_output=True)
        result = subprocess.run([str(self.binary), str(binary)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
