"""Tests de caractérisation pour services/ollama_installer.py.

Ces tests capturent le comportement ACTUEL du module. Ils doivent être VERTS
d'emblée (réseau et subprocess mockés, disque en tmp_path uniquement).
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.ollama_download import (
    _download_file,
    _expected_ollama_sha256,
    _sha256_of,
    _verify_ollama_binary,
)
from services.ollama_installer import (
    _extract_tar_zst,
    _is_real_ollama,
    _safe_extract_zip,
    ensure_ollama_binary,
)

# ---- _download_file ----


def test_download_file_writes_atomically(tmp_path: Path) -> None:
    """_download_file écrit en .part puis renomme (atomique)."""
    dest = tmp_path / "output.txt"
    log_calls = []

    def log(msg: str, detail: str, success: bool | None) -> None:
        log_calls.append((msg, detail, success))

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.side_effect = [b"hello", b" world", b""]
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        _download_file("http://example.com/file", str(dest), log)

    assert dest.read_bytes() == b"hello world"
    assert not (tmp_path / "output.txt.part").exists()


def test_download_file_on_error_no_partial_file(tmp_path: Path) -> None:
    """Si erreur, le fichier .part est nettoyé, pas de fichier final."""
    dest = tmp_path / "output.txt"
    log_calls = []

    def log(msg: str, detail: str, success: bool | None) -> None:
        log_calls.append((msg, detail, success))

    with patch("urllib.request.urlopen", side_effect=ConnectionError("network down")), pytest.raises(ConnectionError):
        _download_file("http://example.com/file", str(dest), log)

    assert not dest.exists()
    assert not (tmp_path / "output.txt.part").exists()


# ---- _sha256_of ----


def test_sha256_of_known_content(tmp_path: Path) -> None:
    """_sha256_of calcule le hash correct par blocs."""
    f = tmp_path / "data.bin"
    f.write_bytes(b"test content")
    expected = hashlib.sha256(b"test content").hexdigest()

    result = _sha256_of(str(f))

    assert result == expected


# ---- _expected_ollama_sha256 ----


def test_expected_ollama_sha256_parses_release_manifest(tmp_path: Path) -> None:
    """_expected_ollama_sha256 parse le manifeste sha256sum.txt."""
    manifest = "abc123  ./ollama-linux-amd64.tar.zst\ndef456  ./ollama-windows-amd64.zip\n"
    log_calls = []

    def log(msg: str, detail: str, success: bool | None) -> None:
        log_calls.append((msg, detail, success))

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = manifest.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = _expected_ollama_sha256("ollama-linux-amd64.tar.zst", log)

    assert result == "abc123"


def test_expected_ollama_sha256_missing_asset_returns_none(tmp_path: Path) -> None:
    """Asset absent du manifeste -> None (pas de log, c'est le comportement actuel)."""
    manifest = "abc123  ./ollama-linux-amd64.tar.zst\n"
    log_calls = []

    def log(msg: str, detail: str, success: bool | None) -> None:
        log_calls.append((msg, detail, success))

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = manifest.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = _expected_ollama_sha256("ollama-macos-arm64.tar.gz", log)

    assert result is None
    # Le comportement actuel ne log PAS quand l'asset est absent du manifeste
    # (seulement en cas d'exception réseau)
    assert len(log_calls) == 0


# ---- _verify_ollama_binary ----


def test_verify_ollama_binary_ok(tmp_path: Path) -> None:
    """Hash correct -> True + log succès."""
    f = tmp_path / "ollama"
    f.write_bytes(b"binary content")
    expected = hashlib.sha256(b"binary content").hexdigest()
    log_calls = []

    def log(msg: str, detail: str, success: bool | None) -> None:
        log_calls.append((msg, detail, success))

    with patch("services.ollama_download._expected_ollama_sha256", return_value=expected):
        result = _verify_ollama_binary(str(f), "ollama-linux-amd64.tar.zst", log)

    assert result is True
    assert any(c[2] is True for c in log_calls)


def test_verify_ollama_binary_mismatch_fails(tmp_path: Path) -> None:
    """Hash incorrect -> False + log erreur."""
    f = tmp_path / "ollama"
    f.write_bytes(b"wrong content")
    log_calls = []

    def log(msg: str, detail: str, success: bool | None) -> None:
        log_calls.append((msg, detail, success))

    with patch(
        "services.ollama_download._expected_ollama_sha256",
        return_value="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    ):
        result = _verify_ollama_binary(str(f), "ollama-linux-amd64.tar.zst", log)

    assert result is False
    assert any("MISMATCH" in c[1] for c in log_calls)


def test_verify_ollama_binary_missing_expected_refuses(tmp_path: Path) -> None:
    """Hash attendu indisponible -> False (sécurité)."""
    f = tmp_path / "ollama"
    f.write_bytes(b"content")
    log_calls = []

    def log(msg: str, detail: str, success: bool | None) -> None:
        log_calls.append((msg, detail, success))

    with patch("services.ollama_download._expected_ollama_sha256", return_value=None):
        result = _verify_ollama_binary(str(f), "ollama-linux-amd64.tar.zst", log)

    assert result is False
    assert any("refusée" in c[1] for c in log_calls)


# ---- _safe_extract_zip ----


def test_safe_extract_zip_normal(tmp_path: Path) -> None:
    """Archive ZIP normale -> extraction correcte."""
    zip_path = tmp_path / "test.zip"
    dest = tmp_path / "out"
    dest.mkdir()

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("file.txt", "content")
        zf.writestr("sub/file2.txt", "content2")

    _safe_extract_zip(str(zip_path), str(dest))

    assert (dest / "file.txt").read_text() == "content"
    assert (dest / "sub" / "file2.txt").read_text() == "content2"


def test_safe_extract_zip_path_traversal_rejected(tmp_path: Path) -> None:
    """Entrée ../ -> ValueError, aucune écriture."""
    zip_path = tmp_path / "evil.zip"
    dest = tmp_path / "out"
    dest.mkdir()

    with zipfile.ZipFile(zip_path, "w") as zf:
        zi = zipfile.ZipInfo("../escape.txt")
        zi.external_attr = 0
        zf.writestr(zi, "bad")

    with pytest.raises(ValueError, match="non sûre"):
        _safe_extract_zip(str(zip_path), str(dest))

    # Rien n'a été écrit
    assert not any(dest.iterdir())


def test_safe_extract_zip_symlink_rejected(tmp_path: Path) -> None:
    """Lien symbolique dans ZIP -> ValueError."""
    zip_path = tmp_path / "evil.zip"
    dest = tmp_path / "out"
    dest.mkdir()

    with zipfile.ZipFile(zip_path, "w") as zf:
        zi = zipfile.ZipInfo("link.txt")
        # external_attr avec bit symlink (stat.S_IFLNK << 16)
        import stat

        zi.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(zi, "target")

    with pytest.raises(ValueError, match="non sûre"):
        _safe_extract_zip(str(zip_path), str(dest))


# ---- _extract_tar_zst ----


def test_extract_tar_zst_calls_tar_zstd_then_fallback(tmp_path: Path) -> None:
    """Appelle tar --zstd, en cas d'échec fallback tar -xf."""
    archive = tmp_path / "data.tar.zst"
    archive.write_bytes(b"dummy")
    dest = tmp_path / "out"
    dest.mkdir()
    log_calls = []

    def log(msg: str, detail: str, success: bool | None) -> None:
        log_calls.append((msg, detail, success))

    call_order = []

    def mock_run(cmd, **kwargs):
        call_order.append(cmd[0])
        if cmd[0] == "tar" and "--zstd" in cmd:
            raise FileNotFoundError("zstd not found")
        # fallback
        return MagicMock()

    with patch("subprocess.run", side_effect=mock_run):
        _extract_tar_zst(str(archive), str(dest), log)

    assert call_order == ["tar", "tar"]
    assert any("fallback" in c[1] for c in log_calls)


# ---- _is_real_ollama ----


def test_is_real_ollama_valid_version_output() -> None:
    """Sortie --version contenant 'ollama' -> True."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="ollama version 0.1.0", stderr="")
        assert _is_real_ollama("/fake/path/ollama") is True


def test_is_real_ollama_invalid_output() -> None:
    """Sortie sans 'ollama' -> False."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="something else", stderr="")
        assert _is_real_ollama("/fake/path/ollama") is False


def test_is_real_ollama_exception_returns_false() -> None:
    """Exception subprocess -> False + log warning."""
    with patch("subprocess.run", side_effect=OSError("not found")):
        assert _is_real_ollama("/fake/path/ollama") is False


# ---- ensure_ollama_binary ----


def test_ensure_ollama_binary_existing_valid_returns_path(tmp_path: Path) -> None:
    """Binaire déjà présent et valide -> retourne le chemin sans installer."""
    existing = tmp_path / "ollama"
    existing.write_bytes(b"binary")
    log_calls = []

    def log(msg: str, detail: str, success: bool | None) -> None:
        log_calls.append((msg, detail, success))

    with (
        patch("services.ollama_installer.get_ollama_path", return_value=str(existing)),
        patch("services.ollama_installer._is_real_ollama", return_value=True),
    ):
        result = ensure_ollama_binary(log)

    assert result == str(existing)
    # Aucune installation tentée
    assert not any("installation" in c[1] for c in log_calls)


def test_ensure_ollama_binary_existing_invalid_returns_none(tmp_path: Path) -> None:
    """Binaire présent mais invalide -> None."""
    existing = tmp_path / "ollama"
    existing.write_bytes(b"fake")
    log_calls = []

    def log(msg: str, detail: str, success: bool | None) -> None:
        log_calls.append((msg, detail, success))

    with (
        patch("services.ollama_installer.get_ollama_path", return_value=str(existing)),
        patch("services.ollama_installer._is_real_ollama", return_value=False),
    ):
        result = ensure_ollama_binary(log)

    assert result is None
    assert any("suspect" in c[1] for c in log_calls)
