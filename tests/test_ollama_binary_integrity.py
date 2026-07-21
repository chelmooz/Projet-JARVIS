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


def test_verify_accepts_matching_hash(tmp_path):
    data = b"payload"
    p = _make_tmp_file(tmp_path, data)
    # On force la source de hash a retourner le hash correct
    ollama_installer._expected_ollama_sha256 = lambda asset, log: hashlib.sha256(data).hexdigest()
    try:
        assert ollama_installer._verify_ollama_binary(p, "asset", lambda *a, **k: None) is True
    finally:
        del ollama_installer._expected_ollama_sha256


def test_verify_rejects_mismatching_hash(tmp_path):
    data = b"payload"
    p = _make_tmp_file(tmp_path, data)
    ollama_installer._expected_ollama_sha256 = lambda asset, log: "0" * 64
    try:
        assert ollama_installer._verify_ollama_binary(p, "asset", lambda *a, **k: None) is False
    finally:
        del ollama_installer._expected_ollama_sha256


def test_verify_falls_back_when_hash_unavailable(tmp_path):
    data = b"payload"
    p = _make_tmp_file(tmp_path, data)
    # Source de hash indisponible -> on ne bloque pas (offline)
    ollama_installer._expected_ollama_sha256 = lambda asset, log: None
    try:
        assert ollama_installer._verify_ollama_binary(p, "asset", lambda *a, **k: None) is True
    finally:
        del ollama_installer._expected_ollama_sha256
