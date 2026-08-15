#!/usr/bin/env python3
"""Test that select_model raises ValueError when no model available."""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.selector import select_model


class TestSelectModelRaises(unittest.TestCase):
    """TEST: select_model raises ValueError when no model available."""

    def test_select_model_raises_when_no_model_available(self):
        """RED: Mock inference avec first_available() → None, select_model doit lever ValueError."""
        # Arrange - Mock inference where resolve_model returns None and first_available returns None
        mock_inference = MagicMock()
        mock_inference.resolve_model.return_value = None  # Important: resolve_model returns None
        mock_inference.first_available.return_value = None

        # Act & Assert
        try:
            select_model("dev", mock_inference)
            self.fail("Expected ValueError to be raised")
        except ValueError as e:
            self.assertIn("aucun modèle", str(e).lower())

    def test_select_model_with_model_available(self):
        """GREEN: Quand un modèle est disponible via resolve_model, il doit être sélectionné."""
        # Arrange
        mock_inference = MagicMock()
        mock_inference.resolve_model.return_value = "hf.co/ibm-granite/granite-4.1-8b-instruct-GGUF:Q4_K_M"

        # Act
        result = select_model("dev", mock_inference)

        # Assert
        self.assertEqual(result, "hf.co/ibm-granite/granite-4.1-8b-instruct-GGUF:Q4_K_M")

    def test_select_model_with_fallback(self):
        """GREEN: Quand aucun modèle spécifique mais un fallback disponible, il doit être sélectionné."""
        # Arrange
        mock_inference = MagicMock()
        mock_inference.resolve_model.return_value = None  # Specific model not found
        mock_inference.first_available.return_value = "hf.co/ibm-granite/granite-4.1-8b-instruct-GGUF:Q4_K_M"

        # Act
        result = select_model("dev", mock_inference)

        # Assert
        self.assertEqual(result, "hf.co/ibm-granite/granite-4.1-8b-instruct-GGUF:Q4_K_M")

    def test_select_model_no_inference(self):
        """GREEN: Quand inference est None, ValueError doit être levé."""
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            select_model("dev", None)

        self.assertIn("aucun modèle", str(context.exception).lower())


if __name__ == "__main__":
    unittest.main()
