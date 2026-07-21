"""TDD — jarvis doctor (M23a)."""
import os

from scripts import jarvis_doctor as doctor


def test_run_checks_returns_all_entries():
    results = doctor.run_checks()
    assert len(results) == len(doctor.CHECKS)
    for name, ok, detail in results:
        assert isinstance(name, str)
        assert isinstance(ok, bool)
        assert isinstance(detail, str)


def test_check_python_reports_version():
    ok, detail = doctor._check_python()
    assert "Python" in detail
    # Python 3.10+ est presque universel aujourd'hui ; on accepte le format
    assert detail.startswith("Python ")


def test_check_env_file_reflects_reality(tmp_path, monkeypatch):
    # Sans .env a la racine du projet, le check signale l'absence
    monkeypatch.setattr(doctor, "ROOT", str(tmp_path))
    ok, detail = doctor._check_env_file()
    assert ok is False
    assert ".env" in detail


def test_check_env_file_present(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor, "ROOT", str(tmp_path))
    open(os.path.join(str(tmp_path), ".env"), "w").close()
    ok, detail = doctor._check_env_file()
    assert ok is True


def test_check_port_reports_state():
    ok, detail = doctor._check_port()
    assert ok is True
    assert "Port" in detail
