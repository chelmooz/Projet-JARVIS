"""Tests de caractérisation pour ``controllers/warmup.py:lifespan`` (Lot E3).

Verrouille le comportement actuel AVANT tout refactor (extraction
``_startup_sequence`` / ``_shutdown_sequence``, Lot E4) :
- démarrage dégradé sans inférence/vecteur configurés (aucune exception) ;
- warmup vectoriel et modèle lancés en tâches de fond, échecs journalisés
  sans jamais propager (fail-safe documenté dans le module) ;
- file d'ingestion démarrée/arrêtée seulement si présente sur le contexte ;
- arrêt : annulation des tâches de warmup en cours, fermeture de l'inférence
  et flush vectoriel tolérants aux exceptions (log, pas de raise).

Le fichier ``memory/.jarvis_token`` est ancré sur ``__file__`` du module
(pas de paramètre injectable) : on monkeypatch ``controllers.warmup.__file__``
pour rediriger l'écriture sous ``tmp_path`` et respecter la règle « aucun
disque hors tmp_path ».
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI

import controllers.warmup as warmup_module
from controllers.warmup import lifespan


class FakeVector:
    def __init__(self, *, fail_preload: bool = False, fail_consolidate: bool = False, fail_flush: bool = False) -> None:
        self.preload_called = False
        self.consolidate_called = False
        self.flush_called = False
        self._fail_preload = fail_preload
        self._fail_consolidate = fail_consolidate
        self._fail_flush = fail_flush

    def preload(self) -> None:
        self.preload_called = True
        if self._fail_preload:
            raise RuntimeError("preload boom")

    def consolidate(self) -> None:
        self.consolidate_called = True
        if self._fail_consolidate:
            raise RuntimeError("consolidate boom")

    def flush(self) -> None:
        self.flush_called = True
        if self._fail_flush:
            raise RuntimeError("flush boom")


class FakeInference:
    def __init__(self, *, available: bool = True, fail_query: bool = False, fail_close: bool = False) -> None:
        self.query_called = False
        self.close_called = False
        self._available = available
        self._fail_query = fail_query
        self._fail_close = fail_close

    def is_available(self, model: str) -> bool:
        return self._available

    def query(self, prompt: str, model: str) -> str:
        self.query_called = True
        if self._fail_query:
            raise RuntimeError("query boom")
        return "ok"

    def close(self) -> None:
        self.close_called = True
        if self._fail_close:
            raise RuntimeError("close boom")


class FakeIngestQueue:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class FakeStopEvent:
    def __init__(self) -> None:
        self.is_set = False

    def set(self) -> None:
        self.is_set = True


class FakeContext:
    """Contexte minimal : seuls les attributs lus via ``getattr`` par lifespan."""

    def __init__(self, **kwargs: Any) -> None:
        self._initialized = True  # évite tout appel à AppContext.initialize() réel
        self._warmup_tasks: list[asyncio.Task[None]] = []  # posé aussi par lifespan lui-même
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture(autouse=True)
def _redirect_token_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ancre ``Path(__file__).resolve().parent.parent`` sur ``tmp_path`` (règle 5)."""
    fake_module_path = tmp_path / "controllers" / "warmup.py"
    monkeypatch.setattr(warmup_module, "__file__", str(fake_module_path))


def _make_app(ctx: FakeContext) -> FastAPI:
    app = FastAPI()
    app.state.context = ctx
    return app


async def _run_startup(app: FastAPI) -> Any:
    """Exécute la portion démarrage du lifespan et renvoie le générateur (pour le shutdown)."""
    gen = lifespan(app)
    await gen.__anext__()
    return gen


async def _run_shutdown(gen: Any) -> None:
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()


class TestLifespanStartupDegraded:
    @pytest.mark.asyncio
    async def test_startup_completes_without_inference_or_vector(self) -> None:
        """Démarrage dégradé (ni inférence ni vecteur configurés) : aucune exception."""
        ctx = FakeContext(inference=None, vector=None)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)

    @pytest.mark.asyncio
    async def test_startup_creates_token_file_under_tmp_path(self, tmp_path: Path) -> None:
        ctx = FakeContext(inference=None, vector=None)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)

        token_file = tmp_path / "memory" / ".jarvis_token"
        assert token_file.exists()
        assert token_file.read_text()

    @pytest.mark.asyncio
    async def test_startup_reuses_existing_token_file(self, tmp_path: Path) -> None:
        token_file = tmp_path / "memory" / ".jarvis_token"
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text("existing-token")

        ctx = FakeContext(inference=None, vector=None)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)

        assert token_file.read_text() == "existing-token"


class TestLifespanWarmupVector:
    @pytest.mark.asyncio
    async def test_vector_preload_and_consolidate_called_when_present(self) -> None:
        vector = FakeVector()
        ctx = FakeContext(inference=None, vector=vector)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)

        assert vector.preload_called is True
        assert vector.consolidate_called is True
        await _run_shutdown(gen)

    @pytest.mark.asyncio
    async def test_vector_preload_failure_is_logged_not_raised(self) -> None:
        """Échec du préchargement vectoriel : catch large documenté, pas de propagation."""
        vector = FakeVector(fail_preload=True)
        ctx = FakeContext(inference=None, vector=vector)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        # Ne doit pas lever malgré l'exception interne au warmup en tâche de fond.
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)

    @pytest.mark.asyncio
    async def test_vector_consolidate_failure_is_logged_not_raised(self) -> None:
        vector = FakeVector(fail_consolidate=True)
        ctx = FakeContext(inference=None, vector=vector)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)


