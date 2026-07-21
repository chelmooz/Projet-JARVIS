"""MemoryService — Stockage des habitudes et préférences utilisateur sur disque.

Responsabilité unique (SRP) :
- Gérer la persistance et la récupération des habitudes utilisateur (habits.json).
- Garantir la cohérence des données en mémoire et sur disque (thread-safe).
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any

from config.constants import MAX_HABITS, MEMORY_DIR
from ports import HabitPort
from services.file_utils import write_json_atomic

_logger = logging.getLogger("jarvis.memory")

HABITS_PATH = os.path.join(MEMORY_DIR, "habits.json")


class MemoryService(HabitPort):
    """Service de mémoire pour le stockage local des habitudes utilisateur."""

    def __init__(self) -> None:
        """Initialise le service et charge les habitudes depuis le disque."""
        os.makedirs(MEMORY_DIR, exist_ok=True)
        self._lock = threading.RLock()
        self._habits: list[dict[str, Any]] = self._load()

    @staticmethod
    def _load_from_disk() -> list[dict[str, Any]]:
        """Lit le fichier habits.json et retourne son contenu."""
        try:
            with open(HABITS_PATH, encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError) as e:
            _logger.debug("habits.json illisible ou absent, liste vide retournée : %s", e)
            return []

    def _load(self) -> list[dict[str, Any]]:
        """Charge la liste des habitudes en mémoire de manière thread-safe."""
        with self._lock:
            return self._load_from_disk()

    def _save(self, data: list[dict[str, Any]]) -> None:
        """Persiste la liste des habitudes sur disque de manière atomique."""
        with self._lock:
            write_json_atomic(HABITS_PATH, data)

    def get_habits(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retourne les N dernières habitudes enregistrées."""
        with self._lock:
            return self._habits[-limit:]

    def update_habits(self, entry: dict[str, Any]) -> None:
        """Ajoute une entrée d'habitude, tronque à MAX_HABITS et persiste."""
        with self._lock:
            self._habits.append(entry)
            if len(self._habits) > MAX_HABITS:
                self._habits = self._habits[-MAX_HABITS:]
            # Copie pour éviter toute mutation externe accidentelle avant l'écriture
            self._save(list(self._habits))

    def is_healthy(self) -> bool:
        """Vérifie que le dossier de mémoire existe et est accessible."""
        return os.path.isdir(MEMORY_DIR) and os.access(MEMORY_DIR, os.R_OK | os.W_OK)


__all__ = ["MemoryService"]
