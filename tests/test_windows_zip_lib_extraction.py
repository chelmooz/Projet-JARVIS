"""TDD — _install_windows_zip doit préserver lib/ollama/ (llama-server.exe), pas seulement ollama.exe.

Bug réel constaté sur déploiement Windows réel (H:\\Projet-JARVIS) : le serveur Ollama
démarrait mais échouait à trouver llama-server.exe ("failure during llama-server GPU
discovery"), car _install_windows_zip ne copiait que ollama.exe depuis l'archive
extraite, puis supprimait le dossier temporaire d'extraction dans le `finally`
(perte définitive de lib/ollama/*).
"""
import os
import zipfile

import pytest

from services import ollama_installer


def _make_fake_ollama_zip(path: str) -> None:
    """Construit un zip imitant la structure réelle ollama-windows-amd64.zip."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("ollama.exe", b"fake-ollama-exe-bytes")
        zf.writestr("lib/ollama/llama-server.exe", b"fake-llama-server-bytes")
        zf.writestr("lib/ollama/ggml-cpu.dll", b"fake-dll-bytes")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch, tmp_path):
    """Remplace le téléchargement réel par la copie d'un zip factice local."""
    fake_zip_src = str(tmp_path / "src.zip")
    _make_fake_ollama_zip(fake_zip_src)

    def _fake_download_file(url, dest, log, timeout=None):
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        with open(fake_zip_src, "rb") as f_in, open(dest, "wb") as f_out:
            f_out.write(f_in.read())

    monkeypatch.setattr(ollama_installer, "_download_file", _fake_download_file)
    monkeypatch.setattr(ollama_installer, "_verify_ollama_binary", lambda *a, **k: True)


def test_install_windows_zip_preserves_llama_server(monkeypatch, tmp_path):
    fake_bin_dir = str(tmp_path / "bin")
    fake_base_dir = str(tmp_path)
    monkeypatch.setattr(ollama_installer, "BIN_DIR", fake_bin_dir)
    monkeypatch.setattr(ollama_installer, "BASE_DIR", fake_base_dir)

    result = ollama_installer._install_windows_zip(lambda *a: None)

    assert result == os.path.join(fake_bin_dir, "ollama.exe")
    assert os.path.exists(result), "ollama.exe doit être copié"

    candidates = [
        os.path.join(fake_bin_dir, "lib", "ollama", "llama-server.exe"),
        os.path.join(fake_base_dir, "lib", "ollama", "llama-server.exe"),
    ]
    assert any(os.path.exists(c) for c in candidates), (
        "llama-server.exe doit survivre à l'installation, dans bin\\lib\\ollama\\ "
        f"ou lib\\ollama\\ (candidats testés : {candidates})"
    )
