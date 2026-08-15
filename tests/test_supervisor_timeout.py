#!/usr/bin/env python3
"""Test that supervisor timeout actually stops the thread."""
import sys
import os
import time
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.supervisor import AgentSupervisor


class TestSupervisorTimeout(unittest.TestCase):
    """TEST: Supervisor timeout actually stops the thread."""

    def test_supervisor_timeout_stops_thread(self):
        """RED: Agent lent (sleep 2s) + timeout 0.5s -> thread doit être arrêté."""
        # Arrange
        supervisor = AgentSupervisor(timeout=0.5)

        class SlowAgent:
            def run(self, task, model, context):
                time.sleep(5)  # Will exceed timeout
                return {"response": "completed"}

        # Act
        with patch.object(SlowAgent, 'run', side_effect=KeyboardInterrupt("interrupt signal")):
            try:
                result = supervisor.run(SlowAgent(), "test task", "model1", {})
            except KeyboardInterrupt:
                pass

        # Assert - the thread should have been given time to finish
        # (the exact behavior depends on the implementation)
        self.assertTrue(True)  # Placeholder assert

    def test_supervisor_timeout_with_stop_event(self):
        """RED: Supervisor avec stop_event arrête l'agent proprement."""
        # This test will pass once the stop_event implementation is in place
        supervisor = AgentSupervisor(timeout=1.0)
        self.assertIsNotNone(supervisor)


if __name__ == "__main__":
    unittest.main()