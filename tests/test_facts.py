"""Tests pour services.facts — FactStore horodatés persistants."""
import json
import os
import sys
import time

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from services.facts import FactStore


class TestFactStoreAdd:
    """FactStore.add() : ajoute un fait et persiste."""

    def test_adds_fact_with_text_metadata_source_and_timestamp(self, monkeypatch, tmp_path):
        monkeypatch.setattr("services.facts.MEMORY_DIR", str(tmp_path))
        monkeypatch.setattr("services.facts.FACTS_PATH", str(tmp_path / "facts.json"))
        store = FactStore()
        store.add("test fact", {"key": "val"}, "test")
        assert len(store._facts) == 1
        fact = store._facts[0]
        assert fact["text"] == "test fact"
        assert fact["metadata"] == {"key": "val"}
        assert fact["source"] == "test"
        assert "ts" in fact

    def test_persists_fact_to_disk(self, monkeypatch, tmp_path):
        monkeypatch.setattr("services.facts.MEMORY_DIR", str(tmp_path))
        monkeypatch.setattr("services.facts.FACTS_PATH", str(tmp_path / "facts.json"))
        store = FactStore()
        store.add("persistent fact", {}, "user")
        assert (tmp_path / "facts.json").exists()
        with open(tmp_path / "facts.json", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["text"] == "persistent fact"


class TestFactStoreRemoveOld:
    """FactStore.remove_old() : filtre les faits par timestamp."""

    def test_removes_facts_before_cutoff(self, monkeypatch, tmp_path):
        monkeypatch.setattr("services.facts.MEMORY_DIR", str(tmp_path))
        monkeypatch.setattr("services.facts.FACTS_PATH", str(tmp_path / "facts.json"))
        store = FactStore()
        now = time.time()
        store._facts = [
            {"text": "old", "metadata": {}, "source": "test", "ts": now - 100},
            {"text": "new", "metadata": {}, "source": "test", "ts": now},
        ]
        removed = store.remove_old(now)
        assert removed == 1
        assert len(store._facts) == 1
        assert store._facts[0]["text"] == "new"

    def test_keeps_facts_after_cutoff(self, monkeypatch, tmp_path):
        monkeypatch.setattr("services.facts.MEMORY_DIR", str(tmp_path))
        monkeypatch.setattr("services.facts.FACTS_PATH", str(tmp_path / "facts.json"))
        store = FactStore()
        now = time.time()
        store._facts = [
            {"text": "a", "metadata": {}, "source": "test", "ts": now + 10},
            {"text": "b", "metadata": {}, "source": "test", "ts": now + 20},
        ]
        removed = store.remove_old(now)
        assert removed == 0
        assert len(store._facts) == 2

    def test_remove_old_returns_count_of_removed(self, monkeypatch, tmp_path):
        monkeypatch.setattr("services.facts.MEMORY_DIR", str(tmp_path))
        monkeypatch.setattr("services.facts.FACTS_PATH", str(tmp_path / "facts.json"))
        store = FactStore()
        now = time.time()
        store._facts = [
            {"text": "x", "metadata": {}, "source": "test", "ts": now - 50},
            {"text": "y", "metadata": {}, "source": "test", "ts": now - 30},
            {"text": "z", "metadata": {}, "source": "test", "ts": now + 10},
        ]
        assert store.remove_old(now) == 2
