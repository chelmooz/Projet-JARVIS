"""Tests TDD refactor add_message — responsabilités isolées (3.B / SRP / KISS)."""
from services.conversation import MAX_MESSAGE_LENGTH, ConversationService


class TestAddMessageResponsibilities:

    def test_validate_rejects_bad_id(self):
        c = ConversationService()
        assert c._validate_conv_id("") is False
        assert c._validate_conv_id("../../../etc/passwd") is False
        assert c._validate_conv_id("abc-123_XY") is True

    def test_build_message_enriches_fields(self):
        c = ConversationService()
        msg = c._build_message("user", "hello", "dev", "phi4:latest")
        assert msg["role"] == "user"
        assert msg["content"] == "hello"
        assert msg["agent"] == "dev"
        assert msg["model"] == "phi4:latest"
        assert "id" in msg and "ts" in msg

    def test_build_message_applies_defaults(self):
        c = ConversationService()
        msg = c._build_message("user", "hi")
        assert msg["agent"] == ""
        assert msg["model"] == ""

    def test_build_message_truncates_content(self):
        c = ConversationService()
        long = "x" * (MAX_MESSAGE_LENGTH + 50)
        msg = c._build_message("user", long)
        assert len(msg["content"]) == MAX_MESSAGE_LENGTH

    def test_load_or_create_returns_existing(self):
        c = ConversationService()
        conv_id = c.create()
        conv = c._load_or_create(conv_id)
        assert conv["id"] == conv_id

    def test_load_or_create_creates_missing(self):
        c = ConversationService()
        conv = c._load_or_create("tdd_missing_id")
        assert conv is not None
        assert conv["id"] == "tdd_missing_id"
        assert c.get_conversation("tdd_missing_id") is not None

    def test_append_and_persist_writes_message(self):
        c = ConversationService()
        conv_id = c.create()
        conv = c._load_or_create(conv_id)
        msg = c._build_message("user", "hello")
        c._append_and_persist(conv_id, conv, msg)
        loaded = c.get_conversation(conv_id)
        assert len(loaded["messages"]) == 1
        assert loaded["messages"][0]["content"] == "hello"

    def test_update_index_reflects_count(self):
        c = ConversationService()
        conv_id = c.create()
        c._update_index(conv_id, msg_count=3)
        entry = next(e for e in c.list_all() if e["id"] == conv_id)
        assert entry["msg_count"] == 3

    def test_add_message_contract_unchanged(self):
        c = ConversationService()
        conv_id = c.create()
        c.add_message(conv_id, "user", "hello", agent="dev", model="phi4")
        conv = c.get_conversation(conv_id)
        assert len(conv["messages"]) == 1
        assert conv["messages"][0]["agent"] == "dev"
