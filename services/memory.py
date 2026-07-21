"""Service memoire — Stockage des habitudes et préférences utilisateur sur disque."""
import json
import logging
import os
import threading

from config.constants import MAX_HABITS, MEMORY_DIR
from ports import MemoryPort
from services.file_utils import write_json_atomic

_logger = logging.getLogger("jarvis.memory")

HABITS_PATH = os.path.join(MEMORY_DIR, "habits.json")

_lock = threading.RLock()


class MemoryService(MemoryPort):
    """MemoryService."""

    def __init__(self):
        """Charge les habitudes depuis le disque au démarrage."""
        os.makedirs(MEMORY_DIR, exist_ok=True)
        self._habits = self._load()

    @staticmethod
    def _load_from_disk() -> list:
        try:
            with open(HABITS_PATH) as f:
                return json.load(f)
        except Exception as e:
            _logger.debug("habits.json illisible/absent, liste vide: %s", e)
            return []

    def _load(self) -> list:
        """Charge la liste des habitudes depuis habits.json."""
        with _lock:
            return self._load_from_disk()

    def _save(self, data):
        with _lock:
            write_json_atomic(HABITS_PATH, data)

    def get_habits(self, limit: int = 10) -> list[dict]:
        """Retourne les N dernières habitudes enregistrées."""
        return self._habits[-limit:]

    def update_habits(self, entry: dict):
        """Ajoute une entrée d'habitude, tronque à MAX_HABITS et persiste."""
        with _lock:
            self._habits.append(entry)
            if len(self._habits) > MAX_HABITS:
                self._habits = self._habits[-MAX_HABITS:]
            self._save(self._habits)

    def is_healthy(self) -> bool:
        """Vérifie que le dossier memory/ existe."""
        return os.path.exists(MEMORY_DIR)
