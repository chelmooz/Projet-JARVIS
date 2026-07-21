"""Tests ConversationService — CRUD conversations."""
from services.conversation import ConversationService


class TestConversation:

    def test_create_returns_string_id(self):
        c = ConversationService()
        conv_id = c.create()
        assert conv_id is not None

    def test_get_returns_created_conversation(self):
        c = ConversationService()
        conv_id = c.create()
        conv = c.get_conversation(conv_id)
        assert conv is not None
        assert conv["id"] == conv_id

    def test_add_message_increments_count(self):
        c = ConversationService()
        conv_id = c.create()
        c.add_message(conv_id, "user", "hello")
        c.add_message(conv_id, "assistant", "hi", agent="dev", model="phi4-mini:3.8b")
        conv = c.get_conversation(conv_id)
        assert len(conv["messages"]) == 2

    def test_list_returns_ids(self):
        c = ConversationService()
        before = len(c.list_all())
        c.create()
        c.create()
        assert len(c.list_all()) >= before + 2

    def test_delete_removes_conversation(self):
        c = ConversationService()
        conv_id = c.create()
        c.delete(conv_id)
        assert c.get_conversation(conv_id) is None

    def test_delete_all(self):
        c = ConversationService()
        c.create()
        c.delete_all()
        assert c.list_all() == []

    def test_invalid_id_returns_none(self):
        c = ConversationService()
        assert c.get_conversation("nonexistent") is None

    def test_is_healthy(self):
        c = ConversationService()
        assert c.is_healthy() is True

    def test_add_message_auto_creates_if_not_exists(self):
        c = ConversationService()
        c.add_message("auto_create_test", "user", "hello auto")
        conv = c.get_conversation("auto_create_test")
        assert conv is not None
        assert len(conv["messages"]) == 1
        assert conv["messages"][0]["content"] == "hello auto"
