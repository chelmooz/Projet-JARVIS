"""Test de contrat d'import — valide que tous les modules critiques sont importables.

Ce test DOIT échouer tant que le package `models/` est ignoré par .gitignore
(ImportError sur les DTO Result, Pipeline, PipeStep, Task).
Une fois A2-A3 faits, ce test passe et devient le verrou CI (A7).
"""

import pytest


def test_import_models_dto():
    """Les DTO métier de models/__init__.py sont importables."""
    from models import AgentProfile, Conversation, Document, Message, OnError, Pipeline, PipeStep, Result, Task

    assert Result is not None
    assert Pipeline is not None
    assert PipeStep is not None
    assert Task is not None
    assert AgentProfile is not None
    assert Conversation is not None
    assert Message is not None
    assert Document is not None
    assert OnError is not None


def test_import_ports_uses_models_result():
    """ports/__init__.py importe Result depuis models (pas de duplication)."""
    from models import Result as ModelsResult
    from ports import Result as PortsResult

    assert PortsResult is ModelsResult


def test_import_services_pipeline():
    """services.pipeline.PipelineService est importable."""
    from services.pipeline import PipelineService

    assert PipelineService is not None


def test_import_services_router():
    """services.router.AgentRouter est importable."""
    from services.router import AgentRouter

    assert AgentRouter is not None


def test_import_controllers_router():
    """controllers.router.create_app est importable."""
    from controllers.router import create_app

    assert create_app is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
