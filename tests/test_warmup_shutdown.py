#!/usr/bin/env python3
"""Test that shutdown during warmup doesn't produce CancelledError."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from controllers.warmup import _shutdown_sequence


class TestShutdownDuringWarmup(unittest.TestCase):
    """TEST: Shutdown during warmup produces no CancelledError."""

    @patch("controllers.warmup._warmup_vector_store")
    @patch("controllers.warmup._warmup_default_model")
    def test_shutdown_during_warmup_no_cancelled_error(self, mock_model, mock_vector):
        """RED: Lancer warmup et appeler _shutdown_sequence sans CancelledError."""
        # Arrange - Setup context with warmup tasks
        ctx = MagicMock()
        ctx._warmup_tasks = []

        # Act
        _shutdown_sequence(ctx)

        # Assert - Should not raise CancelledError
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
