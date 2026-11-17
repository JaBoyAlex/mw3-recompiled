#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Run selected upstream synthetic host checks in isolated, private processes.

Preserves failures; process isolation investigates shared-state/order dependence,
and does not turn the corresponding aggregate-suite failure into a pass.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

from prepare import sha

SPEC = "[ppc],[memory],[aliases],[thread],[threads],[tls],[interlocked],[barrier],[dispatcher]"


def exact_filter(name):
    # Catch2 filters interpret wildcards, commas, quotes, brackets and backslashes.
    return ''.join('\\' + c if c in '\\*?,[]"' else c for c in name)


def summarize(path):
    tree = ET.parse(path)
    cases = list(tree.iter("TestCase"))
    return dict(cases=len(cases), failed=[c.attrib.get("name") for c in cases
                if any(r.attrib.get("success") == "false" for r in c.iter("OverallResult"))
                or list(c.iter("FatalErrorCondition")) or list(c.iter("Exception"))],
                suites=[s.attrib for s in tree.iter("OverallResultsCases")])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_root.resolve() / uuid.uuid4().hex
    output.mkdir(parents=True)
    report = dict(schema_version=1, evidence_class="upstream-original-synthetic-host-tests",
                  guest_executed=False, script_sha256=sha(__file__), binary_sha256=sha(args.binary),
                  neighboring_libraries={p.name: sha(p) for p in sorted(args.binary.parent.glob("*.so*")) if p.is_file()},
                  selection=SPEC, isolated_processes=True, cases=[])
    print(json.dumps(dict(output=str(output), guest_executed=False)), flush=True)
    try:
        listing = subprocess.run([str(args.binary.resolve()), SPEC, "--list-tests", "--reporter", "xml"],
                                 capture_output=True, timeout=30, check=True)
        (output / "listing.xml").write_bytes(listing.stdout)
        names = [c.findtext("Name") for c in ET.fromstring(listing.stdout).findall("TestCase")]
        if not names or len(names) != len(set(names)) or any(not n for n in names):
            raise ValueError("empty or duplicate test selection")
        for index, name in enumerate(names):
            lane = output / str(index)
            lane.mkdir()
            (lane / "tmp").mkdir()
            (lane / "config").mkdir()
            env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                       XDG_CONFIG_HOME=str(lane / "config"), TMPDIR=str(lane / "tmp"))
            start = time.monotonic()
            with (lane / "stdout.log").open("wb") as log:
                result = subprocess.run([str(args.binary.resolve()), exact_filter(name), "--reporter", "xml",
                                         "--out", str(lane / "results.xml")], cwd=lane, env=env,
                                        stdout=log, stderr=subprocess.STDOUT, timeout=45)
            checked = summarize(lane / "results.xml")
            if checked["cases"] != 1:
                raise ValueError(f"isolated filter selected {checked['cases']} cases: {index}")
            report["cases"].append(dict(name=name, returncode=result.returncode,
                                        seconds=time.monotonic()-start, **checked))
            (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        report["failed_cases"] = sum(c["returncode"] != 0 or bool(c["failed"]) for c in report["cases"])
        report["status"] = "FAIL" if report["failed_cases"] else "PASS"
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(dict(status=report["status"], cases=len(names), failed=report["failed_cases"])))
        return int(bool(report["failed_cases"]))
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as error:
        report.update(status="ERROR", error=str(error))
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        parser.exit(2, f"host checks failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
