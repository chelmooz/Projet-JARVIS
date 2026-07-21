"""VectorIndex — Indexation, persistance et déduplication O(1) des documents.

Refacto DevOps / SOLID / Thread-Safe :
- Déduplication en O(1) via un set de hachages (fin du scan linéaire O(N)).
- Thread-safety totale : toutes les mutations de _data sont protégées par _lock.
- Résilience : en cas de corruption, le fichier est sauvegardé en .bak avant réinitialisation.
- Cohérence du schéma de données garanti.
"""
import hashlib
import json
import logging
import os
import shutil
import threading
from typing import Optional

from services.file_utils import write_json_atomic

_logger = logging.getLogger("jarvis.vector.index")


class VectorIndex:
    """Stocke et persiste les documents de l'index vectoriel (responsabilité IO stricte)."""

    def __init__(self, data: dict, path: str, lock: threading.RLock):
        """
        Args:
            data: Le dictionnaire de données partagé (doit contenir "documents").
            path: Chemin du fichier de persistance.
            lock: Verrou partagé pour garantir la thread-safety.
        """
        self._data = data
        self._path = path
        self._lock = lock
        
        # Index secondaire pour déduplication O(1) des textes
        # On utilise un hash pour éviter de stocker les textes en double en mémoire
        self._text_hashes: set[str] = set()
        self._rebuild_hash_index()

    def _rebuild_hash_index(self):
        """Reconstruit l'index de hachage O(1) à partir des données existantes."""
        self._text_hashes.clear()
        for doc in self._data.get("documents", []):
            text_hash = hashlib.sha256(doc["text"].encode("utf-8")).hexdigest()
            self._text_hashes.add(text_hash)

    def _get_text_hash(self, text: str) -> str:
        """Calcule le hash SHA-256 d'un texte pour la déduplication."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def add_document(self, text: str, metadata: Optional[dict]) -> bool:
        """Ajoute un document (dedup O(1) par hash). Retourne True si ajouté."""
        text_hash = self._get_text_hash(text)
        
        with self._lock:
            if text_hash in self._text_hashes:
                return False  # Déjà présent
            
            # Ajout sécurisé
            self._data["documents"].append({
                "text": text,
                "metadata": metadata or {},
                "embedding": None,
            })
            self._text_hashes.add(text_hash)
            return True

    def exists(self, text: str) -> bool:
        """Vérifie si un texte est déjà indexé (O(1))."""
        text_hash = self._get_text_hash(text)
        with self._lock:
            return text_hash in self._text_hashes

    def save(self):
        """Persiste l'index sur disque de manière atomique et thread-safe."""
        with self._lock:
            try:
                write_json_atomic(self._path, self._data)
            except Exception as e:
                _logger.error("Échec critique de la sauvegarde de l'index vectoriel : %s", e)
                raise

    def load_secure(self) -> dict:
        """Charge l'index depuis le disque avec gestion robuste de la corruption."""
        if not os.path.exists(self._path):
            return {"documents": [], "embedding_dim": None}
        
        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validation du schéma minimal
            if isinstance(data, dict) and "documents" in data:
                # S'assurer que la clé embedding_dim existe pour la cohérence
                data.setdefault("embedding_dim", None)
                return data
            else:
                raise ValueError("Structure de données JSON invalide")
                
        except (json.JSONDecodeError, OSError, ValueError) as e:
            _logger.critical(
                "Fichier d'index vectoriel corrompu (%s). Sauvegarde et réinitialisation.", 
                self._path
            )
            # Sauvegarde du fichier corrompu pour analyse
            backup_path = self._path + ".corrupted.bak"
            try:
                if os.path.exists(self._path):
                    shutil.copy2(self._path, backup_path)
                    _logger.info("Fichier corrompu sauvegardé dans %s", backup_path)
            except OSError as backup_error:
                _logger.error("Échec de la sauvegarde du fichier corrompu : %s", backup_error)
            
            # Retourne un état vide mais schématiquement correct
            return {"documents": [], "embedding_dim": None}
