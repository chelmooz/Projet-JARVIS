"""TDD — Intégrité SHA256 du binaire Ollama (M24a)."""
import hashlib

from services import ollama_installer


def _make_tmp_file(tmp_path, content: bytes) -> str:
    p = tmp_path / "ollama.bin"
    p.write_bytes(content)
    return str(p)


def test_sha256_of_matches_hashlib(tmp_path):
    data = b"fake-ollama-binary-content"
    p = _make_tmp_file(tmp_path, data)
    expected = hashlib.sha256(data).hexdigest()
    assert ollama_installer._sha256_of(p) == expected


def test_verify_accepts_matching_hash(tmp_path, monkeypatch):
    data = b"payload"
    p = _make_tmp_file(tmp_path, data)
    # On force la source de hash a retourner le hash correct
    monkeypatch.setattr(
        ollama_installer,
        "_expected_ollama_sha256",
        lambda asset, log: hashlib.sha256(data).hexdigest(),
    )
    assert ollama_installer._verify_ollama_binary(p, "asset", lambda *a, **k: None) is True


def test_verify_rejects_mismatching_hash(tmp_path, monkeypatch):
    data = b"payload"
    p = _make_tmp_file(tmp_path, data)
    monkeypatch.setattr(
        ollama_installer, "_expected_ollama_sha256", lambda asset, log: "0" * 64
    )
    assert ollama_installer._verify_ollama_binary(p, "asset", lambda *a, **k: None) is False


def test_verify_falls_back_when_hash_unavailable(tmp_path, monkeypatch):
    data = b"payload"
    p = _make_tmp_file(tmp_path, data)
    # Source de hash indisponible -> on ne bloque pas (offline)
    monkeypatch.setattr(ollama_installer, "_expected_ollama_sha256", lambda asset, log: None)
    assert ollama_installer._verify_ollama_binary(p, "asset", lambda *a, **k: None) is True


def test_sha256_source_url_uses_real_ollama_filename():
    """Bug réel (08/08/2026) : le code visait sha256sums.txt (404 sur les
    releases GitHub Ollama) au lieu de sha256sum.txt (singulier, le vrai
    nom) -> la vérification SHA256 était sautée à 100% des installations."""
    import inspect

    src = inspect.getsource(ollama_installer._expected_ollama_sha256)
    assert "sha256sum.txt" in src
    assert "sha256sums.txt" not in src


def test_sha256_parsing_strips_dot_slash_prefix(monkeypatch):
    """Le fichier sha256sum.txt liste les assets avec un préfixe './'
    (ex: './ollama-windows-amd64.zip'), pas le nom nu. Sans le strip, le
    hash n'était jamais matché même une fois la bonne URL utilisée."""
    fake_content = (
        "9606cee7501703a0969682667def313130f99ed73f44a88a7a8efe82d4b565f0  "
        "./ollama-windows-amd64.zip\n"
    )

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return fake_content.encode()

    monkeypatch.setattr(
        ollama_installer.urllib.request, "urlopen", lambda *a, **k: _FakeResponse()
    )
    result = ollama_installer._expected_ollama_sha256(
        "ollama-windows-amd64.zip", lambda *a, **k: None
    )
    assert result == "9606cee7501703a0969682667def313130f99ed73f44a88a7a8efe82d4b565f0"
