"""Tests de sécurité de l'installateur Ollama portable."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from services import ollama_installer


def _logger(events: list[tuple[str, str, bool | None]]):
    def log(step: str, message: str, success: bool | None) -> None:
        events.append((step, message, success))

    return log


def test_verification_refuse_archive_when_manifest_sha256_indisponible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Un téléchargement sans empreinte attendue doit être refusé."""
    archive = tmp_path / "ollama.zip"
    archive.write_bytes(b"contenu quelconque")
    events: list[tuple[str, str, bool | None]] = []
    monkeypatch.setattr(ollama_installer, "_expected_ollama_sha256", lambda _asset, _log: None)

    assert not ollama_installer._verify_ollama_binary(str(archive), "ollama.zip", _logger(events))
    assert any("Installation refusée" in message for _, message, _ in events)


def test_verification_accepte_archive_avec_sha256_correspondant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Une empreinte SHA-256 correcte est acceptée."""
    archive = tmp_path / "ollama.zip"
    archive.write_bytes(b"archive saine")
    expected = ollama_installer._sha256_of(str(archive))
    events: list[tuple[str, str, bool | None]] = []
    monkeypatch.setattr(ollama_installer, "_expected_ollama_sha256", lambda _asset, _log: expected)

    assert ollama_installer._verify_ollama_binary(str(archive), "ollama.zip", _logger(events))
    assert any("Intégrité SHA256 vérifiée" in message for _, message, _ in events)


def test_extraction_zip_refuse_ecriture_hors_destination(tmp_path: Path) -> None:
    """Une entrée ../ ne doit jamais pouvoir écrire en dehors du répertoire temporaire."""
    archive = tmp_path / "malicious.zip"
    destination = tmp_path / "extract"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../outside.txt", "contenu non autorisé")

    with pytest.raises(ValueError, match="Entrée ZIP non sûre"):
        ollama_installer._safe_extract_zip(str(archive), str(destination))

    assert not (tmp_path / "outside.txt").exists()


def test_extraction_zip_accepte_une_archive_normale(tmp_path: Path) -> None:
    """Une archive au contenu local reste installable."""
    archive = tmp_path / "healthy.zip"
    destination = tmp_path / "extract"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("lib/ollama/readme.txt", "contenu sain")

    ollama_installer._safe_extract_zip(str(archive), str(destination))

    assert (destination / "lib" / "ollama" / "readme.txt").read_text() == "contenu sain"
