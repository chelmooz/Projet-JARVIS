"""Tests FileSystemService — Auth, list_dir, read_file, find_files.

Chaque cycle TDD : RED → GREEN → REFACTOR.
"""
import os
import shutil
import tempfile

from services.file_system import FileSystemService


class TestFileSystemAuth:
    """Cycle 1 — Auth : authorize, revoke, is_authorized."""

    def setup_method(self):
        self.svc = FileSystemService()
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # --- 1.1 RED : refuse chemin non authorise ---

    def test_refuse_chemin_non_authorise(self):
        assert not self.svc.is_authorized(self.tmpdir)

    def test_list_dir_refuse_sans_auth(self):
        result = self.svc.list_dir(self.tmpdir)
        assert not result.get("success")
        assert "non authorise" in result.get("error", "").lower()

    def test_read_file_refuse_sans_auth(self):
        result = self.svc.read_file(__file__)
        assert not result.get("success")
        assert "non authorise" in result.get("error", "").lower()

    # --- 1.2 GREEN tests after implementation ---

    def test_authorize_path(self):
        ok = self.svc.authorize_path(self.tmpdir)
        assert ok
        assert self.svc.is_authorized(self.tmpdir)

    def test_authorize_path_doublon(self):
        self.svc.authorize_path(self.tmpdir)
        ok = self.svc.authorize_path(self.tmpdir)
        assert ok  # idempotent

    def test_revoke_path(self):
        self.svc.authorize_path(self.tmpdir)
        ok = self.svc.revoke_path(self.tmpdir)
        assert ok
        assert not self.svc.is_authorized(self.tmpdir)

    def test_revoke_path_inexistant(self):
        ok = self.svc.revoke_path(self.tmpdir)
        assert not ok

    def test_list_authorized(self):
        self.svc.authorize_path(self.tmpdir)
        paths = self.svc.list_authorized()
        assert self.tmpdir in paths

    def test_authorize_resout_chemin_relatif(self):
        ok = self.svc.authorize_path(".")
        assert ok
        abs_path = os.path.abspath(".")
        assert self.svc.is_authorized(abs_path)
        assert abs_path in self.svc.list_authorized()


class TestFileSystemListDir:
    """Cycle 2 — list_dir."""

    def setup_method(self):
        self.svc = FileSystemService()
        self.tmpdir = tempfile.mkdtemp()
        self.svc.authorize_path(self.tmpdir)
        # Create test files
        for name in ("alpha.txt", "beta.log", "gamma/"):
            p = os.path.join(self.tmpdir, name)
            if name.endswith("/"):
                os.makedirs(p.rstrip("/"), exist_ok=True)
            else:
                open(p, "w").close()
        self.tmpfile = __file__

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_dir_ok(self):
        result = self.svc.list_dir(self.tmpdir)
        assert result["success"]
        assert result["path"] == self.tmpdir
        names = [e["name"] for e in result["entries"]]
        assert "alpha.txt" in names
        assert "beta.log" in names
        assert "gamma" in names

    def test_list_dir_entries_have_types(self):
        result = self.svc.list_dir(self.tmpdir)
        entries = {e["name"]: e for e in result["entries"]}
        assert not entries["alpha.txt"]["is_dir"]
        assert entries["gamma"]["is_dir"]

    def test_list_dir_inexistant(self):
        result = self.svc.list_dir("Z:/n_existe_pas")
        assert not result["success"]

    def test_list_dir_non_authorise(self):
        svc2 = FileSystemService()
        result = svc2.list_dir(self.tmpdir)
        assert not result["success"]


class TestFileSystemReadFile:
    """Cycle 3 — read_file."""

    def setup_method(self):
        self.svc = FileSystemService()
        self.tmpdir = tempfile.mkdtemp()
        self.svc.authorize_path(self.tmpdir)
        self.test_file = os.path.join(self.tmpdir, "test.txt")
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write("Hello JARVIS!\nLine 2\n")

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_read_file_ok(self):
        result = self.svc.read_file(self.test_file)
        assert result["success"]
        assert "Hello JARVIS!" in result["content"]

    def test_read_file_inexistant(self):
        result = self.svc.read_file(os.path.join(self.tmpdir, "nope.txt"))
        assert not result["success"]

    def test_read_file_non_authorise(self):
        svc2 = FileSystemService()
        result = svc2.read_file(self.test_file)
        assert not result["success"]

    def test_read_file_limite_10ko(self):
        big = os.path.join(self.tmpdir, "big.txt")
        with open(big, "w", encoding="utf-8") as f:
            f.write("x" * 15000)
        result = self.svc.read_file(big)
        assert result["success"]
        assert len(result["content"]) <= 10000 + 50  # 10 Ko + message troncature

    def test_read_file_refuse_binaire(self):
        bin_file = os.path.join(self.tmpdir, "test.bin")
        with open(bin_file, "wb") as f:
            f.write(b"\x00\x01\x02\xFF\xFE")
        result = self.svc.read_file(bin_file)
        assert not result["success"]


class TestFileSystemFindFiles:
    """Cycle 4 — find_files."""

    def setup_method(self):
        self.svc = FileSystemService()
        self.tmpdir = tempfile.mkdtemp()
        self.svc.authorize_path(self.tmpdir)
        for name in ("a.txt", "sub/b.txt", "sub/sub2/c.log"):
            parts = name.split("/")
            path = os.path.join(self.tmpdir, *parts)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_find_files_par_pattern(self):
        result = self.svc.find_files(os.path.join(self.tmpdir, "**/*.txt"))
        assert result["success"]
        assert len(result["matches"]) >= 2

    def test_find_files_aucun_match(self):
        result = self.svc.find_files(os.path.join(self.tmpdir, "**/*.xyz"))
        assert result["success"]
        assert result["matches"] == []

    def test_find_files_non_authorise(self):
        svc2 = FileSystemService()
        result = svc2.find_files(os.path.join(self.tmpdir, "**/*.txt"))
        assert not result["success"]

    def test_find_files_borne_resultats(self):
        for i in range(50):
            p = os.path.join(self.tmpdir, f"d{i}", "f.txt")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").close()
        result = self.svc.find_files(os.path.join(self.tmpdir, "**/*.txt"), max_results=10)
        assert result["success"]
        assert len(result["matches"]) == 10
        assert result.get("truncated") is True


class TestFileSystemSecureByDefault:
    """Cycle 5 — Vérification du principe Secure by Default en production."""

    def test_secure_by_default_en_production(self, monkeypatch):
        import sys
        # On simule la production : pas de mode dev
        monkeypatch.setenv("JARVIS_DEV", "false")

        # On simule l'absence de pytest dans les modules pour tromper la détection
        modules_copy = dict(sys.modules)
        if "pytest" in modules_copy:
            del modules_copy["pytest"]
        monkeypatch.setattr(sys, "modules", modules_copy)

        svc = FileSystemService()
        tmpdir = tempfile.mkdtemp()
        try:
            # 1. Sans variable d'env, le sandbox par défaut doit restreindre au projet.
            # Donc autoriser un dossier temporaire externe (hors projet) doit être REFUSÉ.
            ok = svc.authorize_path(tmpdir)
            assert not ok

            # 2. Par contre, autoriser un chemin dans le projet (ex. PROJECT_DIR) doit être OK.
            from config.constants import PROJECT_DIR
            assert svc.authorize_path(PROJECT_DIR)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
