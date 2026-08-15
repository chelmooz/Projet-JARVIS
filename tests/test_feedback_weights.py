#!/usr/bin/env python3
"""Test that FEEDBACK_WEIGHTS is defined only once."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestFeedbackWeightsDefinedOnce(unittest.TestCase):
    """TEST: FEEDBACK_WEIGHTS is defined only once."""

    def test_feedback_weights_defined_once(self):
        """RED: Vérifier qu'il n'y a qu'une seule définition de FEEDBACK_WEIGHTS."""
        # Read the constants.py file and check for duplicate definitions
        with open(os.path.join(os.path.dirname(__file__), "..", "config", "constants.py")) as f:
            content = f.read()

        # Count occurrences of "FEEDBACK_WEIGHTS" assignment
        # Look for assignments like: FEEDBACK_WEIGHTS = ...
        assignments = [line for line in content.split("\n") if "FEEDBACK_WEIGHTS" in line and "=" in line]

        # Should have exactly 1 assignment
        self.assertEqual(
            len(assignments), 1, f"Expected 1 definition of FEEDBACK_WEIGHTS, got {len(assignments)}: {assignments}"
        )


if __name__ == "__main__":
    unittest.main()
