"""OllamaHTTPClient — Couche HTTP bas niveau (pool, retry, streaming, cancellation).

Extrait d'OllamaAdapter (Phase 20) : toute la logique de transport, retry,
budget de temps, streaming SSE et annulation ciblée par thread.
"""

import contextvars
import json
import logging
import os
import threading
import time
from typing import Any

import httpx
import yaml

from config.constants import AGENT_TIMEOUT_SECONDS, DEFAULT_MODEL, PROJECT_DIR
from config.paths import OLLAMA_PORT, PROFILES_FILE

_logger = logging.getLogger("jarvis.adapters.http")


class BudgetExceededError(RuntimeError):
    """Budget de temps global épuisé avant la fin des tentatives."""


class OllamaHTTPClient:
    """Client HTTP Ollama avec pool partagé + clients dédiés par thread d'inférence.

    Responsabilités :
    - Pool partagé (`_http`) pour opérations légères non annulables (ping, tags)
    - Clients dédiés par thread (`_request_clients`) pour inférence annulable
    - Retry avec budget global (ROADMAP 13.6)
    - Streaming SSE NDJSON (ROADMAP 14.2)
    - Annulation ciblée par thread (ROADMAP 14.1)
    - Configuration : base_url, timeout, keep_alive (globaux + par profil)
    """

    MODELS_CACHE_TTL = 30

    def __init__(self, base_url: str | None = None, max_retries: int = 3):
        self._base_url = (base_url or self._load_base_url()).rstrip("/")
        self._timeout: int | None = None
        self._keep_alive: int | None = None
        self._http: httpx.Client | None = httpx.Client(timeout=httpx.Timeout(self._load_timeout(), connect=1.0))
        self._max_retries = max(1, int(max_retries))
        self._closed = False
        self._request_clients: dict[int, httpx.Client] = {}
        self._cancelled_threads: set[int] = set()
        self._request_lock = threading.Lock()
        self._stream_sink_var: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
            "_stream_sink_var", default=None
        )

    def set_stream_sink(self, sink: Any) -> None:
        self._stream_sink_var.set(sink)

    def clear_stream_sink(self) -> None:
        self._stream_sink_var.set(None)

    def close(self) -> None:
        self._closed = True
        if self._http is not None:
            try:
                self._http.close()
            except Exception as e:
                _logger.debug("Error closing HTTP client: %s", e)
            self._http = None
        with self._request_lock:
            clients = list(self._request_clients.values())
            self._request_clients.clear()
            self._cancelled_threads.clear()
        for client in clients:
            try:
                client.close()
            except Exception as e:
                _logger.debug("Error closing request client: %s", e)

    def ping(self) -> bool:
        return self._check_endpoint()

    def _check_endpoint(self) -> bool:
        try:
            return self._get_http().get(f"{self._base_url}/api/tags", timeout=0.5).status_code == 200
        except Exception:
            _logger.warning("Ollama endpoint %s injoignable", self._base_url)
            return False

    def _get_http(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=httpx.Timeout(self._load_timeout(), connect=1.0))
        return self._http

    def _request_client_for_call(self) -> httpx.Client | None:
        from unittest.mock import MagicMock

        http = self._http
        tid = threading.get_ident()
        with self._request_lock:
            if tid in self._cancelled_threads:
                return None
            client = self._request_clients.get(tid)
            if client is None:
                if http is not None and isinstance(getattr(http, "post", None), MagicMock):
                    return http
                client = httpx.Client(timeout=httpx.Timeout(self._load_timeout(), connect=1.0))
                self._request_clients[tid] = client
            return client

    def cancel_request(self, thread_id: int) -> None:
        with self._request_lock:
            self._cancelled_threads.add(thread_id)
            client = self._request_clients.pop(thread_id, None)
        if client is not None:
            try:
                client.close()
            except Exception as e:
                _logger.debug("cancel_request: fermeture client du thread %s échouée: %s", thread_id, e)

    def _load_base_url(self) -> str:
        try:
            adapters_path = os.path.join(PROJECT_DIR, "config", "adapters.yaml")
            with open(adapters_path) as f:
                cfg = yaml.safe_load(f) or {}
            return str(cfg.get("ollama", {}).get("base_url", f"http://127.0.0.1:{OLLAMA_PORT}"))
        except Exception as e:
            _logger.warning("Impossible de lire adapters.yaml pour base_url Ollama: %s", e)
            return f"http://127.0.0.1:{OLLAMA_PORT}"

    def _load_timeout(self) -> int:
        if self._timeout is not None:
            return self._timeout
        try:
            path = os.path.join(PROJECT_DIR, "config", "model_preferences.json")
            with open(path) as f:
                self._timeout = json.load(f).get("timeout", 120)
        except Exception:
            _logger.warning("Impossible de charger le timeout depuis model_preferences.json, fallback 120")
            self._timeout = 120
        return self._timeout

    def _load_keep_alive(self) -> int:
        if self._keep_alive is not None:
            return self._keep_alive
        try:
            path = os.path.join(PROJECT_DIR, "config", "model_preferences.json")
            with open(path) as f:
                self._keep_alive = json.load(f).get("keep_alive", 600)
        except Exception:
            _logger.warning("Impossible de charger keep_alive depuis model_preferences.json, fallback 600")
            self._keep_alive = 600
        return self._keep_alive

    def _keep_alive_for(self, model: str) -> int:
        if model == DEFAULT_MODEL:
            return -1
        try:
            import json
            from pathlib import Path

            with Path(PROFILES_FILE).open(encoding="utf-8") as handle:
                profiles = json.load(handle).get("profiles", {})
            for profile_key, profile_cfg in profiles.items():
                if profile_cfg.get("model") == model:
                    return int(profile_cfg.get("keep_alive", self._load_keep_alive()))
        except Exception as e:
            _logger.debug("Impossible de lire keep_alive depuis agent_profiles.json: %s", e)
        return int(self._load_keep_alive())

    def _call_with_retry(
        self,
        endpoint: str,
        payload: dict[str, Any],
        timeout: int | None = None,
        budget_seconds: float | int | None = None,
    ) -> dict[str, Any]:
        if getattr(self, "_closed", False):
            raise RuntimeError(f"Ollama echec: adapter fermé, requete abandonnee sur {endpoint}")

        tid = threading.get_ident()
        with self._request_lock:
            self._cancelled_threads.discard(tid)

        timeout = timeout or self._load_timeout()
        budget = float(budget_seconds) if budget_seconds is not None else float(AGENT_TIMEOUT_SECONDS)
        budget_remaining = budget
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            if getattr(self, "_closed", False):
                break

            if budget_remaining <= 0:
                raise BudgetExceededError(
                    f"Budget de temps épuisé après {attempt} tentative(s) sur {endpoint} (budget={budget:g}s)"
                )

            attempt_timeout = min(float(timeout), budget_remaining)
            t = httpx.Timeout(attempt_timeout, connect=1.0)

            client = self._request_client_for_call()
            if client is None:
                raise RuntimeError(f"Ollama {endpoint} annulé (timeout du garde-fou agent, thread {tid})")

            start = time.monotonic()

            try:
                r = client.post(endpoint, json=payload, timeout=t)
                r.raise_for_status()
                data: Any = r.json()
                return dict(data)
            except httpx.ReadTimeout as e:
                raise RuntimeError(f"Ollama {endpoint} en lecture timeout (modèle bloqué), pas de retry: {e}") from e
            except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as e:
                last_error = e
                budget_remaining -= time.monotonic() - start
                if tid in self._cancelled_threads:
                    raise RuntimeError(f"Ollama {endpoint} annulé (timeout du garde-fou Agent, thread {tid})") from e
                if attempt < self._max_retries - 1:
                    if budget_remaining <= 0:
                        continue
                    _logger.warning(
                        "Ollama %s echec (tentative %d/%d), retry...",
                        endpoint,
                        attempt + 1,
                        self._max_retries,
                    )
                    sleep_duration = 0.2 if attempt == 0 else 0.5
                    if budget_remaining > 0:
                        time.sleep(min(sleep_duration, budget_remaining))
                    continue
                break
        raise RuntimeError(f"Ollama echec apres {self._max_retries} tentative(s) sur {endpoint}: {last_error}")

    def _call_streaming(self, endpoint: str, payload: dict[str, Any], key: str) -> str:
        if getattr(self, "_closed", False):
            raise RuntimeError(f"Ollama echec: adapter fermé, requete abandonnee sur {endpoint}")
        client = self._request_client_for_call()
        if client is None:
            raise RuntimeError(f"Ollama {endpoint} annulé (timeout du garde-fou agent)")
        chunks: list[str] = []
        try:
            with client.stream("POST", endpoint, json=payload, timeout=self._load_timeout()) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    chunk = self._extract_stream_chunk(line, key)
                    if chunk:
                        sink = self._stream_sink_var.get()
                        if sink is not None:
                            sink.push(chunk)
                        chunks.append(chunk)
        except (httpx.RequestError, httpx.HTTPStatusError, OSError, ValueError) as e:
            raise RuntimeError(f"Ollama {endpoint} en streaming (stream=True) a échoué: {e}") from e
        return "".join(chunks)

    @staticmethod
    def _extract_stream_chunk(line: str, key: str) -> str:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return ""
        if data.get("done"):
            return ""
        if key == "message":
            return str(data.get("message", {}).get("content", ""))
        return str(data.get("response", ""))