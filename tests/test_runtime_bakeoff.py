# SPDX-License-Identifier: GPL-3.0-only
"""Include game-free experiment guards in the standard contributor/CI suite."""
from pathlib import Path
import unittest


def load_tests(loader, standard_tests, pattern):
    # A fresh loader gives the independent directory its own import root.
    return unittest.TestLoader().discover(str(Path(__file__).resolve().parents[1] /
                                              "experiments/runtime-bakeoff/tests"), pattern="test_*.py")
