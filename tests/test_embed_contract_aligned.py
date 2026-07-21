"""Tests — contrat embed align (audit DevOps 3.2 / 5.4).

Les deux contrats couvrent des couches differentes (facade InferencePort vs
backend LLMAdapter) : ce n'est pas un doublon a fusionner, mais leurs signatures
`embed` divergeaient (`embed(text)` vs `embed(text, model=None)`). Apres alignement,
les trois (Port, InferenceService, OllamaAdapter) acceptent `model` optionnel.
"""
import inspect

from ports import InferencePort
from services.adapters.ollama_adapter import OllamaAdapter
from services.inference import InferenceService


def test_embed_signatures_accept_optional_model():
    sig_port = inspect.signature(InferencePort.embed)
    assert "model" in sig_port.parameters

    sig_svc = inspect.signature(InferenceService.embed)
    assert "model" in sig_svc.parameters

    sig_adapter = inspect.signature(OllamaAdapter.embed)
    assert "model" in sig_adapter.parameters
