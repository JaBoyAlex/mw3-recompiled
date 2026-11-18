# SPDX-License-Identifier: GPL-3.0-only
"""Only explicit all-skipped XML can explain Catch2's nonzero skip exit."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
import test_runtime_memory as driver


class UpstreamStatusGuards(unittest.TestCase):
    def test_skip_cannot_hide_failure_or_an_unexplained_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"original.xml"
            path.write_text('<Catch2TestRun><TestCase><Skip>original 16 KiB fixture unavailable</Skip></TestCase>'
                            '<OverallResults successes="0" failures="0" skips="1"/></Catch2TestRun>')
            self.assertEqual(driver.upstream_status(4,dict(failed=[]),path)[0],"SKIP")
            self.assertEqual(driver.upstream_status(1,dict(failed=[]),path)[0],"FAIL")
            self.assertEqual(driver.upstream_status(4,dict(failed=["actual failure"]),path)[0],"FAIL")
            path.write_text('<Catch2TestRun><OverallResults successes="0" failures="0" skips="0"/></Catch2TestRun>')
            self.assertEqual(driver.upstream_status(4,dict(failed=[]),path)[0],"FAIL")


if __name__=="__main__":unittest.main()
