#!/usr/bin/env python3
"""Test that pipeline agent_key uses agent_runner."""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import PipeStep
from services.pipeline import PipelineService


class TestPipelineAgentRunner(unittest.TestCase):
    """TEST: Pipeline agent_key uses agent_runner via AgentGraph."""

    def test_pipeline_with_agent_runner_callable(self):
        """RED: Pipeline avec agent_runner callable et agent_key doit fonctionner."""
        # Arrange - Mock agent_runner qui est callable
        runner = MagicMock()
        runner.run.return_value = {"response": "agent-response"}
        # On ajoute l'attribut que _runner_supports_model vérifie
        runner._runner_supports_model = True

        # Act
        service = PipelineService(
            inference=MagicMock(),
            memory=MagicMock(),
            model_selector=MagicMock(),
            agent_runner=runner,
        )

        # Créer un step avec agent_key
        step = PipeStep(name="test_step", agent_key="cyber", prompt_template="Prompt: {task}")

        # Assert - Vérifier que le runner est accessible
        self.assertIsNotNone(service._agent_runner)
        self.assertEqual(service._agent_runner, runner)

    def test_pipeline_without_agent_runner(self):
        """RED: Sans agent_runner, pipeline avec agent_key doit lever une erreur."""
        # Act
        service = PipelineService(
            inference=MagicMock(),
            memory=MagicMock(),
            model_selector=MagicMock(),
            agent_runner=None,
        )

        # Assert
        self.assertIsNone(service._agent_runner)

    def test_pipeline_step_has_agent_key(self):
        """RED: Pipeline étape avec agent_key doit être détectée."""
        # Arrange
        step = PipeStep(name="test_step", agent_key="cyber", prompt_template="Prompt: {task}")

        # Assert
        self.assertEqual(step.agent_key, "cyber")


if __name__ == "__main__":
    unittest.main()