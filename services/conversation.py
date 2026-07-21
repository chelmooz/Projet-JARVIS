"""Service conversations — Stockage et gestion des conversations sur disque."""
from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import threading
import time
import uuid

from config.constants import MAX_CONVERSATION_MESSAGES, PROJECT_DIR
from ports import ConversationPort
from services.file_utils import write_json_atomic

_logger = logging.getLogger("jarvis.conversation")

# Sécurité : ID de conversation = uniquement alphanumérique + tirets
_VALID_CONV_ID = re.compile(r"^[a-zA-Z0-9_-]+$")

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"
CONV_ID_LENGTH = 8

# Taille max du contenu d'un message (caractères)
MAX_MESSAGE_LENGTH = 2000


class ConversationService(ConversationPort):
    """Stockage et gestion des conversations sur disque."""

    def __init__(self, storage_dir: str = None):
        """Initialise le dossier de stockage et charge l'index des conversations.

        Args:
            storage_dir: Répertoire de stockage (injectable). Par défaut PROJECT_DIR/memory/.
        """
        if storage_dir is None:
            storage_dir = os.path.join(PROJECT_DIR, "memory")
        self._storage_dir = storage_dir
        self._conv_dir = os.path.join(storage_dir, "conversations")
        os.makedirs(self._conv_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._on_message = None
        self._index_path = os.path.join(storage_dir, "conversations.json")
        self._index = self._load_index()
        self._save_index()  # Persiste le nettoyage des orphelins
        self.backfill_message_ids()  # Attribution d'id aux messages existants

    def _normalize_index(self, idx: dict) -> dict:
        """Normalise l'index : updated_at en string, msg_count garanti, nettoie les orphelins."""
        cleaned = []
        for c in idx.get("conversations", []):
            if not isinstance(c.get("updated_at"), str):
                c["updated_at"] = self._ts()
            c["msg_count"] = c.get("msg_count", 0) or 0
            # Vérifie que le fichier existe, sinon ignore (orphelin)
            conv_path = os.path.join(self._conv_dir, f"{c['id']}.json")
            if os.path.exists(conv_path):
                cleaned.append(c)
        idx["conversations"] = cleaned
        return idx

    def _load_index(self) -> dict:
        """Charge l'index (liste des conversations avec métadonnées)."""
        try:
            with open(self._index_path) as f:
                idx = self._normalize_index(json.load(f))
            return idx
        except Exception as e:
            _logger.debug("conversations.json illisible/absent, index vide: %s", e)
            return {"conversations": []}

    def _save_index(self):
        write_json_atomic(self._index_path, self._index, indent=2)

    @staticmethod
    def _ts() -> str:
        return time.strftime(ISO_FORMAT, time.localtime())

    def create(self, title: str = "Nouvelle conversation") -> str:
        """Crée une nouvelle conversation, retourne son ID (8 premiers chars d'un UUID4)."""
        with self._lock:
            conv_id = str(uuid.uuid4())[:CONV_ID_LENGTH]
            now = self._ts()
            self._index["conversations"].append({
                "id": conv_id, "title": title, "created_at": now,
                "updated_at": now, "msg_count": 0,
            })
            self._save_index()
            conv_path = os.path.join(self._conv_dir, f"{conv_id}.json")
        write_json_atomic(conv_path, {"id": conv_id, "messages": []})
        return conv_id

    @staticmethod
    def _validate_conv_id(conv_id: str) -> bool:
        """Valide le format de l'ID (protection contre les injections de chemin)."""
        return bool(_VALID_CONV_ID.match(conv_id))

    def add_message(self, conv_id: str, role: str, content: str,
                    agent: str = None, model: str = None,
                    backend: str = None):
        """Ajoute un message à une conversation. Crée la conversation si elle n'existe pas."""
        if not self._validate_conv_id(conv_id):
            raise ValueError(f"conv_id invalide: {conv_id!r}")
        msg = self._build_message(role, content, agent, model)
        with self._lock:
            conv = self._load_or_create(conv_id)
            self._append_and_persist(conv_id, conv, msg)
            self._update_index(conv_id, len(conv["messages"]))
        if self._on_message:
            self._on_message(conv_id, msg["id"], role, content, msg["ts"])

    def _build_message(self, role: str, content: str, agent: str = None,
                       model: str = None) -> dict:
        """Construit un message enrichi (id, ts, defaults, troncature)."""
        return {
            "id": uuid.uuid4().hex[:12],
            "role": role,
            "content": content[:MAX_MESSAGE_LENGTH],
            "agent": agent or "",
            "model": model or "",
            "ts": time.time(),
        }

    def _load_or_create(self, conv_id: str) -> dict:
        """Charge la conversation, la crée (vide) si illisible/absente."""
        conv_path = os.path.join(self._conv_dir, f"{conv_id}.json")
        try:
            with open(conv_path) as f:
                return json.load(f)
        except Exception as e:
            _logger.debug("conversation %s illisible/absente, reinitialisee: %s", conv_id, e)
            self._register_missing(conv_id)
            return {"id": conv_id, "messages": []}

    def _register_missing(self, conv_id: str):
        """Ajoute l'entrée d'index et persiste le fichier d'une conversation neuve."""
        now = self._ts()
        self._index["conversations"].append({
            "id": conv_id, "title": f"Conversation {conv_id}",
            "created_at": now, "updated_at": now, "msg_count": 0,
        })
        write_json_atomic(os.path.join(self._conv_dir, f"{conv_id}.json"),
                          {"id": conv_id, "messages": []})

    def _append_and_persist(self, conv_id: str, conv: dict, msg: dict):
        """Ajoute le message et persiste le fichier conversation.

        Fenêtre glissante : si la conversation dépasse MAX_CONVERSATION_MESSAGES,
        seuls les derniers messages sont conservés (évite un JSON qui grossit
        indéfiniment, coûteux à recharger sur cle USB lente).
        """
        conv["messages"].append(msg)
        if len(conv["messages"]) > MAX_CONVERSATION_MESSAGES:
            conv["messages"] = conv["messages"][-MAX_CONVERSATION_MESSAGES:]
        conv_path = os.path.join(self._conv_dir, f"{conv_id}.json")
        write_json_atomic(conv_path, conv, indent=2)

    def _update_index(self, conv_id: str, msg_count: int):
        """Met à jour le compteur et la date de la conversation dans l'index."""
        for c in self._index["conversations"]:
            if c["id"] == conv_id:
                c["msg_count"] = msg_count
                c["updated_at"] = self._ts()
                break
        self._save_index()

    def get_conversation(self, conv_id: str) -> dict | None:
        """Récupère une conversation complète avec ses messages."""
        if not self._validate_conv_id(conv_id):
            return None
        conv_path = os.path.join(self._conv_dir, f"{conv_id}.json")
        try:
            with open(conv_path) as f:
                return json.load(f)
        except Exception as e:
            _logger.debug("conversation %s illisible/absente: %s", conv_id, e)
            return None

    def list_all(self) -> list[dict]:
        """Retourne la liste des conversations (métadonnées, sans les messages)."""
        return self._index.get("conversations", [])

    def list_unindexed(self, limit: int | None = None) -> list[dict]:
        """Retourne les conversations non encore indexées (indexed != True).

        Utilisé par la vectorisation pour ne traiter chaque conversation qu'une
        seule fois (idempotence) sans la supprimer. `limit=None` = toutes.
        """
        items = [c for c in self._index.get("conversations", []) if not c.get("indexed")]
        if limit is not None:
            items = items[:limit]
        return items

    def mark_indexed(self, conv_id: str):
        """Marque une conversation comme indexée (vectorisée). Non destructive."""
        if not self._validate_conv_id(conv_id):
            return
        with self._lock:
            for c in self._index["conversations"]:
                if c["id"] == conv_id:
                    c["indexed"] = True
                    break
            self._save_index()

    def set_on_message(self, callback):
        """Enregistre un hook appele a chaque nouveau message (auto-ingest vectoriel)."""
        self._on_message = callback

    def backfill_message_ids(self):
        """Attribue un `id` aux messages existants qui n'en ont pas (non destructif).

        Migration one-shot : comme `add_message` assigne toujours un `id`, un seul
        passage suffit. Un flag persistant `_message_ids_backfilled` dans l'index évite
        de rescanner toutes les conversations (N lectures disque) à chaque démarrage
        sur clef USB lente.
        """
        if self._index.get("_message_ids_backfilled"):
            return False
        changed_any = False
        for entry in self._index.get("conversations", []):
            conv_path = os.path.join(self._conv_dir, f"{entry['id']}.json")
            if not os.path.exists(conv_path):
                continue
            try:
                with open(conv_path) as f:
                    conv = json.load(f)
                changed = False
                for msg in conv.get("messages", []):
                    if "id" not in msg:
                        msg["id"] = uuid.uuid4().hex[:12]
                        changed = True
                if changed:
                    write_json_atomic(conv_path, conv, indent=2)
                    changed_any = True
            except Exception as e:
                _logger.debug("backfill ignore conversation %s (illisible/corrompue): %s", entry.get("id"), e)
                continue
        self._index["_message_ids_backfilled"] = True
        self._save_index()
        return changed_any

    def delete(self, conv_id: str):
        """Supprime une conversation (index + fichier)."""
        if not self._validate_conv_id(conv_id):
            return
        with self._lock:
            self._index["conversations"] = [
                c for c in self._index["conversations"] if c["id"] != conv_id
            ]
            self._save_index()
            conv_path = os.path.join(self._conv_dir, f"{conv_id}.json")
            with contextlib.suppress(Exception):
                os.remove(conv_path)

    def delete_all(self):
        """Supprime toutes les conversations (index + tous les fichiers)."""
        with self._lock:
            self._index["conversations"] = []
            self._save_index()
            for f in os.listdir(self._conv_dir):
                if f.endswith(".json"):
                    with contextlib.suppress(Exception):
                        os.remove(os.path.join(self._conv_dir, f))

    def is_healthy(self) -> bool:
        """Vérifie que le dossier de stockage existe."""
        return os.path.exists(self._conv_dir)
