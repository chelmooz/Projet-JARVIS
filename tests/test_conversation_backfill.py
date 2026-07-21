"""TDD — backfill_message_ids : migration one-shot + skip si deja fait (perf USB)."""
import json

from services.conversation import ConversationService


def test_backfill_skips_when_flag_set(monkeypatch, tmp_path):
    svc = ConversationService(storage_dir=str(tmp_path))
    svc._index["_message_ids_backfilled"] = True
    opened = []
    real_open = open

    def _spy(p, *a, **k):
        opened.append(str(p))
        return real_open(p, *a, **k)

    monkeypatch.setattr("builtins.open", _spy)
    assert svc.backfill_message_ids() is False
    # Aucune lecture disque declenchee (early-return)
    assert opened == [], opened


def test_backfill_migrates_once_then_skips_on_reload(monkeypatch, tmp_path):
    conv_dir = tmp_path / "conversations"
    conv_dir.mkdir()
    (conv_dir / "abc.json").write_text(
        json.dumps({"id": "abc", "messages": [{"role": "user", "content": "hi"}]})
    )
    # Index adequat (comme en usage reel : entree + fichier)
    (tmp_path / "conversations.json").write_text(
        json.dumps({"conversations": [
            {"id": "abc", "title": "abc", "created_at": "x", "updated_at": "x", "msg_count": 1}
        ]})
    )

    # 1ere instance : migre (id attribue) + pose le flag persistant
    svc1 = ConversationService(storage_dir=str(tmp_path))
    data = json.loads((conv_dir / "abc.json").read_text())
    assert "id" in data["messages"][0]
    assert svc1._index.get("_message_ids_backfilled") is True

    # 2e instance : ne doit PAS relire le fichier conversation (flag)
    opened = []
    real_open = open

    def _spy(p, *a, **k):
        opened.append(str(p))
        return real_open(p, *a, **k)

    monkeypatch.setattr("builtins.open", _spy)
    ConversationService(storage_dir=str(tmp_path))
    conv_file = str(conv_dir / "abc.json")
    assert conv_file not in opened, f"backfill a rescanne {conv_file} : {opened}"
