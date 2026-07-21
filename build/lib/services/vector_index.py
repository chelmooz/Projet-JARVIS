"""VectorIndex — indexation, persistance et déduplication des documents.

Responsabilité unique (SRP) : gérer le dict ``documents`` de l'index vectoriel
(ajout avec dédup, lecture/écriture disque). Délègue le calcul d'embedding et
la similarité à d'autres modules spécialisés.
"""
import json
import threading

from services.file_utils import write_json_atomic


class VectorIndex:
    """Stocke et persiste les documents de l'index vectoriel (responsabilité IO)."""

    def __init__(self, data: dict, path: str = None, lock: threading.RLock = None):
        self._data = data
        self._path = path
        self._lock = lock or threading.RLock()

    def add_document(self, text: str, metadata: dict | None) -> bool:
        """Ajoute un document (dedup par texte). Retourne True si ajouté."""
        if any(d["text"] == text for d in self._data["documents"]):
            return False
        self._data["documents"].append({
            "text": text, "metadata": metadata or {}, "embedding": None,
        })
        return True

    def exists(self, text: str) -> bool:
        """Vérifie si un texte est déjà indexé."""
        return any(d["text"] == text for d in self._data["documents"])

    def save(self):
        """Persiste l'index sur disque (atomique, thread-safe)."""
        with self._lock:
            write_json_atomic(self._path, self._data)

    def load(self) -> dict:
        """Charge l'index depuis le disque, fallback dict vide."""
        import logging
        _logger = logging.getLogger("jarvis.vector")
        try:
            with open(self._path) as f:
                return json.load(f)
        except Exception as e:
            _logger.warning("Impossible de charger l index vectoriel (%s), demarrage a vide", e)
            return {"documents": [], "embeddings": []}