class TestLifespanWarmupModel:
    @pytest.mark.asyncio
    async def test_model_query_called_when_available(self) -> None:
        inference = FakeInference(available=True)
        ctx = FakeContext(inference=inference, vector=None)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)

        assert inference.query_called is True
        await _run_shutdown(gen)

    @pytest.mark.asyncio
    async def test_model_query_skipped_when_unavailable(self) -> None:
        """Modèle non disponible : warning journalisé, pas d'appel query (évite un échec certain)."""
        inference = FakeInference(available=False)
        ctx = FakeContext(inference=inference, vector=None)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)

        assert inference.query_called is False
        await _run_shutdown(gen)

    @pytest.mark.asyncio
    async def test_model_query_failure_is_logged_not_raised(self) -> None:
        inference = FakeInference(available=True, fail_query=True)
        ctx = FakeContext(inference=inference, vector=None)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)


class TestLifespanInitialize:
    @pytest.mark.asyncio
    async def test_calls_initialize_when_not_yet_initialized(self) -> None:
        """``ctx.initialize()`` est appelé une fois si présent et pas encore initialisé."""
        calls: list[bool] = []

        class InitializableContext(FakeContext):
            def __init__(self) -> None:
                super().__init__(inference=None, vector=None)
                self._initialized = False

            def initialize(self) -> None:
                calls.append(True)
                self._initialized = True

        ctx = InitializableContext()
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)

        assert calls == [True]

    @pytest.mark.asyncio
    async def test_skips_initialize_when_already_initialized(self) -> None:
        """``ctx.initialize()`` n'est PAS rappelé si ``_initialized`` est déjà vrai."""
        calls: list[bool] = []

        class InitializableContext(FakeContext):
            def __init__(self) -> None:
                super().__init__(inference=None, vector=None)
                self._initialized = True  # déjà initialisé

            def initialize(self) -> None:
                calls.append(True)

        ctx = InitializableContext()
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)

        assert calls == []


class TestLifespanIngestQueue:
    @pytest.mark.asyncio
    async def test_ingest_queue_started_when_present(self) -> None:
        queue = FakeIngestQueue()
        ctx = FakeContext(inference=None, vector=None, ingest_queue=queue)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        assert queue.started is True

        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)
        assert queue.stopped is True

    @pytest.mark.asyncio
    async def test_no_ingest_queue_attribute_is_safe(self) -> None:
        """Absence totale de l'attribut ``ingest_queue`` : pas d'AttributeError."""
        ctx = FakeContext(inference=None, vector=None)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)


class TestLifespanShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_cancels_pending_warmup_tasks(self) -> None:
        """Une tâche de warmup encore en vol au shutdown est annulée, pas attendue.

        Le shutdown est déclenché immédiatement après le démarrage, avant de
        laisser le scheduler exécuter les tâches de fond (``asyncio.to_thread``
        n'a pas eu l'occasion de s'exécuter).
        """
        vector = FakeVector()
        ctx = FakeContext(inference=None, vector=vector)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        tasks_at_shutdown = list(ctx._warmup_tasks)
        assert any(not task.done() for task in tasks_at_shutdown), "précondition : au moins une tâche encore en vol"

        # Shutdown immédiat, sans laisser les tâches de fond se terminer.
        await _run_shutdown(gen)
        # ``cancel()`` ne fait que demander l'annulation : un tour de boucle
        # est nécessaire pour qu'elle soit traitée par la tâche annulée.
        await asyncio.sleep(0)

        assert all(task.cancelled() or task.done() for task in tasks_at_shutdown)

    @pytest.mark.asyncio
    async def test_shutdown_sets_stop_event_when_present(self) -> None:
        stop_event = FakeStopEvent()
        ctx = FakeContext(inference=None, vector=None, stop_event=stop_event)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)

        assert stop_event.is_set is True

    @pytest.mark.asyncio
    async def test_shutdown_closes_inference_when_present(self) -> None:
        inference = FakeInference(available=False)
        ctx = FakeContext(inference=inference, vector=None)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)

        assert inference.close_called is True

    @pytest.mark.asyncio
    async def test_shutdown_inference_close_failure_is_logged_not_raised(self) -> None:
        inference = FakeInference(available=False, fail_close=True)
        ctx = FakeContext(inference=inference, vector=None)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        # Ne doit pas lever malgré l'exception dans inference.close().
        await _run_shutdown(gen)

    @pytest.mark.asyncio
    async def test_shutdown_flushes_vector_when_present(self) -> None:
        vector = FakeVector()
        ctx = FakeContext(inference=None, vector=vector)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)

        assert vector.flush_called is True

    @pytest.mark.asyncio
    async def test_shutdown_vector_flush_failure_is_logged_not_raised(self) -> None:
        vector = FakeVector(fail_flush=True)
        ctx = FakeContext(inference=None, vector=vector)
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        # Ne doit pas lever malgré l'exception dans vector.flush().
        await _run_shutdown(gen)

    @pytest.mark.asyncio
    async def test_shutdown_without_vector_or_inference_is_safe(self) -> None:
        """Contexte totalement dégradé au shutdown : aucun attribut, aucune exception."""
        ctx = FakeContext()
        app = _make_app(ctx)

        gen = await _run_startup(app)
        await asyncio.gather(*ctx._warmup_tasks)
        await _run_shutdown(gen)
