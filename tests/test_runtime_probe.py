# SPDX-License-Identifier: GPL-3.0-only
"""Original import-boundary guards; no title code or SDK required."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from runtime_probe import guarded_traps


def inventory():
    return dict(import_audit=dict(libraries=[dict(records=[
        dict(type=1,export_kind="kFunction",export_name="RtlImageXexHeaderField",address=0x82001000),
        dict(type=1,export_kind="kFunction",export_name="OriginalSyntheticOtherImport",address=0x82001010),
        dict(type=0,export_kind="kVariable",export_name="XexExecutableModuleHandle",address=0x82002000)
    ])]))


class RuntimeProbeGuards(unittest.TestCase):
    def test_only_reviewed_query_is_admitted_and_every_function_is_still_bound(self):
        source,address=guarded_traps(inventory(),"original_synthetic_probe",2)
        self.assertEqual(address,0x82002000)
        self.assertIn('extern "C" void __imp__RtlImageXexHeaderField(PPCContext&, u8*);',source)
        self.assertNotIn("MW3_PROBE_UNREVIEWED_IMPORT:RtlImageXexHeaderField",source)
        self.assertIn("MW3_PROBE_UNREVIEWED_IMPORT:OriginalSyntheticOtherImport",source)
        self.assertIn("*fn != &__imp__RtlImageXexHeaderField",source)
        self.assertIn("*fn != &__imp__OriginalSyntheticOtherImport",source)

    def test_missing_function_or_variable_and_coverage_change_are_refused(self):
        original=inventory()
        with self.assertRaises(ValueError):guarded_traps(original,"fixture",3)
        for index in (0,2):
            changed=copy.deepcopy(original)
            del changed["import_audit"]["libraries"][0]["records"][index]
            with self.subTest(index=index),self.assertRaises(ValueError):guarded_traps(changed,"fixture",2 if index==2 else 1)
        changed=copy.deepcopy(original)
        changed["import_audit"]["libraries"][0]["records"].append(copy.deepcopy(original["import_audit"]["libraries"][0]["records"][2]))
        with self.assertRaises(ValueError):guarded_traps(changed,"fixture",2)

    def test_bad_data_import_addresses_and_kind_are_refused(self):
        for address in (-1,0x100000000,0x82000001,True,"bad"):
            value=inventory()
            value["import_audit"]["libraries"][0]["records"][2]["address"]=address
            with self.subTest(address=address),self.assertRaises(ValueError):guarded_traps(value,"fixture",2)
        value=inventory()
        value["import_audit"]["libraries"][0]["records"][2]["export_kind"]="kFunction"
        with self.assertRaises(ValueError):guarded_traps(value,"fixture",2)


if __name__=="__main__":unittest.main()
