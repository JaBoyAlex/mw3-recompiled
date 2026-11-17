#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Run game-free contributor checks with Python 3.11+, CMake 3.25+ and a C++20 compiler."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    print("+ " + " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", choices=("Debug", "Release"), default="Debug")
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--ctest", default="ctest")
    parser.add_argument("--generator", default="Visual Studio 17 2022" if os.name == "nt" else "Ninja")
    parser.add_argument("--sanitizers", action="store_true")
    args = parser.parse_args()
    folder = ROOT / "out" / (args.config.lower() + ("-asan" if args.sanitizers else ""))
    try:
        run(sys.executable, "tools/project.py", "validate")
        run(sys.executable, "tools/check_repository.py")
        run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v")
        configure = [args.cmake, "-S", ROOT, "-B", folder, "-G", args.generator,
                     "-DBUILD_TESTING=ON", f"-DMW3_SANITIZERS={'ON' if args.sanitizers else 'OFF'}"]
        if args.generator.startswith("Visual Studio"):
            configure += ["-A", "x64"]
        else:
            configure += [f"-DCMAKE_BUILD_TYPE={args.config}"]
        run(*configure)
        run(args.cmake, "--build", folder, "--config", args.config, "--parallel", "2")
        run(args.ctest, "--test-dir", folder, "-C", args.config, "--output-on-failure")
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: game-free checks; real MW3 execution NOT TESTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
