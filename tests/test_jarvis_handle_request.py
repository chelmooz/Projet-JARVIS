"""Tests de caractérisation pour ``controllers/routes/jarvis.py:handle_request`` (Lot E5).

Complète ``tests/test_api_chat.py`` (Lot 3.2, déjà vert : routage, nominal,
422, 413) avec les branches non couvertes, AVANT tout refactor (Lot E6) :
- mode hors-ligne (préférences) court-circuite l'orchestrateur ;
- orchestrateur non initialisé -> 503 ;
- exception non gérée -> 500, réponse JSON stable (pas de leak de stacktrace) ;
- image base64 invalide -> silencieusement ignorée (``image=None``), pas de 4xx ;
- négociation SSE (``Accept: text/event-stream``) -> flux ``token``... puis ``done``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from controllers.router import create_app
from services.router import AgentRouter


class _RoutingOrchestrator:
    """Orchestrateur factice : délègue le routage au vrai AgentRouter."""

    def __init__(self, router: AgentRouter) -> None:
        self._router = router
        self.calls: list[str] = []

    async def handle_request(self, task: str, image: str | None = None, conv_id: str | None = None) -> dict[str, Any]:
        self.calls.append(task)
        agent = self._router.select_agent(task)
        return {"response": f"routed:{agent}", "agent": agent, "model": "fake"}


class _CrashingOrchestrator:
    """Orchestrateur factice : lève toujours une exception (chemin d'erreur 500)."""

    async def handle_request(self, task: str, image: str | None = None, conv_id: str | None = None) -> dict[str, Any]:
        raise RuntimeError("boom")


class _StreamingOrchestrator:
    """Orchestrateur factice pour le chemin SSE : résultat déterministe, pas de vrais tokens."""

    async def handle_request(self, task: str, image: str | None = None, conv_id: str | None = None) -> dict[str, Any]:
        return {"response": "streamed reply", "agent": "dev", "model": "fake"}


class _StreamCapableInference:
    """Double minimal exposant l'API de streaming utilisée par ``_handle_request_streamed``."""

    def __init__(self) -> None:
        self.sink_set = False
        self.sink_cleared = False

    def set_stream_sink(self, sink: Any) -> None:
        self.sink_set = True

    def clear_stream_sink(self) -> None:
        self.sink_cleared = True


class _Analytics:
    def track_query(self, **_: object) -> None:
        return None


class _Conversations:
    def add_message(self, *args: object, **kwargs: object) -> None:
        return None


def _build_client(
    monkeypatch: pytest.MonkeyPatch,
    orchestrator: Any,
    *,
    inference: Any = None,
    offline: bool = False,
) -> TestClient:
    monkeypatch.setattr("controllers.routes.jarvis.read_preferences", lambda: {"offline": offline})
    app = create_app()
    app.state.context = SimpleNamespace(
        orchestrator=orchestrator,
        analytics=_Analytics(),
        conversations=_Conversations(),
        inference=inference,
    )
    return TestClient(app)


class TestHandleRequestOffline:
    def test_offline_mode_short_circuits_orchestrator(self, monkeypatch: pytest.MonkeyPatch) -> None:
        orchestrator = _RoutingOrchestrator(AgentRouter())
        client = _build_client(monkeypatch, orchestrator, offline=True)

        resp = client.post("/api/jarvis", json={"task": "quoi que ce soit"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["agent"] == "system"
        assert body["backend"] == "offline"
        # L'orchestrateur n'est jamais sollicité en mode hors-ligne.
        assert orchestrator.calls == []


class TestHandleRequestNotReady:
    def test_orchestrator_none_returns_503(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _build_client(monkeypatch, orchestrator=None)

        resp = client.post("/api/jarvis", json={"task": "hello"})

        assert resp.status_code == 503
        body = resp.json()
        assert body["agent"] == "system"
        assert "error" in body


class TestHandleRequestErrorPath:
    def test_orchestrator_exception_returns_500_generic_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Une exception dans l'orchestrateur ne doit jamais fuiter de détail interne."""
        client = _build_client(monkeypatch, orchestrator=_CrashingOrchestrator())

        resp = client.post("/api/jarvis", json={"task": "hello"})

        assert resp.status_code == 500
        body = resp.json()
        assert body == {"error": "Erreur interne du service", "agent": "system", "model": "unknown"}


class TestHandleRequestImageValidation:
    def test_invalid_base64_image_is_silently_dropped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Image invalide : la requête aboutit quand même (200), l'image est juste ignorée."""
        orchestrator = _RoutingOrchestrator(AgentRouter())
        client = _build_client(monkeypatch, orchestrator)

        resp = client.post("/api/jarvis", json={"task": "analyse ceci", "image": "not-valid-base64!!"})

        assert resp.status_code == 200
        assert orchestrator.calls == ["analyse ceci"]


class TestHandleRequestStreaming:
    def test_sse_negotiation_returns_event_stream(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``Accept: text/event-stream`` déclenche le flux SSE (tokens puis done)."""
        inference = _StreamCapableInference()
        client = _build_client(monkeypatch, _StreamingOrchestrator(), inference=inference)

        with client.stream(
            "POST",
            "/api/jarvis",
            json={"task": "stream ceci"},
            headers={"accept": "text/event-stream"},
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            raw = "".join(resp.iter_text())

        assert "event: done" in raw
        assert "streamed reply" in raw
        assert inference.sink_set is True
        assert inference.sink_cleared is True

    def test_non_streaming_request_does_not_touch_stream_sink(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sans négociation SSE, l'inférence n'est jamais sollicitée pour le streaming."""
        inference = _StreamCapableInference()
        client = _build_client(monkeypatch, _RoutingOrchestrator(AgentRouter()), inference=inference)

        resp = client.post("/api/jarvis", json={"task": "hello"})

        assert resp.status_code == 200
        assert inference.sink_set is False
        assert inference.sink_cleared is False
