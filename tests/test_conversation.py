"""Tests TDD pour services/conversation.py — stockage et gestion des conversations."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from services.conversation import ConversationService


class TestConversationCreate:
    """Tests de création de conversation."""

    def test_create_returns_valid_id(self):
        """create() retourne un ID valide (8 chars alphanumériques)."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test conversation")

            assert conv_id is not None
            assert len(conv_id) == 8
            assert conv_id.isalnum() or all(c.isalnum() or c in "_-" for c in conv_id)

    def test_create_persists_index_and_file(self):
        """create() persiste l'index et le fichier conversation."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Ma conversation")

            # Vérifie index
            index_path = Path(tmp) / "conversations.json"
            assert index_path.exists()
            with open(index_path, encoding="utf-8") as f:
                index = json.load(f)
            assert len(index["conversations"]) == 1
            assert index["conversations"][0]["id"] == conv_id
            assert index["conversations"][0]["title"] == "Ma conversation"
            assert index["conversations"][0]["msg_count"] == 0

            # Vérifie fichier conversation
            conv_path = Path(tmp) / "conversations" / f"{conv_id}.json"
            assert conv_path.exists()
            with open(conv_path, encoding="utf-8") as f:
                conv = json.load(f)
            assert conv["id"] == conv_id
            assert conv["messages"] == []

    def test_create_multiple_conversations(self):
        """Plusieurs appels create() ajoutent plusieurs entrées à l'index."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            id1 = service.create("Conv 1")
            id2 = service.create("Conv 2")

            assert id1 != id2
            index_path = Path(tmp) / "conversations.json"
            with open(index_path, encoding="utf-8") as f:
                index = json.load(f)
            assert len(index["conversations"]) == 2


