"""TDD — Bornage contexte conversationnel (M23f)."""
import services.conversation as conversation


def test_append_keeps_recent_window(monkeypatch, tmp_path):
    # On reduit la fenetre pour le test (sinon 200 messages)
    monkeypatch.setattr(conversation, "MAX_CONVERSATION_MESSAGES", 3)
    svc = conversation.ConversationService(storage_dir=str(tmp_path))
    cid = "testconv"
    for i in range(5):
        svc.add_message(cid, "user", f"msg {i}")
    conv = svc.get_conversation(cid)
    # Seulement les 3 derniers doivent rester
    assert len(conv["messages"]) == 3
    assert conv["messages"][0]["content"] == "msg 2"
    assert conv["messages"][-1]["content"] == "msg 4"


def test_append_under_limit_keeps_all(monkeypatch, tmp_path):
    monkeypatch.setattr(conversation, "MAX_CONVERSATION_MESSAGES", 3)
    svc = conversation.ConversationService(storage_dir=str(tmp_path))
    cid = "small"
    svc.add_message(cid, "user", "a")
    svc.add_message(cid, "user", "b")
    conv = svc.get_conversation(cid)
    assert len(conv["messages"]) == 2
