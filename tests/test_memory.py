"""Tests MemoryService."""
import json
import os
import sys

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from services.memory import MemoryService


def _make_service(tmpdir):
    class TestMemory(MemoryService):
        def __init__(self):
            self._habits = []
            self._mem_dir = tmpdir
            self._habits_path = os.path.join(tmpdir, "habits.json")
        def _load(self): return self._habits
        def _save(self, data):
            with open(self._habits_path, "w") as f:
                json.dump(data, f)
        def is_healthy(self): return True
    return TestMemory()


class TestMemoryService:
    def test_get_habits_returns_list(self):
        m = MemoryService()
        m._habits = [{"task": "test"}]
        assert m.get_habits() == [{"task": "test"}]

    def test_get_habits_respects_limit(self):
        m = MemoryService()
        m._habits = [{"task": f"t{i}"} for i in range(20)]
        assert len(m.get_habits(5)) == 5

    def test_update_habits_appends(self):
        m = MemoryService()
        m._habits = []
        m.update_habits({"task": "hello"})
        assert len(m._habits) == 1
        assert m._habits[0]["task"] == "hello"

    def test_update_habits_trims_at_200(self):
        m = MemoryService()
        m._habits = [{"task": f"t{i}"} for i in range(200)]
        m.update_habits({"task": "last"})
        assert len(m._habits) == 200
        assert m._habits[-1]["task"] == "last"

    def test_is_healthy_returns_bool(self):
        m = MemoryService()
        assert isinstance(m.is_healthy(), bool)