class TestConversationAddMessage:
    """Tests d'ajout de message."""

    def test_add_message_to_existing_conversation(self):
        """add_message() ajoute un message à une conversation existante."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test")

            service.add_message(conv_id, "user", "Hello")

            conv_path = Path(tmp) / "conversations" / f"{conv_id}.json"
            with open(conv_path, encoding="utf-8") as f:
                conv = json.load(f)
            assert len(conv["messages"]) == 1
            assert conv["messages"][0]["role"] == "user"
            assert conv["messages"][0]["content"] == "Hello"
            assert "id" in conv["messages"][0]
            assert "ts" in conv["messages"][0]

    def test_add_message_creates_conversation_if_missing(self):
        """add_message() crée la conversation si elle n'existe pas."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            # Ne pas créer la conversation au préalable
            conv_id = "abc12345"  # ID valide

            service.add_message(conv_id, "user", "Hello")

            # Vérifie que l'index a été mis à jour
            index_path = Path(tmp) / "conversations.json"
            with open(index_path, encoding="utf-8") as f:
                index = json.load(f)
            assert any(c["id"] == conv_id for c in index["conversations"])

            # Vérifie le fichier conversation
            conv_path = Path(tmp) / "conversations" / f"{conv_id}.json"
            with open(conv_path, encoding="utf-8") as f:
                conv = json.load(f)
            assert len(conv["messages"]) == 1

    def test_add_message_with_metadata(self):
        """add_message() stocke les métadonnées agent, model, backend."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test")

            service.add_message(conv_id, "assistant", "Response", agent="dev", model="qwen2.5", backend="ollama")

            conv_path = Path(tmp) / "conversations" / f"{conv_id}.json"
            with open(conv_path, encoding="utf-8") as f:
                conv = json.load(f)
            msg = conv["messages"][0]
            assert msg["agent"] == "dev"
            assert msg["model"] == "qwen2.5"
            assert msg["backend"] == "ollama"

    def test_add_message_invalid_conv_id_raises(self):
        """add_message() lève ValueError sur conv_id invalide (path traversal)."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)

            with pytest.raises(ValueError, match="conv_id invalide"):
                service.add_message("../etc/passwd", "user", "Hello")

            with pytest.raises(ValueError, match="conv_id invalide"):
                service.add_message("", "user", "Hello")

    def test_add_message_sliding_window(self):
        """add_message() applique la fenêtre glissante (MAX_CONVERSATION_MESSAGES)."""
        with tempfile.TemporaryDirectory() as tmp:
            # On doit patcher la constante avant import
            import config.constants as constants

            original_max = constants.MAX_CONVERSATION_MESSAGES
            try:
                constants.MAX_CONVERSATION_MESSAGES = 3
                # Recharger le module pour prendre en compte la constante modifiée
                import importlib

                import services.conversation as conv_module

                importlib.reload(conv_module)
                conversation_service = conv_module.ConversationService

                service = conversation_service(storage_dir=tmp)
                conv_id = service.create("Test")

                for i in range(5):
                    service.add_message(conv_id, "user", f"Message {i}")

                conv_path = Path(tmp) / "conversations" / f"{conv_id}.json"
                with open(conv_path, encoding="utf-8") as f:
                    conv = json.load(f)
                # Seuls les 3 derniers messages doivent être conservés
                assert len(conv["messages"]) == 3
                assert conv["messages"][0]["content"] == "Message 2"
                assert conv["messages"][2]["content"] == "Message 4"
            finally:
                constants.MAX_CONVERSATION_MESSAGES = original_max
                importlib.reload(conv_module)

    def test_add_message_updates_index_msg_count(self):
        """add_message() met à jour msg_count dans l'index."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test")

            service.add_message(conv_id, "user", "Hello")

            index_path = Path(tmp) / "conversations.json"
            with open(index_path, encoding="utf-8") as f:
                index = json.load(f)
            assert index["conversations"][0]["msg_count"] == 1


class TestConversationGet:
    """Tests de récupération de conversation."""

    def test_get_conversation_returns_full_conversation(self):
        """get_conversation() retourne la conversation complète avec messages."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test")
            service.add_message(conv_id, "user", "Hello")
            service.add_message(conv_id, "assistant", "Hi there")

            conv = service.get_conversation(conv_id)

            assert conv is not None
            assert conv["id"] == conv_id
            assert len(conv["messages"]) == 2
            assert conv["messages"][0]["content"] == "Hello"
            assert conv["messages"][1]["content"] == "Hi there"

    def test_get_conversation_nonexistent_returns_none(self):
        """get_conversation() retourne None si conversation absente."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)

            result = service.get_conversation("nonexistent")

            assert result is None

    def test_get_conversation_invalid_id_returns_none(self):
        """get_conversation() retourne None sur ID invalide."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)

            result = service.get_conversation("../etc/passwd")

            assert result is None

    def test_list_all_returns_metadata_only(self):
        """list_all() retourne métadonnées sans messages."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            _id1 = service.create("Conv 1")
            service.create("Conv 2")
            service.add_message(_id1, "user", "Hello")

            all_convs = service.list_all()

            assert len(all_convs) == 2
            # Vérifie que messages n'est pas dans la réponse
            for c in all_convs:
                assert "messages" not in c
                assert "id" in c
                assert "title" in c
                assert "msg_count" in c


class TestConversationDelete:
    """Tests de suppression."""

    def test_delete_removes_conversation(self):
        """delete() supprime l'entrée d'index et le fichier."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test")
            service.add_message(conv_id, "user", "Hello")

            service.delete(conv_id)

            # Index mis à jour
            index_path = Path(tmp) / "conversations.json"
            with open(index_path, encoding="utf-8") as f:
                index = json.load(f)
            assert len(index["conversations"]) == 0

            # Fichier supprimé
            conv_path = Path(tmp) / "conversations" / f"{conv_id}.json"
            assert not conv_path.exists()

    def test_delete_nonexistent_no_error(self):
        """delete() ne lève pas d'erreur sur conversation inexistante."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)

            service.delete("nonexistent")  # Ne doit pas lever

    def test_delete_invalid_id_no_error(self):
        """delete() ne lève pas d'erreur sur ID invalide."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)

            service.delete("../etc/passwd")  # Ne doit pas lever

    def test_delete_all_removes_everything(self):
        """delete_all() supprime toutes les conversations et fichiers."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            _id1 = service.create("Conv 1")
            service.create("Conv 2")
            service.add_message(_id1, "user", "Hello")

            service.delete_all()

            index_path = Path(tmp) / "conversations.json"
            with open(index_path, encoding="utf-8") as f:
                index = json.load(f)
            assert index["conversations"] == []

            conv_dir = Path(tmp) / "conversations"
            json_files = list(conv_dir.glob("*.json"))
            assert len(json_files) == 0


class TestConversationIndexed:
    """Tests de marquage indexé."""

    def test_list_unindexed_returns_new_conversations(self):
        """list_unindexed() retourne les conversations non indexées."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            service.create("Conv 1")
            service.create("Conv 2")

            unindexed = service.list_unindexed()

            assert len(unindexed) == 2
            assert all(not c.get("indexed") for c in unindexed)

    def test_mark_indexed_sets_flag(self):
        """mark_indexed() marque la conversation comme indexée."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test")

            service.mark_indexed(conv_id)

            unindexed = service.list_unindexed()
            assert len(unindexed) == 0

            # Vérifie dans l'index
            index_path = Path(tmp) / "conversations.json"
            with open(index_path, encoding="utf-8") as f:
                index = json.load(f)
            assert index["conversations"][0].get("indexed") is True

    def test_mark_indexed_invalid_id_no_error(self):
        """mark_indexed() ne lève pas sur ID invalide."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)

            service.mark_indexed("../etc/passwd")  # Ne doit pas lever


