"""Service de logging — Écrit les événements dans logs/api.json au format JSON."""
import json
import logging
import os
import threading
from datetime import datetime

from config.constants import MAX_LOG_ENTRIES, PROJECT_DIR
from ports import LogPort
from services.file_utils import write_json_atomic

_logger = logging.getLogger("jarvis.log")

LOG_PATH = os.path.join(PROJECT_DIR, "logs", "api.json")
_lock = threading.Lock()

_LEVELS = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}


def _configure_root_logging():
    """Configure le logging racine (appelé au démarrage). Idempotent."""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)


class LogService(LogPort):
    """LogService."""

    def __init__(self):
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        raw = os.environ.get("JARVIS_LOG_LEVEL", "INFO").upper()
        self._min_level = _LEVELS.get(raw, 1)
        self.dev_mode = os.environ.get("JARVIS_DEV", "").lower() in ("1", "true", "yes")
        if self.dev_mode:
            _logger.info("Mode developpement active — stack traces completes")

    def log(self, level: str, message: str):
        """Log."""
        if _LEVELS.get(level.upper(), 1) < self._min_level:
            return
        entry = {
            "ts": datetime.now().isoformat(),
            "level": level,
            "message": message,
        }
        logs = self._load_logs()
        logs.append(entry)
        if len(logs) > MAX_LOG_ENTRIES:
            logs = logs[-MAX_LOG_ENTRIES:]
        write_json_atomic(LOG_PATH, logs, indent=2)

    def _load_logs(self):
        """Lit logs/api.json en tolerant les fichiers corrompus.

        En cas de JSON invalide (ecriture interrompue, objets concaténés),
        on recupere les entrées valides en utilisant raw_decode iteratif
        pour gerer le format indent=2 (une entree sur plusieurs lignes).
        """
        try:
            with open(LOG_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception as e:
            _logger.warning("Lecture JSON du log echouee (%s) — reparation", e)
        recovered = []
        try:
            with open(LOG_PATH, encoding="utf-8") as f:
                content = f.read()
            decoder = json.JSONDecoder()
            i = 0
            while i < len(content):
                while i < len(content) and content[i] in " \t\n\r,":
                    i += 1
                if i >= len(content):
                    break
                if content[i] == "{":
                    try:
                        obj, end = decoder.raw_decode(content, i)
                        if isinstance(obj, dict):
                            recovered.append(obj)
                        i = end
                    except json.JSONDecodeError:
                        i += 1
                else:
                    i += 1
        except Exception:
            return []
        if recovered:
            _logger.info("Log réparé : %d entrées recupérées sur fichier corrompu", len(recovered))
        return recovered
