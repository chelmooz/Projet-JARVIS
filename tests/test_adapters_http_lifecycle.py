"""Caractérisation de ``services/adapters/http.py`` — hors ``_call_with_retry``
(déjà couvert par ``test_adapters_http_retry.py``).

Couvre : ping/_check_endpoint, _get_http, _request_client_for_call, close,
cancel_request, _load_base_url, _load_timeout, _load_keep_alive,
_keep_alive_for, _call_streaming, _extract_stream_chunk, set/clear_stream_sink,
et les branches restantes de ``_call_with_retry`` (closed mid-loop, client
None mid-loop, budget épuisé pendant l'attente/backoff).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
import yaml

from services.adapters.http import BudgetExceededError, OllamaHTTPClient


@pytest.fixture
def client() -> OllamaHTTPClient:
    c = OllamaHTTPClient(base_url="http://fake-ollama:11434", max_retries=3)
    c._http = MagicMock()
    return c


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    calls: list[float] = []
    monkeypatch.setattr("services.adapters.http.time.sleep", lambda duration: calls.append(duration))
    return calls


# ---------------------------------------------------------------------------
# ping / _check_endpoint
# ---------------------------------------------------------------------------


class TestPing:
    def test_ping_true_on_200(self, client: OllamaHTTPClient) -> None:
        response = MagicMock(status_code=200)
        client._http.get.return_value = response
        assert client.ping() is True

    def test_ping_false_on_non_200(self, client: OllamaHTTPClient) -> None:
        response = MagicMock(status_code=500)
        client._http.get.return_value = response
        assert client.ping() is False

    def test_ping_false_on_exception(self, client: OllamaHTTPClient) -> None:
        client._http.get.side_effect = httpx.ConnectError("refused")
        assert client.ping() is False


# ---------------------------------------------------------------------------
# _get_http
# ---------------------------------------------------------------------------


class TestGetHttp:
    def test_returns_existing_client(self, client: OllamaHTTPClient) -> None:
        existing = client._http
        assert client._get_http() is existing

    def test_creates_new_client_when_none(self, client: OllamaHTTPClient) -> None:
        client._http = None
        http = client._get_http()
        assert isinstance(http, httpx.Client)
        assert client._http is http
        http.close()


# ---------------------------------------------------------------------------
# set/clear stream sink
# ---------------------------------------------------------------------------


class TestStreamSink:
    def test_set_and_clear_stream_sink(self, client: OllamaHTTPClient) -> None:
        sink = object()
        client.set_stream_sink(sink)
        assert client._stream_sink_var.get() is sink
        client.clear_stream_sink()
        assert client._stream_sink_var.get() is None


# ---------------------------------------------------------------------------
# _request_client_for_call
# ---------------------------------------------------------------------------


class TestRequestClientForCall:
    def test_magicmock_post_seam_returns_shared_http(self, client: OllamaHTTPClient) -> None:
        """Seam de test : si ``self._http.post`` est un MagicMock, on le réutilise tel quel."""
        result = client._request_client_for_call()
        assert result is client._http

    def test_creates_and_caches_dedicated_client(self) -> None:
        real_client = OllamaHTTPClient(base_url="http://fake:11434", max_retries=1)
        first = real_client._request_client_for_call()
        second = real_client._request_client_for_call()
        assert first is second
        assert isinstance(first, httpx.Client)
        real_client.close()

    def test_returns_none_for_cancelled_thread(self, client: OllamaHTTPClient) -> None:
        tid = threading.get_ident()
        client._cancelled_threads.add(tid)
        assert client._request_client_for_call() is None


# ---------------------------------------------------------------------------
# cancel_request
# ---------------------------------------------------------------------------


class TestCancelRequest:
    def test_cancel_marks_thread_and_closes_client(self) -> None:
        real_client = OllamaHTTPClient(base_url="http://fake:11434", max_retries=1)
        dedicated = real_client._request_client_for_call()
        tid = threading.get_ident()
        assert dedicated is not None

        real_client.cancel_request(tid)

        assert tid in real_client._cancelled_threads
        assert tid not in real_client._request_clients
        real_client.close()

    def test_cancel_unknown_thread_is_noop(self, client: OllamaHTTPClient) -> None:
        client.cancel_request(999999)
        assert 999999 in client._cancelled_threads

    def test_cancel_swallows_close_exception(self) -> None:
        real_client = OllamaHTTPClient(base_url="http://fake:11434", max_retries=1)
        tid = threading.get_ident()
        real_client._request_client_for_call()
        broken = MagicMock()
        broken.close.side_effect = RuntimeError("boom")
        real_client._request_clients[tid] = broken
        real_client.cancel_request(tid)  # ne doit pas lever
        assert tid in real_client._cancelled_threads
        real_client.close()


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    def test_close_marks_closed_and_clears_state(self, client: OllamaHTTPClient) -> None:
        client.close()
        assert client._closed is True
        assert client._http is None
        assert client._request_clients == {}
        assert client._cancelled_threads == set()

    def test_close_swallows_shared_client_exception(self, client: OllamaHTTPClient) -> None:
        client._http.close.side_effect = RuntimeError("boom")
        client.close()  # ne doit pas lever
        assert client._closed is True

    def test_close_swallows_dedicated_client_exception(self) -> None:
        real_client = OllamaHTTPClient(base_url="http://fake:11434", max_retries=1)
        real_client._request_client_for_call()
        tid = threading.get_ident()
        broken = MagicMock()
        broken.close.side_effect = RuntimeError("boom")
        real_client._request_clients[tid] = broken
        real_client.close()  # ne doit pas lever

    def test_close_is_noop_when_http_already_none(self, client: OllamaHTTPClient) -> None:
        client._http = None
        client.close()
        assert client._closed is True


# ---------------------------------------------------------------------------
# _load_base_url / _load_timeout / _load_keep_alive
# ---------------------------------------------------------------------------


class TestLoadConfigFromDisk:
    def test_load_base_url_from_adapters_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "adapters.yaml").write_text(yaml.safe_dump({"ollama": {"base_url": "http://custom:9999"}}))
        monkeypatch.setattr("services.adapters.http.PROJECT_DIR", str(tmp_path))
        c = OllamaHTTPClient()
        assert c._base_url == "http://custom:9999"
        c.close()

    def test_load_base_url_fallback_on_missing_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("services.adapters.http.PROJECT_DIR", str(tmp_path))
        c = OllamaHTTPClient()
        assert c._base_url.startswith("http://127.0.0.1:")
        c.close()

    def test_load_timeout_from_model_preferences(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "model_preferences.json").write_text(json.dumps({"timeout": 42}))
        monkeypatch.setattr("services.adapters.http.PROJECT_DIR", str(tmp_path))
        c = OllamaHTTPClient(base_url="http://fake:1")
        assert c._load_timeout() == 42
        c.close()

    def test_load_timeout_fallback_120_on_missing_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("services.adapters.http.PROJECT_DIR", str(tmp_path))
        c = OllamaHTTPClient(base_url="http://fake:1")
        assert c._load_timeout() == 120
        c.close()

    def test_load_timeout_is_cached(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = config_dir / "model_preferences.json"
        prefs.write_text(json.dumps({"timeout": 42}))
        monkeypatch.setattr("services.adapters.http.PROJECT_DIR", str(tmp_path))
        c = OllamaHTTPClient(base_url="http://fake:1")
        assert c._load_timeout() == 42
        prefs.write_text(json.dumps({"timeout": 999}))
        assert c._load_timeout() == 42  # valeur mise en cache, pas relue
        c.close()

    def test_load_keep_alive_from_model_preferences(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "model_preferences.json").write_text(json.dumps({"keep_alive": 111}))
        monkeypatch.setattr("services.adapters.http.PROJECT_DIR", str(tmp_path))
        c = OllamaHTTPClient(base_url="http://fake:1")
        assert c._load_keep_alive() == 111
        c.close()

    def test_load_keep_alive_fallback_600_on_missing_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("services.adapters.http.PROJECT_DIR", str(tmp_path))
        c = OllamaHTTPClient(base_url="http://fake:1")
        assert c._load_keep_alive() == 600
        c.close()

    def test_load_keep_alive_is_cached(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        prefs = config_dir / "model_preferences.json"
        prefs.write_text(json.dumps({"keep_alive": 111}))
        monkeypatch.setattr("services.adapters.http.PROJECT_DIR", str(tmp_path))
        c = OllamaHTTPClient(base_url="http://fake:1")
        assert c._load_keep_alive() == 111
        prefs.write_text(json.dumps({"keep_alive": 999}))
        assert c._load_keep_alive() == 111  # valeur mise en cache, pas relue
        c.close()


class TestKeepAliveFor:
    def test_default_model_returns_minus_one(self, client: OllamaHTTPClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("services.adapters.http.DEFAULT_MODEL", "the-default")
        assert client._keep_alive_for("the-default") == -1

    def test_matching_profile_returns_its_keep_alive(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        profiles_file = tmp_path / "agent_profiles.json"
        profiles_file.write_text(json.dumps({"profiles": {"techlead": {"model": "qwen2.5", "keep_alive": 777}}}))
        monkeypatch.setattr("services.adapters.http.PROFILES_FILE", str(profiles_file))
        c = OllamaHTTPClient(base_url="http://fake:1")
        assert c._keep_alive_for("qwen2.5") == 777
        c.close()

    def test_no_matching_profile_falls_back_to_load_keep_alive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        profiles_file = tmp_path / "agent_profiles.json"
        profiles_file.write_text(json.dumps({"profiles": {"techlead": {"model": "other-model"}}}))
        monkeypatch.setattr("services.adapters.http.PROFILES_FILE", str(profiles_file))
        monkeypatch.setattr("services.adapters.http.PROJECT_DIR", str(tmp_path))
        c = OllamaHTTPClient(base_url="http://fake:1")
        assert c._keep_alive_for("unmatched-model") == 600
        c.close()

    def test_missing_profiles_file_falls_back_to_load_keep_alive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("services.adapters.http.PROFILES_FILE", str(tmp_path / "absent.json"))
        monkeypatch.setattr("services.adapters.http.PROJECT_DIR", str(tmp_path))
        c = OllamaHTTPClient(base_url="http://fake:1")
        assert c._keep_alive_for("whatever-model") == 600
        c.close()


# ---------------------------------------------------------------------------
# _call_streaming / _extract_stream_chunk
# ---------------------------------------------------------------------------


class FakeStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self) -> Iterator[str]:
        yield from self._lines


class FakeStreamClient:
    def __init__(self, lines: list[str], raise_exc: Exception | None = None) -> None:
        self._lines = lines
        self._raise_exc = raise_exc

    @contextmanager
    def stream(self, method: str, url: str, json: Any = None, timeout: Any = None) -> Iterator[FakeStreamResponse]:
        if self._raise_exc is not None:
            raise self._raise_exc
        yield FakeStreamResponse(self._lines)


class TestCallStreaming:
    def test_streams_response_key_chunks(self, client: OllamaHTTPClient, monkeypatch: pytest.MonkeyPatch) -> None:
        lines = [
            json.dumps({"response": "Bon"}),
            json.dumps({"response": "jour"}),
            json.dumps({"done": True}),
        ]
        fake = FakeStreamClient(lines)
        monkeypatch.setattr(client, "_request_client_for_call", lambda: fake)
        result = client._call_streaming("/api/generate", {"model": "x"}, key="response")
        assert result == "Bonjour"

    def test_streams_message_key_chunks(self, client: OllamaHTTPClient, monkeypatch: pytest.MonkeyPatch) -> None:
        lines = [json.dumps({"message": {"content": "salut"}})]
        fake = FakeStreamClient(lines)
        monkeypatch.setattr(client, "_request_client_for_call", lambda: fake)
        result = client._call_streaming("/api/chat", {"model": "x"}, key="message")
        assert result == "salut"

    def test_streams_skips_blank_lines_and_invalid_json(
        self, client: OllamaHTTPClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lines = ["", "not json", json.dumps({"response": "ok"})]
        fake = FakeStreamClient(lines)
        monkeypatch.setattr(client, "_request_client_for_call", lambda: fake)
        result = client._call_streaming("/api/generate", {"model": "x"}, key="response")
        assert result == "ok"

    def test_streams_pushes_to_sink_when_set(self, client: OllamaHTTPClient, monkeypatch: pytest.MonkeyPatch) -> None:
        lines = [json.dumps({"response": "chunk1"})]
        fake = FakeStreamClient(lines)
        monkeypatch.setattr(client, "_request_client_for_call", lambda: fake)
        sink = MagicMock()
        client.set_stream_sink(sink)
        client._call_streaming("/api/generate", {"model": "x"}, key="response")
        sink.push.assert_called_once_with("chunk1")

    def test_streams_raises_runtime_error_on_request_error(
        self, client: OllamaHTTPClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = FakeStreamClient([], raise_exc=httpx.ConnectError("refused"))
        monkeypatch.setattr(client, "_request_client_for_call", lambda: fake)
        with pytest.raises(RuntimeError, match="streaming"):
            client._call_streaming("/api/generate", {"model": "x"}, key="response")

    def test_streams_closed_adapter_raises_immediately(self, client: OllamaHTTPClient) -> None:
        client._closed = True
        with pytest.raises(RuntimeError, match="adapter fermé"):
            client._call_streaming("/api/generate", {"model": "x"}, key="response")

    def test_streams_no_client_available_raises(
        self, client: OllamaHTTPClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(client, "_request_client_for_call", lambda: None)
        with pytest.raises(RuntimeError, match="annulé"):
            client._call_streaming("/api/generate", {"model": "x"}, key="response")


# ---------------------------------------------------------------------------
# Branches restantes de _call_with_retry
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, json_data: dict[str, Any] | None = None) -> None:
        self._json = json_data or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._json


class TestCallWithRetryRemainingBranches:
    def test_closed_mid_loop_breaks_and_raises_final_error(
        self, client: OllamaHTTPClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """L'adapter est fermé entre deux tentatives (thread concurrent) : la
        boucle `break` sans lever BudgetExceededError, et retombe sur le
        RuntimeError générique de fin de tentatives."""

        def _post_then_close(*args: Any, **kwargs: Any) -> Any:
            client._closed = True
            raise httpx.ConnectError("refused")

        client._http.post.side_effect = _post_then_close

        with pytest.raises(RuntimeError, match="echec apres 3 tentative"):
            client._call_with_retry("/api/generate", {"model": "x"})

        assert client._http.post.call_count == 1

    def test_no_client_available_mid_loop_raises_runtime_error(
        self, client: OllamaHTTPClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(client, "_request_client_for_call", lambda: None)
        with pytest.raises(RuntimeError, match="annulé"):
            client._call_with_retry("/api/generate", {"model": "x"})

    def test_budget_exhausted_during_attempt_continues_then_raises(
        self, client: OllamaHTTPClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le budget devient négatif *pendant* une tentative (calcul de
        ``budget_remaining`` après l'échec) : la branche `continue` (sans
        sleep) est empruntée, puis l'itération suivante lève
        ``BudgetExceededError``."""
        times = iter([0.0, 100.0])
        monkeypatch.setattr("services.adapters.http.time.monotonic", lambda: next(times))
        client._http.post.side_effect = httpx.ConnectError("refused")

        with pytest.raises(BudgetExceededError, match="après 1 tentative"):
            client._call_with_retry("/api/generate", {"model": "x"}, budget_seconds=10)

        assert client._http.post.call_count == 1
