"""Tests launcher — pas de fd leak si Popen leve (audit DevOps 4.4).

Le pattern etait `f_err = _open_log(...)` ; `Popen` ; `f_err.close()`. Si
`Popen` leve (binaire corrompu, permission refusee), `f_err.close()` etait
saute -> fd ouvert jusqu'au GC. Le `with` ferme le fichier dans tous les cas.
"""
import os
from unittest import mock

from services.launcher import ProcessManager


def _fake_open_log(tmp_path, opened):
    real_open = open

    def _open(name):
        path = os.path.join(tmp_path, name.lower().replace(" ", "_") + ".log")
        f = real_open(path, "a", encoding="utf-8")
        opened.append(f)
        return f

    return _open


def test_start_ollama_closes_log_on_popen_error(tmp_path, monkeypatch):
    pm = ProcessManager()
    opened = []
    monkeypatch.setattr("services.launcher._open_log", _fake_open_log(tmp_path, opened))
    monkeypatch.setattr("services.launcher.get_ollama_path", lambda: "fake_ollama")
    monkeypatch.setattr("services.launcher.kill_existing", lambda *a, **k: None)

    def boom(*a, **k):
        raise OSError("cannot spawn")

    monkeypatch.setattr("services.launcher.subprocess.Popen", boom)
    assert pm.start_ollama() is None
    assert opened, "log file should have been opened"
    assert opened[0].closed is True


def test_start_ollama_closes_log_on_success(tmp_path, monkeypatch):
    pm = ProcessManager()
    opened = []
    monkeypatch.setattr("services.launcher._open_log", _fake_open_log(tmp_path, opened))
    monkeypatch.setattr("services.launcher.get_ollama_path", lambda: "fake_ollama")
    monkeypatch.setattr("services.launcher.kill_existing", lambda *a, **k: None)
    fake_proc = mock.MagicMock()
    fake_proc.poll.return_value = None
    monkeypatch.setattr("services.launcher.subprocess.Popen", lambda *a, **k: fake_proc)
    assert pm.start_ollama() is fake_proc
    assert opened and opened[0].closed is True
