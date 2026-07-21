"""OllamaAdapter — Backend LLM via Ollama API native."""
import contextlib
import json
import logging
import os
import time

import httpx
import yaml

from config.constants import PROJECT_DIR
from config.paths import OLLAMA_PORT
from models import Result
from services.adapters.protocols import LLMAdapter

_logger = logging.getLogger("jarvis.adapters.ollama")

MODELS_CACHE_TTL = 30  # Secondes : cache des /api/tags pour eviter 1 HTTP call par resolve_model

ADAPTERS_PATH = os.path.join(PROJECT_DIR, "config", "adapters.yaml")


class OllamaAdapter(LLMAdapter):
    """OllamaAdapter."""

    def __init__(self, base_url: str | None = None, max_retries: int = 3):
        self._base_url = (base_url or self._load_base_url()).rstrip("/")
        self._http = httpx.Client(timeout=httpx.Timeout(30.0, connect=1.0))
        self._backend = "ollama"
        self._max_retries = max(1, int(max_retries))
        self._models_cache: list[str] | None = None
        self._models_cache_ts: float = 0.0
        self._timeout: int | None = None

    def close(self) -> None:
        """Libère le client HTTP (sockets) en fin d'usage pour ne pas leisser de sockets ouverts."""
        if self._http is not None:
            with contextlib.suppress(Exception):
                self._http.close()
            self._http = None

    def __del__(self):
        with contextlib.suppress(Exception):
            self.close()

    def ping(self) -> bool:
        return OllamaAdapter._check_endpoint(self._base_url)

    @staticmethod
    def _check_endpoint(url: str) -> bool:
        try:
            return httpx.get(f"{url}/api/tags", timeout=2).status_code == 200
        except Exception:
            return False

    def _get_http(self) -> "httpx.Client":
        """Retourne un client HTTP valide, le recreant si None (annulation requete).

        `close()` (appele par `cancel_current()` au timeout AgentSupervisor) remet
        `self._http` a None ; le prochain appel recree le client. Le thread en vol
        garde la reference de l'ancien client (ferme) qui leve -> pas de zombie.
        """
        if self._http is None:
            self._http = httpx.Client(timeout=httpx.Timeout(30.0, connect=1.0))
        return self._http

    @staticmethod
    def _load_base_url() -> str:
        """ load base url."""
        try:
            with open(ADAPTERS_PATH) as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get("ollama", {}).get("base_url", f"http://127.0.0.1:{OLLAMA_PORT}")

        except Exception as e:
            _logger.warning("Impossible de lire adapters.yaml pour base_url Ollama: %s", e)
            return f"http://127.0.0.1:{OLLAMA_PORT}"

    def _load_timeout(self) -> int:
        """Charge le timeout depuis model_preferences.json (caché par appel)."""
        if self._timeout is not None:
            return self._timeout
        try:
            path = os.path.join(PROJECT_DIR, "config", "model_preferences.json")
            with open(path) as f:
                self._timeout = json.load(f).get("timeout", 120)
        except Exception:
            self._timeout = 120
        return self._timeout

    def _call_with_retry(self, endpoint: str, payload: dict, timeout: int | None = None) -> dict:
        """Appelle l'endpoint Ollama avec re-essais sur erreurs transitoires.

        `_max_retries` tentatives reelles (defaut 3) ; on attend 1s entre deux
        echecs avant de reessayer. Leve RuntimeError seulement apres epuisement.
        """
        timeout = timeout or self._load_timeout()
        t = httpx.Timeout(timeout, connect=1.0)
        client = self._get_http()
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                r = client.post(endpoint, json=payload, timeout=t)
                r.raise_for_status()
                return r.json()
            except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    _logger.warning(
                        "Ollama %s echec (tentative %d/%d), retry...",
                        endpoint, attempt + 1, self._max_retries,
                    )
                    time.sleep(1)
                    continue
                break
        raise RuntimeError(
            f"Ollama echec apres {self._max_retries} tentative(s) sur {endpoint}: {last_error}"
        )

    def query(self, prompt: str, model: str, system: str | None = None) -> str:
        """Query."""
        payload = {"model": model, "prompt": prompt, "stream": False, "keep_alive": -1}
        if system:
            payload["system"] = system
        data = self._call_with_retry(f"{self._base_url}/api/generate", payload)
        return data.get("response", "")

    def query_multimodal(self, model: str, prompt: str, image_base64: str) -> dict:
        """Query multimodal."""
        payload = {
            "model": model, "prompt": prompt, "stream": False,
            "images": [image_base64],
        }
        data = self._call_with_retry(f"{self._base_url}/api/generate", payload)
        return {"content": data.get("response", ""), "model": model, "role": "assistant"}

    def chat(self, model: str, messages: list[dict]) -> Result:
        """Chat."""
        try:
            data = self._call_with_retry(f"{self._base_url}/api/chat", {
                "model": model, "messages": messages, "stream": False, "keep_alive": -1,
            })
            content = data.get("message", {}).get("content", "")
            return Result.ok(data={"content": content, "role": "assistant"}, agent="system", model=model)
        except RuntimeError as e:
            return Result.fail(error=str(e), agent="system", model=model)

    def _fetch_models(self) -> list[str]:
        """ fetch models (cache 30s pour eviter 1 HTTP call par resolve_model)."""
        now = time.time()
        if self._models_cache is not None and now - self._models_cache_ts < MODELS_CACHE_TTL:
            return self._models_cache
        try:
            client = self._get_http()
            r = client.get(f"{self._base_url}/api/tags", timeout=2)
            models = [m["name"] for m in r.json().get("models", [])]
        except Exception as e:
            _logger.warning("Liste modeles Ollama indisponible: %s", e)
            models = []
        self._models_cache = models
        self._models_cache_ts = now
        return models

    def list_models(self) -> list[str]:
        """List models."""
        return self._fetch_models()

    @staticmethod
    def _repo_name(tag: str) -> str:
        """Extrait le nom de dépôt d'un tag Ollama (suffixe -gguf retiré).

        'qwen2.5:latest'                 -> 'qwen2.5'
        'hf.co/org/Repo-GGUF:Q4_K_M'     -> 'repo'
        """
        name = tag.rsplit("/", 1)[-1].lower()
        return name.split(":", 1)[0].removesuffix("-gguf")

    @staticmethod
    def _matches(available: list[str], model: str) -> bool:
        """Match tolérant : nom exact OU base name == nom de repo du tag.

        Les modèles HF importés portent un tag de la forme
        'hf.co/<org>/<repo>-GGUF:Q4_K_M' ; on accepte donc qu'un nom court
        (ex: 'phi-4-mini-instruct-abliterated') matche 'repo-gguf'
        (sans le suffixe GGUF).
        """
        model = model.strip().lower()
        wanted = model.removesuffix("-gguf")
        for tag in available:
            if tag.lower() == model:
                return True
            if OllamaAdapter._repo_name(tag) == wanted:
                return True
        return False

    def is_available(self, model: str) -> bool:
        """Indique si available (match exact ou base name)."""
        return self._matches(self._fetch_models(), model)

    def resolve_model(self, model: str) -> str | None:
        """Retourne le tag Ollama reel correspondant a un nom court de config.

        'qwen2.5' -> 'qwen2.5:latest'
        'phi-4-mini-instruct-abliterated' -> 'hf.co/Melvin56/...-GGUF:Q4_K_M'
        Renvoie None si aucun modele ne matche.
        """
        if not model:
            return None
        available = self._fetch_models()
        if model in available:
            return model
        for tag in available:
            if self._matches([tag], model):
                return tag
        return None

    def first_available(self) -> str | None:
        """First available."""
        models = self._fetch_models()
        return models[0] if models else None

    def embed(self, text: str, model: str | None = None) -> list[float]:
        model = model or "nomic-embed-text-v2-moe"
        model = self.resolve_model(model) or model
        data = self._call_with_retry(f"{self._base_url}/api/embed", {
            "model": model, "input": [text],
        })
        embeddings = data.get("embeddings")
        if not embeddings:
            raise RuntimeError(
                "Ollama embed a retourne aucun vecteur (modele d'embedding absent "
                "ou reponse partielle)"
            )
        return embeddings[0]

    def get_active_backend(self) -> str:
        """Recupere active backend."""
        return self._backend
