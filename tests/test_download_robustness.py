"""TDD — Robustesse téléchargement (R1, audit post-correction)."""
import urllib.error

from services import ollama_installer


class _FakeResp:
    """Réponse factice : renvoie `data` puis se termine, ou lève sur demande."""

    def __init__(self, data: bytes = b"", raise_on_read: int = -1):
        self._data = data
        self._pos = 0
        self._raise_on_read = raise_on_read  # lève à la Nième lecture (0-based)
        self._reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        if self._raise_on_read >= 0 and self._reads >= self._raise_on_read:
            raise urllib.error.URLError("interrupted")
        self._reads += 1
        if self._pos >= len(self._data):
            return b""
        chunk = self._data[self._pos:self._pos + (n if n and n > 0 else len(self._data))]
        self._pos += len(chunk)
        return chunk


def _fake_urlopen(content: bytes, raise_on_read: int = -1):
    def _fake(url, timeout=None):
        return _FakeResp(content, raise_on_read=raise_on_read)
    return _fake


def test_download_success_writes_dest_and_cleans_part(monkeypatch, tmp_path):
    dest = str(tmp_path / "out.bin")
    monkeypatch.setattr(ollama_installer.urllib.request, "urlopen", _fake_urlopen(b"binary-content"))
    ollama_installer._download_file("http://x/out.bin", dest, lambda *a, **k: None)
    assert (tmp_path / "out.bin").read_bytes() == b"binary-content"
    assert not (tmp_path / "out.bin.part").exists()


def test_download_removes_partial_on_interruption(monkeypatch, tmp_path):
    dest = str(tmp_path / "out.bin")
    # Écrit 6 octets (1re lecture) puis lève (2e lecture) -> fichier partiel
    monkeypatch.setattr(ollama_installer.urllib.request, "urlopen", _fake_urlopen(b"PARTIAL", raise_on_read=1))
    try:
        ollama_installer._download_file("http://x/out.bin", dest, lambda *a, **k: None)
        assert False, "devait lever"
    except urllib.error.URLError:
        pass
    assert not (tmp_path / "out.bin.part").exists()
    assert not (tmp_path / "out.bin").exists()
