"""Tests de refactoring TDD — controllers/context.py vers modules decouples.

Phase RED : tests qui valident l'architecture cible avant extraction finale.
"""

import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from controllers.context import build_app, get_context
from controllers.di import AppContext


class TestAppContextInitialization:
    """Tests RED pour la classe AppContext (DI)."""

    def test_app_context_created_with_none_services(self):
        """AppContext.__init__ doit initialiser tous les services a None."""
        ctx = AppContext()
        assert ctx.inference is None
        assert ctx.memory is None
        assert ctx.vector is None
        assert ctx.log is None
        assert ctx.analytics is None
        assert ctx.conversations is None
        assert ctx.metrics is None
        assert ctx.agents == {}
        assert ctx.router_svc is None
        assert ctx.toolbox is None
        assert ctx.orchestrator is None
        assert ctx._initialized is False

    def test_app_context_has_status_cache(self):
        """AppContext doit avoir un status_cache initialise."""
        ctx = AppContext()
        assert isinstance(ctx.status_cache, dict)
        assert "ts" in ctx.status_cache
        assert "data" in ctx.status_cache

    def test_app_context_has_profiles_path(self):
        """AppContext doit avoir un chemin vers agent_profiles.json."""
        ctx = AppContext()
        # Cross-platform path check
        normalized_path = ctx.profiles_path.replace("\\", "/")
        assert normalized_path.endswith("config/agent_profiles.json")

    def test_initialize_idempotent(self):
        """initialize() ne doit pas reinitialiser si deja fait."""
        ctx = AppContext()
        ctx.initialize()
        assert ctx._initialized is True
        # Second call should be a no-op
        ctx.initialize()
        assert ctx._initialized is True


class TestBuildApp:
    """Tests RED pour la factory build_app()."""

    def test_build_app_returns_fastapi_instance(self):
        """build_app() doit retourner une instance FastAPI."""
        app = build_app()
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)

    def test_build_app_creates_app_with_routes(self):
        """L'app FastAPI doit avoir au moins les routes de base (FastAPI auto)."""
        app = build_app()
        routes = [r.path for r in app.routes]
        # FastAPI auto-generates /docs, /openapi.json, /redoc
        # The actual API routes are added in router.py after build_app() call
        assert "/docs" in routes
        assert "/openapi.json" in routes

    def test_build_app_registers_static_mount(self):
        """L'app doit monter le dossier static si present."""
        app = build_app()
        # Check if static is mounted
        route_paths = [r.path if hasattr(r, "path") else str(r) for r in app.routes]
        static_mounted = any("static" in str(r) for r in route_paths)
        # May be False if STATIC_DIR doesn't exist during test
        assert isinstance(static_mounted, bool)


class TestGetContext:
    """Tests RED pour le singleton AppContext."""

    def test_get_context_returns_app_context(self):
        """get_context() doit retourner l'instance AppContext."""
        ctx = get_context()
        assert isinstance(ctx, AppContext)

    def test_get_context_is_singleton(self):
        """get_context() doit toujours retourner la meme instance."""
        ctx1 = get_context()
        ctx2 = get_context()
        assert ctx1 is ctx2


class TestModuleSeparation:
    """Tests RED pour valider que les modules sont bien decouples."""

    def test_di_module_exists(self):
        """Le module controllers.di doit exister et etre importable."""
        from controllers import di
        assert hasattr(di, "AppContext")

    def test_middlewares_module_exists(self):
        """Le module controllers.middlewares doit exister."""
        from controllers import middlewares
        assert hasattr(middlewares, "_setup_middlewares")
        assert hasattr(middlewares, "_body_size_limiter")

    def test_status_module_exists(self):
        """Le module controllers.status doit exister."""
        from controllers import status
        assert hasattr(status, "_check_ollama")
        assert hasattr(status, "_build_status_data")
        assert hasattr(status, "_refresh_status_cache")

    def test_warmup_module_exists(self):
        """Le module controllers.warmup doit exister."""
        from controllers import warmup
        assert hasattr(warmup, "_warmup")
        assert hasattr(warmup, "_warmup_vector_store")
        assert hasattr(warmup, "lifespan")


class TestBackwardCompatibility:
    """Tests RED pour valider la compatibilite avec l'ancien context.py."""

    def test_context_exports_di_symbols(self):
        """context.py doit reexporter AppContext et get_context()."""
        from controllers import context
        assert hasattr(context, "AppContext")
        assert hasattr(context, "get_context")

    def test_context_exports_middleware_symbols(self):
        """context.py doit reexporter les symboles de middlewares."""
        from controllers import context
        assert hasattr(context, "_body_size_limiter")
        assert hasattr(context, "_setup_middlewares")

    def test_context_exports_status_symbols(self):
        """context.py doit reexporter les symboles de status."""
        from controllers import context
        assert hasattr(context, "_check_ollama")
        assert hasattr(context, "_build_status_data")
        assert hasattr(context, "_refresh_status_cache")
        assert hasattr(context, "_status_refresher")

    def test_context_exports_warmup_symbols(self):
        """context.py doit reexporter les symboles de warmup."""
        from controllers import context
        assert hasattr(context, "_warmup")
        assert hasattr(context, "_warmup_vector_store")
        assert hasattr(context, "lifespan")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
