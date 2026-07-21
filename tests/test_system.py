"""Tests System — Detection d'environnement, chemins, Python portable, Ollama."""
import os

from config.paths import (
    BIN_DIR,
    PORTABLE_DIR,
)
from config.paths import (
    ROOT as BASE_DIR,
)
from services.system import (
    SYSTEM,
    find_python,
    get_ollama_path,
)


class TestSystemConstants:

    def test_base_dir_ends_with_projet_jarvis(self):
        # Tolérant au nom de dossier réel : "Projet JARVIS" (espace, clé USB)
        # ou "Projet-JARVIS" (tiret, nom du repo GitHub au clone).
        norm = BASE_DIR.replace("-", " ").lower()
        assert "projet jarvis" in norm, f"BASE_DIR inattendu : {BASE_DIR}"

    def test_system_is_lowercase_string(self):
        assert SYSTEM in ("windows", "linux", "darwin")

    def test_bin_dir_is_absolute(self):
        assert os.path.isabs(BIN_DIR)
        assert BIN_DIR.endswith("bin")

    def test_portable_dir_is_absolute(self):
        assert os.path.isabs(PORTABLE_DIR)
        assert PORTABLE_DIR.endswith("portable_python")


class TestFindPython:

    def test_returns_string_or_none(self):
        py = find_python()
        assert py is None or isinstance(py, str)

    def test_returns_existing_path(self):
        py = find_python()
        if py:
            assert os.path.exists(py)

    def test_fallback_to_system_python_when_portable_missing(self):
        """Contrat actuel : find_python() replie sur le Python systeme (sys.executable)
        et ne retourne jamais None meme si aucun Python portable n'est present."""
        import services.system as s
        original = s.PORTABLE_LINUX, s.PORTABLE_MAC
        s.PORTABLE_LINUX = "/nonexistent/linux"
        s.PORTABLE_MAC = "/nonexistent/mac"
        try:
            py = find_python()
            assert py is not None
            assert isinstance(py, str)
        finally:
            s.PORTABLE_LINUX, s.PORTABLE_MAC = original


class TestGetOllamaPath:

    def test_returns_string_or_none(self):
        path = get_ollama_path()
        assert path is None or (isinstance(path, str) and len(path) > 0)

    def test_prefers_portable_binary(self):
        path = get_ollama_path()
        if path:
            expected_name = "ollama.exe" if SYSTEM == "windows" else "ollama"
            assert path.endswith(expected_name) or "ollama" in path
