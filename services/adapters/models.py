"""ModelRegistry — Registre des modèles Ollama (fetch, cache, résolution, keep_alive).

Extrait d'OllamaAdapter (Phase 20) : logique de découverte et résolution de modèles,
indépendante du transport HTTP. S'appuie sur ollama_models.py (fonctions pures).
"""

import logging
import time
from typing import Any

from services.adapters.http import OllamaHTTPClient
from services.adapters.ollama_models import first_completion, matches, resolve_tag

_logger = logging.getLogger("jarvis.adapters.models")

MODELS_CACHE_TTL = 30


class ModelRegistry:
    """Registre des modèles avec cache TTL 30s.

    Responsabilités :
    - Fetch /api/tags avec cache partagé
    - list_models(), is_available(), resolve_model(), first_available()
    - Politique keep_alive par modèle/profil
    """

    def __init__(self, http_client: OllamaHTTPClient):
        self._http = http_client
        self._models_cache: list[dict[str, Any]] | None = None
        self._models_cache_ts: float = 0.0

    def _fetch_models_raw(self) -> list[dict[str, Any]]:
        """Fetch models avec métadonnées complètes (capabilities incluses).

        Cache 30s partagé pour éviter 1 HTTP call par resolve_model()/first_available().
        """
        now = time.time()
        if self._models_cache is not None and now - self._models_cache_ts < MODELS_CACHE_TTL:
            return self._models_cache
        try:
            client = self._http._get_http()
            r = client.get(f"{self._http._base_url}/api/tags", timeout=2)
            raw_models: Any = r.json()
            models = [dict(m) for m in raw_models.get("models", [])]
        except Exception as e:
            _logger.warning("Liste modeles Ollama indisponible: %s", e)
            models = []
        self._models_cache = models
        self._models_cache_ts = now
        return models

    def _fetch_models(self) -> list[str]:
        """Fetch models (noms seulement) — cache partagé avec _fetch_models_raw()."""
        return [str(m["name"]) for m in self._fetch_models_raw()]

    def list_models(self) -> list[str]:
        return self._fetch_models()

    def is_available(self, model: str) -> bool:
        """Indique si available (match exact ou base name)."""
        return matches(self._fetch_models(), model)

    def resolve_model(self, model: str) -> str | None:
        """Retourne le tag Ollama réel correspondant à un nom court de config."""
        return resolve_tag(self._fetch_models(), model)

    def first_available(self) -> str | None:
        """Premier modèle disponible capable de génération de texte.

        Exclut les modèles embedding-only (ex: nomic-embed-text) : les
        envoyer à /api/generate produit un 400 Bad Request côté Ollama
        (capability "embedding" mais pas "completion"). Un modèle sans
        champ "capabilities" (anciennes versions d'Ollama) est considéré
        disponible par défaut — comportement historique préservé.

        Préférence texte pur : un modèle completion avec la capability
        "vision" (ex: moondream) n'est proposé qu'en dernier recours —
        brancher un modèle vision au chat produit des réponses hors sujet.
        """
        candidates = self._fetch_models_raw()
        return first_completion(candidates, prefer_pure_text=True) or first_completion(candidates)

    def keep_alive_for(self, model: str) -> int:
        """keep_alive appliqué à un modèle selon le profil d'agent qui l'utilise.

        - Modèle par défaut (DEFAULT_MODEL) : -1 (résident en mémoire)
        - Autres modèles : lecture depuis config/agent_profiles.json (clé "keep_alive" par profil)
        - Fallback : keep_alive global depuis model_preferences.json
        """
        return self._http._keep_alive_for(model)