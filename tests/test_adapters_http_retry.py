"""Tests de caractérisation pour ``services/adapters/http.py:_call_with_retry`` (Lot F1).

Verrouille le comportement actuel AVANT tout refactor (extraction d'une
politique de retry pure, Lot F2) :
- succès immédiat (2xx) ;
- retry puis succès (``httpx.RequestError``/``HTTPStatusError``) ;
- ``httpx.ReadTimeout`` : cas spécial, aucun retry, échec immédiat ;
- épuisement de toutes les tentatives -> ``RuntimeError`` explicite ;
- budget de temps épuisé -> ``BudgetExceededError`` ;
- annulation concurrente (thread marqué annulé pendant une tentative) ;
- adaptateur fermé -> échec immédiat, aucun appel HTTP ;
- backoff borné par le budget restant.

Le seam de test existant dans le code (``_request_client_for_call`` renvoie
``self._http`` tel quel si ``self._http.post`` est un ``MagicMock``) est
réutilisé : on injecte un ``MagicMock`` comme client HTTP, sans toucher au
réseau.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from services.adapters.http import BudgetExceededError, OllamaHTTPClient


class FakeResponse:
    """Réponse HTTP factice : ``raise_for_status()`` + ``json()`` configurables."""

    def __init__(self, json_data: dict[str, Any] | None = None, raise_exc: Exception | None = None) -> None:
        self._json = json_data or {}
        self._raise_exc = raise_exc

    def raise_for_status(self) -> None:
        if self._raise_exc is not None:
            raise self._raise_exc

    def json(self) -> dict[str, Any]:
        return self._json


@pytest.fixture
def client() -> OllamaHTTPClient:
    """Client avec un pool HTTP factice (``MagicMock``) — aucun réseau réel."""
    c = OllamaHTTPClient(base_url="http://fake-ollama:11434", max_retries=3)
    c._http = MagicMock()
    return c


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Remplace ``time.sleep`` par un enregistreur : tests rapides et déterministes."""
    calls: list[float] = []
    monkeypatch.setattr("services.adapters.http.time.sleep", lambda duration: calls.append(duration))
    return calls


class TestCallWithRetrySuccess:
    def test_immediate_success_returns_dict(self, client: OllamaHTTPClient) -> None:
        client._http.post.return_value = FakeResponse(json_data={"response": "ok"})

        result = client._call_with_retry("/api/generate", {"model": "x"})

        assert result == {"response": "ok"}
        assert client._http.post.call_count == 1

    def test_retry_then_success(self, client: OllamaHTTPClient) -> None:
        client._http.post.side_effect = [
            httpx.ConnectError("refused"),
            FakeResponse(json_data={"response": "ok après retry"}),
        ]

        result = client._call_with_retry("/api/generate", {"model": "x"})

        assert result == {"response": "ok après retry"}
        assert client._http.post.call_count == 2

    def test_http_status_error_then_success(self, client: OllamaHTTPClient) -> None:
        bad = FakeResponse(raise_exc=httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock()))
        client._http.post.side_effect = [bad, FakeResponse(json_data={"response": "ok"})]

        result = client._call_with_retry("/api/generate", {"model": "x"})

        assert result == {"response": "ok"}


class TestCallWithRetryReadTimeout:
    def test_read_timeout_raises_immediately_no_retry(self, client: OllamaHTTPClient) -> None:
        """``httpx.ReadTimeout`` : cas spécial documenté, jamais de retry (modèle bloqué)."""
        client._http.post.side_effect = httpx.ReadTimeout("blocked")

        with pytest.raises(RuntimeError, match="lecture timeout"):
            client._call_with_retry("/api/generate", {"model": "x"})

        assert client._http.post.call_count == 1


class TestCallWithRetryExhaustion:
    def test_all_attempts_exhausted_raises_runtime_error(self, client: OllamaHTTPClient) -> None:
        client._http.post.side_effect = httpx.ConnectError("refused")

        with pytest.raises(RuntimeError, match="echec apres 3 tentative"):
            client._call_with_retry("/api/generate", {"model": "x"})

        assert client._http.post.call_count == 3

    def test_adapter_closed_raises_immediately_no_call(self, client: OllamaHTTPClient) -> None:
        client._closed = True

        with pytest.raises(RuntimeError, match="adapter fermé"):
            client._call_with_retry("/api/generate", {"model": "x"})

        assert client._http.post.call_count == 0


class TestCallWithRetryBudget:
    def test_zero_budget_raises_budget_exceeded_before_first_attempt(self, client: OllamaHTTPClient) -> None:
        with pytest.raises(BudgetExceededError, match="Budget de temps épuisé"):
            client._call_with_retry("/api/generate", {"model": "x"}, budget_seconds=0)

        assert client._http.post.call_count == 0


class TestCallWithRetryCancellation:
    def test_cancelled_thread_raises_runtime_error_mid_attempt(self, client: OllamaHTTPClient) -> None:
        """Le thread est marqué annulé pendant la requête : pas de retry, échec immédiat."""

        def _post_then_cancel(*args: Any, **kwargs: Any) -> Any:
            import threading

            client._cancelled_threads.add(threading.get_ident())
            raise httpx.ConnectError("refused")

        client._http.post.side_effect = _post_then_cancel

        with pytest.raises(RuntimeError, match="annulé"):
            client._call_with_retry("/api/generate", {"model": "x"})

        assert client._http.post.call_count == 1


class TestCallWithRetryBackoff:
    def test_backoff_sleep_clamped_to_remaining_budget(
        self, client: OllamaHTTPClient, _no_real_sleep: list[float]
    ) -> None:
        """Le budget restant est très inférieur au backoff nominal (0.2s) : sleep clampé."""
        client._http.post.side_effect = [
            httpx.ConnectError("refused"),
            FakeResponse(json_data={"response": "ok"}),
        ]

        client._call_with_retry("/api/generate", {"model": "x"}, budget_seconds=0.01)

        assert _no_real_sleep, "un backoff doit avoir été enregistré"
        assert _no_real_sleep[0] <= 0.01

    def test_first_retry_backoff_is_nominal_0_2s(self, client: OllamaHTTPClient, _no_real_sleep: list[float]) -> None:
        """Budget large : le backoff de la première tentative suit la valeur nominale (0.2s)."""
        client._http.post.side_effect = [
            httpx.ConnectError("refused"),
            FakeResponse(json_data={"response": "ok"}),
        ]

        client._call_with_retry("/api/generate", {"model": "x"}, budget_seconds=60)

        assert _no_real_sleep == [0.2]