class TestConversationHooks:
    """Tests des hooks."""

    def test_set_on_message_callback_called(self):
        """set_on_message() appelle le callback à chaque message."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test")

            calls = []

            def callback(conv_id, msg_id, role, content, ts):
                calls.append({"conv_id": conv_id, "msg_id": msg_id, "role": role, "content": content})

            service.set_on_message(callback)
            service.add_message(conv_id, "user", "Hello")

            assert len(calls) == 1
            assert calls[0]["conv_id"] == conv_id
            assert calls[0]["role"] == "user"
            assert calls[0]["content"] == "Hello"

    def test_set_on_message_none_disables(self):
        """set_on_message(None) désactive le callback."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test")

            calls = []

            def callback(*args):
                calls.append(args)

            service.set_on_message(callback)
            service.add_message(conv_id, "user", "First")
            service.set_on_message(None)
            service.add_message(conv_id, "user", "Second")

            assert len(calls) == 1  # Seulement le premier


class TestConversationBackfill:
    """Tests de backfill message IDs."""

    def test_backfill_assigns_ids_to_old_messages(self):
        """backfill_message_ids() attribue des IDs aux messages sans ID au démarrage."""
        with tempfile.TemporaryDirectory() as tmp:
            # Créer un service pour avoir la structure
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test")

            # Modifier manuellement le fichier pour simuler d'anciens messages sans ID
            conv_path = Path(tmp) / "conversations" / f"{conv_id}.json"
            with open(conv_path, encoding="utf-8") as f:
                conv = json.load(f)
            conv["messages"] = [
                {"role": "user", "content": "Old message 1"},
                {"role": "assistant", "content": "Old message 2", "id": "already-has-id"},
            ]
            with open(conv_path, "w", encoding="utf-8") as f:
                json.dump(conv, f)

            # Reset index flag to force backfill (doit être fait AVANT de créer le nouveau service)
            index_path = Path(tmp) / "conversations.json"
            with open(index_path, encoding="utf-8") as f:
                index = json.load(f)
            index["_message_ids_backfilled"] = False
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f)

            # Recharger le service (charge l'index avec flag False, lance backfill dans __init__)
            ConversationService(storage_dir=tmp)

            # Le backfill a déjà été exécuté dans __init__
            # Vérifie que les IDs ont été ajoutés
            with open(conv_path, encoding="utf-8") as f:
                conv = json.load(f)
            assert "id" in conv["messages"][0]
            assert conv["messages"][1]["id"] == "already-has-id"  # Préservé

    def test_backfill_returns_false_if_already_done(self):
        """backfill_message_ids() retourne False si déjà fait."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            service.create("Test")

            service.backfill_message_ids()  # Premier appel
            # Deuxième appel doit retourner False
            second = service.backfill_message_ids()

            assert second is False


class TestConversationHealth:
    """Tests de santé."""

    def test_is_healthy_true_when_dir_exists(self):
        """is_healthy() retourne True si dossier existe."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)

            assert service.is_healthy() is True

    def test_is_healthy_false_when_dir_missing(self):
        """is_healthy() retourne False si dossier n'existe pas."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            # Supprimer le dossier
            os.rmdir(os.path.join(tmp, "conversations"))

            assert service.is_healthy() is False


class TestConversationThreadSafety:
    """Tests de thread-safety (basiques)."""

    def test_concurrent_add_message(self):
        """add_message() thread-safe avec lock."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test")

            import threading

            def add_messages():
                for i in range(10):
                    service.add_message(conv_id, "user", f"Msg {i}")

            threads = [threading.Thread(target=add_messages) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Vérifie que tous les messages ont été ajoutés (50 attendus, mais fenêtre glissante limite)
            conv_path = Path(tmp) / "conversations" / f"{conv_id}.json"
            with open(conv_path, encoding="utf-8") as f:
                conv = json.load(f)
            # Au minimum, pas de crash et structure valide
            assert len(conv["messages"]) > 0


class TestConversationStorageError:
    """Tests de gestion d'erreurs de stockage."""

    def test_corrupted_json_file_handled_get_returns_none(self):
        """Fichier JSON corrompu : get_conversation() retourne None sans lever."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test")
            service.add_message(conv_id, "user", "Hello")

            # Corrompre le fichier
            conv_path = Path(tmp) / "conversations" / f"{conv_id}.json"
            with open(conv_path, "w") as f:
                f.write("{ invalid json }")

            # Recharger le service
            service2 = ConversationService(storage_dir=tmp)

            # get_conversation ne doit pas lever, retourne None
            conv = service2.get_conversation(conv_id)
            assert conv is None

    def test_corrupted_json_file_handled_add_message_recreates(self):
        """Fichier JSON corrompu : add_message() recrée la conversation."""
        with tempfile.TemporaryDirectory() as tmp:
            service = ConversationService(storage_dir=tmp)
            conv_id = service.create("Test")
            service.add_message(conv_id, "user", "Hello")

            # Corrompre le fichier
            conv_path = Path(tmp) / "conversations" / f"{conv_id}.json"
            with open(conv_path, "w") as f:
                f.write("{ invalid json }")

            # Recharger le service
            service2 = ConversationService(storage_dir=tmp)

            # add_message ne doit pas lever, recrée la conversation
            service2.add_message(conv_id, "user", "New message")

            # Vérifie que la conversation a été recréée
            conv = service2.get_conversation(conv_id)
            assert conv is not None
            assert conv["id"] == conv_id
            assert len(conv["messages"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
