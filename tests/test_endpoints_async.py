"""Tests Fix #9 — Vérifie que les endpoints I/O-bound sont async def."""
import inspect

import pytest


class TestEndpointsAsync:

    def test_jarvis_handle_request_is_async(self):
        """POST /api/jarvis (handle_request) doit être async def."""
        from controllers.routes.jarvis import handle_request
        assert inspect.iscoroutinefunction(handle_request), (
            "handle_request doit être async def (I/O-bound: appel Ollama)"
        )

    def _check_is_async(self, module_path: str, func_name: str, reason: str):
        """Helper: vérifie qu'une fonction est un coroutine."""
        import importlib
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name, None)
        assert func is not None, f"{module_path}.{func_name} introuvable"
        assert inspect.iscoroutinefunction(func), (
            f"{func_name} doit être async def ({reason})"
        )

    def test_ingest_intentionally_sync(self):
        """ingest_documents reste sync par choix : I/O disque + vector.index_batch()
        bloquant. Le rendre async def sans I/O async sous-jacent ne résoud rien et
        casserait les appelants. Voir AUDIT-P3.7 (endpoints bloquants laissés sync)."""
        self._check_is_sync(
            "controllers.routes.documents", "ingest_documents",
            "écriture disque bloquante via vector.index_batch()",
        )

    def test_pipeline_run_intentionally_sync(self):
        """run_pipeline reste sync : appels LLM distants bloquants. Choix AUDIT-P3.7."""
        self._check_is_sync(
            "controllers.routes.pipelines", "run_pipeline",
            "exécute des appels LLM distants",
        )

    def test_file_read_intentionally_sync(self):
        """read_file reste sync : lecture disque bloquante. Choix AUDIT-P3.7."""
        self._check_is_sync(
            "controllers.routes.files", "read_file",
            "lit des fichiers sur le disque",
        )

    def _check_is_sync(self, module_path: str, func_name: str, reason: str):
        """Helper: vérifie qu'une fonction reste sync (I/O bloquant délibéré)."""
        import importlib

        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name, None)
        assert func is not None, f"{module_path}.{func_name} introuvable"
        assert not inspect.iscoroutinefunction(func), (
            f"{func_name} doit rester sync ({reason})"
        )


# ---------------------------------------------------------------------------
# AUDIT-P3.7 — Conversion des GET simples sync -> async def
# ---------------------------------------------------------------------------


class TestGetEndpointsConvertedToAsync:
    """Vérifie que les GET simples (sans I/O bloquant) sont async def."""

    # (module, nom_fonction, raison)
    _CONVERTED = [
        ("controllers.router", "get_backend", "retourne une valeur en mémoire"),
        ("controllers.router", "get_metrics", "compteurs mémoire + psutil"),
        ("controllers.routes.agents", "vision_info", "documentation statique"),
        ("controllers.routes.analytics", "get_analytics", "stats en mémoire"),
        ("controllers.routes.analytics", "get_peak", "stats en mémoire"),
        ("controllers.routes.conversations", "list_conversations", "index en mémoire"),
        ("controllers.routes.files", "list_authorized", "ensemble en mémoire"),
        ("controllers.routes.jarvis", "jarvis_info", "documentation statique"),
        ("controllers.routes.documents", "vectorize_stats", "stats en mémoire"),
        ("controllers.routes.pipelines", "list_pipelines", "pipelines en mémoire"),
    ]

    @pytest.mark.parametrize("_case", _CONVERTED)
    def test_converted_are_async(self, _case):
        module_path, func_name, reason = _case
        import importlib
        # controllers.router exécute build_app() à l'import : on court-circuite
        # l'init des services (réseau/disque) pour ne vérifier que la signature.
        if module_path == "controllers.router":
            import controllers.context as _ctx_mod
            _ctx_mod._ctx._initialized = True
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name, None)
        assert func is not None, f"{module_path}.{func_name} introuvable"
        assert inspect.iscoroutinefunction(func), (
            f"{func_name} doit être async def ({reason})"
        )


