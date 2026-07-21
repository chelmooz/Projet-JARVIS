"""Service de logging — Écrit les événements dans logs/api.json au format JSON.

Responsabilité unique (SRP) :
- Persister les logs applicatifs dans un fichier JSON rotatif (borne MAX_LOG_ENTRIES).
- Garantir la résilience face à la corruption du fichier (réparation par raw_decode).
- Assurer la thread-safety des opérations de lecture/écriture (verrou global).
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

from config.constants import MAX_LOG_ENTRIES, PROJECT_DIR
from ports import LogPort, LogLevel
from services.file_utils import write_json_atomic

_logger = logging.getLogger("jarvis.log")

LOG_PATH = os.path.join(PROJECT_DIR, "logs", "api.json")
_lock = threading.Lock()

# Aligné sur les niveaux standards de logging Python (ports.LogPort)
_LEVELS: dict[str, int] = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "WARN": 2,  # Compatibilité ascendante
    "ERROR": 3,
    "CRITICAL": 4,
}


def _configure_root_logging() -> None:
    """Configure le logging racine (appelé au démarrage). Idempotent."""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.INFO)


class LogService(LogPort):
    """Service de persistance des logs applicatifs au format JSON."""

    def __init__(self) -> None:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        raw = os.environ.get("JARVIS_LOG_LEVEL", "INFO").upper()
        self._min_level = _LEVELS.get(raw, 1)

    def log(self, level: LogLevel, message: str) -> None:
        """Enregistre un événement de log si son niveau est suffisant."""
        level_upper = level.upper()
        if _LEVELS.get(level_upper, 1) < self._min_level:
            return

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level_upper,
            "message": message,
        }

        # Verrouillage critique pour éviter les race conditions read-modify-write
        with _lock:
            logs = self._load_logs()
            logs.append(entry)
            if len(logs) > MAX_LOG_ENTRIES:
                logs = logs[-MAX_LOG_ENTRIES:]
            write_json_atomic(LOG_PATH, logs, indent=2)

    def _load_logs(self) -> list[dict[str, Any]]:
        """Lit logs/api.json en tolérant les fichiers corrompus.

        En cas de JSON invalide (écriture interrompue, objets concaténés),
        on récupère les entrées valides en utilisant raw_decode itératif
        pour gérer le format indent=2 (une entrée sur plusieurs lignes).
        """
        try:
            with open(LOG_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (OSError, json.JSONDecodeError) as e:
            _logger.warning("Lecture JSON du log échouée (%s) — tentative de réparation", e)

        recovered: list[dict[str, Any]] = []
        try:
            with open(LOG_PATH, encoding="utf-8") as f:
                content = f.read()
            
            decoder = json.JSONDecoder()
            i = 0
            length = len(content)
            
            while i < length:
                # Sauter les espaces et séparateurs
                while i < length and content[i] in " \t\n\r,":
                    i += 1
                if i >= length:
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
        except OSError:
            return []

        if recovered:
            _logger.info("Log réparé : %d entrées récupérées sur fichier corrompu", len(recovered))
        
        return recovered


__all__ = ["LogService", "_configure_root_logging"]
