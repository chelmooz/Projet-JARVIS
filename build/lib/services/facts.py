"""FactStore — Faits horodatés persistants (JSON). Une responsabilité : stocker."""
import json
import logging
import os
import time

from config.paths import MEMORY_DIR
from services.file_utils import write_json_atomic

_logger = logging.getLogger(__name__)

FACTS_PATH = os.path.join(MEMORY_DIR, "facts.json")


class FactStore:
    """Stocke des faits horodatés dans un fichier JSON. CRUD simple, pas de logique métier."""

    def __init__(self):
        os.makedirs(MEMORY_DIR, exist_ok=True)
        self._facts = self._load()

    def _load(self) -> list:
        try:
            with open(FACTS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            _logger.debug("Failed to load facts: %s", e)
            return []

    def _save(self):
        write_json_atomic(FACTS_PATH, self._facts)

    def add(self, text: str, metadata: dict = None, source: str = "user"):
        """Ajoute un fait horodaté et persiste. Thread-safe (write_json_atomic)."""
        self._facts.append({
            "text": text, "metadata": metadata or {},
            "source": source, "ts": time.time(),
        })
        self._save()

    def remove_old(self, cutoff_ts: float) -> int:
        """Supprime les faits antérieurs au cutoff. Retourne le nombre supprimé."""
        before = len(self._facts)
        self._facts = [f for f in self._facts if f["ts"] >= cutoff_ts]
        self._save()
        return before - len(self._facts)