class TestGetEndpointsLeftSync:
    """Vérifie que les GET à I/O bloquant restent sync (commentés)."""

    _LEFT_SYNC = [
        ("controllers.router", "list_models", "appel réseau Ollama bloquant"),
        ("controllers.router", "index", "lecture disque statique"),
        ("controllers.router", "serve_static", "lecture disque statique"),
        ("controllers.router", "get_status", "appel réseau Ollama bloquant"),
        ("controllers.routes.agents", "list_profiles", "lecture fichier JSON"),
        ("controllers.routes.analytics", "list_cyber_workflows", "lecture fichier JSON"),
        ("controllers.routes.conversations", "get_conversation", "lecture fichier JSON"),
        ("controllers.routes.diagnostic", "get_diagnostic", "inspection système bloquante"),
        ("controllers.routes.skills", "list_skills", "lecture fichier JSON"),
        ("controllers.routes.skills", "skills_context", "lecture fichier JSON"),
        ("controllers.routes.settings", "get_settings", "lecture fichier JSON"),
        ("controllers.routes.beta_dashboard", "get_beta_dashboard", "FileResponse disque"),
        ("controllers.routes.quality_audit", "run_audit", "audit disque/CPU bloquant"),
        ("controllers.routes.kill_coding", "analyze_file", "analyse disque/CPU"),
        ("controllers.routes.kill_coding", "analyze_project", "audit disque/CPU"),
        ("controllers.routes.kill_coding", "check_test", "parcours disque"),
        ("controllers.routes.code_review", "review_file", "analyse disque/CPU"),
        ("controllers.routes.code_review", "review_project", "analyse disque/CPU"),
        ("controllers.routes.documents", "search_documents", "recherche vectorielle CPU-bound"),
    ]

    def test_left_sync_are_sync(self):
        pass

    @pytest.mark.parametrize("_case", _LEFT_SYNC)
    def test_left_sync_are_sync_param(self, _case):
        module_path, func_name, reason = _case
        import importlib
        if module_path == "controllers.router":
            import controllers.context as _ctx_mod
            _ctx_mod._ctx._initialized = True
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name, None)
        assert func is not None, f"{module_path}.{func_name} introuvable"
        assert not inspect.iscoroutinefunction(func), (
            f"{func_name} doit rester sync ({reason})"
        )


class TestConvertedGetEndpointsBehavior:
    """Smoke test : les GET convertis répondent 200 via TestClient."""

    @pytest.fixture(autouse=True)
    def _restore_context(self):
        """Restaure l'état global du contexte apres le test.

        _make_client mute ctx._ctx + les globals module (_sync_module_globals) ;
        sans restauration, le fake fuite vers les autres modules de test
        (ex: test_memory_leak -> /api/status -> vector.is_healthy()).
        """
        import controllers.context as ctx
        _ctx = ctx._ctx
        keys = ("_initialized", "conversations", "vector", "metrics", "analytics")
        saved = {k: getattr(_ctx, k, None) for k in keys}
        yield
        for k, v in saved.items():
            setattr(_ctx, k, v)
        ctx._sync_module_globals(_ctx)

    def _make_client(self):
        from unittest.mock import MagicMock

        import controllers.context as ctx

        class FakeConv:
            def __init__(self):
                self._index = {"conversations": [{"id": "c1", "title": "t"}]}
            def list_all(self):
                return self._index["conversations"]

        class FakeVector:
            def stats(self):
                return {"total": 0, "embedded": 0, "pending": 0}
            def is_healthy(self):
                return True

        ctx._ctx._initialized = True
        ctx._ctx.conversations = FakeConv()
        ctx._ctx.vector = FakeVector()
        ctx._ctx.metrics = MagicMock()
        ctx._ctx.metrics.get_metrics.return_value = {"uptime_seconds": 1}
        ctx._ctx.analytics = MagicMock()
        ctx._ctx.analytics.get_stats.return_value = {"total_queries": 0}
        ctx._ctx.analytics.get_most_used.return_value = {"top_agent": None}
        ctx._sync_module_globals(ctx._ctx)

        from fastapi.testclient import TestClient

        from controllers.router import app
        return TestClient(app)

    def test_get_endpoints_return_200(self):
        client = self._make_client()
        endpoints = [
            "/api/backend",
            "/api/jarvis",
            "/api/metrics",
            "/api/vision",
            "/api/analytics",
            "/api/analytics/peak",
            "/api/files/authorized",
            "/api/conversations",
            "/api/vectorize",
            "/api/pipelines",
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code == 200, f"{ep} -> {resp.status_code}: {resp.text}"
            assert resp.json() is not None

