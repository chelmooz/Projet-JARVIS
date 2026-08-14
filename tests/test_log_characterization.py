"""Tests de caractérisation pour ``services/log.py`` (Lot F3).

Verrouille le comportement actuel AVANT tout refactor (extraction d'un
parseur de ligne pur, séparation lecture / rotation / filtrage, Lot F4) :

- ``LogService._load_logs`` : fichier absent, JSON valide (liste), JSON
  invalide (récupération par ``raw_decode`` itératif), JSON valide mais pas
  une liste (ex: objet racine), entrées partiellement malformées (fragments
  non-dict ignorés) ;
- ``LogService.log`` : rotation bornée par ``MAX_LOG_ENTRIES``, filtre de
  niveau minimal (défaut ``INFO``, override via ``JARVIS_LOG_LEVEL``),
  alias ``WARN``/``WARNING``.

Isolation : ``services.log.LOG_PATH`` est monkeypatché vers un fichier
temporaire à chaque test — aucune écriture dans le vrai ``logs/api.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import services.log as log_module
from services.log import LogService


@pytest.fixture
def log_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirige LOG_PATH vers un fichier temporaire isolé."""
    path = tmp_path / "logs" / "api.json"
    monkeypatch.setattr(log_module, "LOG_PATH", str(path))
    return path


@pytest.fixture
def service(log_path: Path, monkeypatch: pytest.MonkeyPatch) -> LogService:
    """Service avec niveau par défaut (INFO, pas de JARVIS_LOG_LEVEL)."""
    monkeypatch.delenv("JARVIS_LOG_LEVEL", raising=False)
    return LogService()


class TestLoadLogsFileAbsent:
    def test_missing_file_returns_empty_list(self, service: LogService) -> None:
        assert service._load_logs() == []


class TestLoadLogsValidJson:
    def test_valid_json_list_returned_as_is(self, service: LogService, log_path: Path) -> None:
        entries = [{"ts": "t1", "level": "INFO", "message": "a"}, {"ts": "t2", "level": "ERROR", "message": "b"}]
        log_path.write_text(json.dumps(entries), encoding="utf-8")

        assert service._load_logs() == entries

    def test_valid_json_but_not_a_list_falls_back_to_recovery(self, service: LogService, log_path: Path) -> None:
        """Un objet JSON racine (pas une liste) : isinstance(data, list) est False,
        donc le code tombe dans le chemin de récupération raw_decode — qui ne
        récupère que des ``{...}`` top-level, pas les clés d'un objet unique.
        """
        log_path.write_text(json.dumps({"ts": "t1", "level": "INFO", "message": "a"}), encoding="utf-8")

        result = service._load_logs()

        assert result == [{"ts": "t1", "level": "INFO", "message": "a"}]


class TestLoadLogsCorruptedRecovery:
    def test_truncated_json_recovers_valid_entries(self, service: LogService, log_path: Path) -> None:
        """Écriture interrompue en fin de fichier : entrée finale tronquée ignorée."""
        content = '[\n{"ts": "t1", "level": "INFO", "message": "a"},\n{"ts": "t2", "level": "ERROR", "mess'
        log_path.write_text(content, encoding="utf-8")

        result = service._load_logs()

        assert result == [{"ts": "t1", "level": "INFO", "message": "a"}]

    def test_concatenated_objects_without_valid_array_wrapper_recovered(
        self, service: LogService, log_path: Path
    ) -> None:
        """Objets concaténés (pas un tableau JSON valide) : chacun récupéré individuellement."""
        content = '{"ts": "t1", "level": "INFO", "message": "a"}{"ts": "t2", "level": "WARNING", "message": "b"}'
        log_path.write_text(content, encoding="utf-8")

        result = service._load_logs()

        assert result == [
            {"ts": "t1", "level": "INFO", "message": "a"},
            {"ts": "t2", "level": "WARNING", "message": "b"},
        ]

    def test_non_dict_fragments_are_skipped(self, service: LogService, log_path: Path) -> None:
        """Un fragment JSON valide mais non-dict (ex: un nombre) n'est pas récupéré."""
        content = '[{"ts": "t1", "level": "INFO", "message": "a"}, 42, {"ts": "t2", "level": "ERROR", "message": "b"}'
        log_path.write_text(content, encoding="utf-8")

        result = service._load_logs()

        assert result == [
            {"ts": "t1", "level": "INFO", "message": "a"},
            {"ts": "t2", "level": "ERROR", "message": "b"},
        ]

    def test_empty_file_recovers_empty_list(self, service: LogService, log_path: Path) -> None:
        log_path.write_text("", encoding="utf-8")

        assert service._load_logs() == []

    def test_garbage_content_recovers_empty_list(self, service: LogService, log_path: Path) -> None:
        log_path.write_text("not json at all !!!", encoding="utf-8")

        assert service._load_logs() == []


class TestLogRotation:
    def test_rotation_keeps_only_last_max_log_entries(
        self, service: LogService, log_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(log_module, "MAX_LOG_ENTRIES", 3)
        for i in range(5):
            service.log("INFO", f"msg-{i}")

        data = json.loads(log_path.read_text(encoding="utf-8"))

        assert len(data) == 3
        assert [e["message"] for e in data] == ["msg-2", "msg-3", "msg-4"]

    def test_no_rotation_when_under_limit(
        self, service: LogService, log_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(log_module, "MAX_LOG_ENTRIES", 10)
        for i in range(3):
            service.log("INFO", f"msg-{i}")

        data = json.loads(log_path.read_text(encoding="utf-8"))

        assert len(data) == 3


class TestLogLevelFilter:
    def test_default_min_level_is_info_debug_dropped(self, service: LogService, log_path: Path) -> None:
        service.log("DEBUG", "should be dropped")

        assert not log_path.exists()

    def test_default_min_level_lets_info_through(self, service: LogService, log_path: Path) -> None:
        service.log("INFO", "kept")

        data = json.loads(log_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["message"] == "kept"

    def test_env_override_raises_min_level_to_error(self, log_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JARVIS_LOG_LEVEL", "ERROR")
        svc = LogService()

        svc.log("WARNING", "dropped")
        svc.log("ERROR", "kept")

        data = json.loads(log_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["message"] == "kept"

    def test_warn_alias_treated_same_as_warning(self, log_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JARVIS_LOG_LEVEL", "WARN")
        svc = LogService()

        svc.log("INFO", "dropped")
        svc.log("WARNING", "kept")

        data = json.loads(log_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["message"] == "kept"

    def test_unknown_level_defaults_to_info_threshold(self, log_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Un ``JARVIS_LOG_LEVEL`` inconnu retombe sur le niveau INFO (valeur par défaut du .get)."""
        monkeypatch.setenv("JARVIS_LOG_LEVEL", "NOT_A_LEVEL")
        svc = LogService()

        svc.log("DEBUG", "dropped")
        svc.log("INFO", "kept")

        data = json.loads(log_path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["message"] == "kept"

    def test_message_level_stored_uppercased(self, service: LogService, log_path: Path) -> None:
        service.log("INFO", "kept")

        data = json.loads(log_path.read_text(encoding="utf-8"))
        assert data[0]["level"] == "INFO"


class TestLogEntryShape:
    def test_entry_has_ts_level_message_keys(self, service: LogService, log_path: Path) -> None:
        service.log("ERROR", "boom")

        data = json.loads(log_path.read_text(encoding="utf-8"))
        entry = data[0]
        assert set(entry.keys()) == {"ts", "level", "message"}
        assert entry["message"] == "boom"
        assert entry["level"] == "ERROR"
        assert isinstance(entry["ts"], str)
