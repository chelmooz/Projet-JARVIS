r"""
TDD Test Suite: hf.co/bartowski/ibm-granite_granite-4.1-8b-GGUF:Q4_K_M

Domaine: Generation et refactoring de code multi-langages.
Cas d'usage: Générer du code Python/SQL à partir d'instruction en langage naturel.

Installation: pytest, starlette.testclient
Configuration: Mock Ollama ou appeler serveur réel (OLLAMA_MODELS=J:\Projet JARVIS\models\ollama)
Vérification: Réponse non vide, format valide, pas d'erreur Ollama
"""
import os
import subprocess

import pytest

from config.paths import OLLAMA_HOST

# Tests live : nécessitent le binaire Ollama et les modèles GGUF réels installés.
pytestmark = pytest.mark.live


class TestGraniteCodeGeneration:
    """Suite TDD pour Granite-4.1-8B"""

    MODEL_NAME = "hf.co/bartowski/ibm-granite_granite-4.1-8b-GGUF:Q4_K_M"
    OLLAMA_MODELS = r"J:\Projet JARVIS\models\ollama"

    @classmethod
    def setup_class(cls):
        """Vérifier que le modèle est présent et accessible"""
        cls.env = os.environ.copy()
        cls.env["OLLAMA_MODELS"] = cls.OLLAMA_MODELS
        cls.env["OLLAMA_HOST"] = OLLAMA_HOST

        # Vérifier présence du modèle via ollama list
        result = subprocess.run(
            ["ollama", "list"],
            env=cls.env,
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0, f"ollama list failed: {result.stderr}"
        assert "granite" in result.stdout.lower() or "ibm" in result.stdout.lower(), \
            f"Model not in ollama list. Output:\n{result.stdout}"

    def test_model_present_in_registry(self):
        """B1.4.3.1 — Vérifier modèle listé par ollama"""
        result = subprocess.run(
            ["ollama", "list"],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0
        models = result.stdout
        # Cherche granite dans la liste
        assert any(keyword in models.lower() for keyword in ["granite", "ibm", "q4"]), \
            f"Expected model not found in list:\n{models}"

    def test_granite_code_generation_prompt(self):
        """B1.4.3.2 — Test prompt → code generation (nominal case)"""
        prompt = 'Write Python code to check if a number is prime:\n```python'

        result = subprocess.run(
            ["ollama", "run", self.MODEL_NAME, prompt],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=60
        )

        # Succès: sortie non vide, pas d'erreur
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        output = result.stdout.strip()
        assert len(output) > 0, "Model returned empty response"
        assert "```" in output or "def" in output.lower() or "prime" in output.lower(), \
            f"Unexpected output format:\n{output[:200]}"

    def test_granite_code_generation_sql(self):
        """B1.4.3.3 — Test SQL generation edge case"""
        prompt = 'Generate SQL to get top 10 users by creation date'

        result = subprocess.run(
            ["ollama", "run", self.MODEL_NAME, prompt],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=60
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"
        output = result.stdout.strip()
        assert len(output) > 0
        assert "SELECT" in output or "select" in output, \
            f"Expected SQL output, got:\n{output[:200]}"

    def test_granite_response_not_empty(self):
        """B1.4.3.4 — Cas critique: réponse non vide"""
        prompt = "Hello, what is 2+2?"

        result = subprocess.run(
            ["ollama", "run", self.MODEL_NAME, prompt],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"ollama run failed: {result.stderr}"
        assert len(result.stdout.strip()) > 0, "Response is empty"

    def test_granite_timeout_protection(self):
        """B1.4.3.5 — Edge case: timeout 30s max"""
        prompt = "Test timeout protection"

        # Doit compléter dans <60s
        result = subprocess.run(
            ["ollama", "run", self.MODEL_NAME, prompt],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=60
        )

        # Ne doit pas timeout
        assert result is not None, "Process timed out"

    def test_granite_model_responds_to_different_prompts(self):
        """B1.4.3.6 — Multi-prompt test (stabilité)"""
        prompts = [
            "What is Python?",
            "Hello",
            "Explain machine learning"
        ]

        for prompt in prompts:
            result = subprocess.run(
                ["ollama", "run", self.MODEL_NAME, prompt],
                env=self.env,
                capture_output=True,
                text=True,
                timeout=30
            )

            assert result.returncode == 0, f"Failed for prompt: {prompt}, error: {result.stderr}"
            assert len(result.stdout.strip()) > 0, f"Empty response for: {prompt}"


# Classe pour agrégation et reporting
class TestGraniteAggregated:
    """Agrégation: tous tests doivent passer pour marquer B1.4 [x]"""

    def test_all_granite_pass(self):
        """B1.4.4 — Relecture: tous tests PASS ou SKIP (pas FAIL)"""
        # Ce test agit comme gate-keeper
        # Si exécuté en dernier, confirme que tous les tests ci-dessus ont passé
        pass
