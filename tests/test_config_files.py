"""Tests Fix #4 — Vérifie la présence des fichiers de configuration requis."""
import os


class TestConfigFiles:

    def test_env_example_exists_at_root(self):
        """Le .env.example canonique est a la racine ; le doublon config/ est supprime."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        root_env = os.path.join(project_root, ".env.example")
        assert os.path.exists(root_env), (
            f".env.example introuvable a la racine {project_root}. "
            "Créez-le avec les variables JARVIS_PORT, JARVIS_LOG_LEVEL, JARVIS_DEV, OLLAMA_HOST."
        )
        dup = os.path.join(project_root, "config", ".env.example")
        assert not os.path.exists(dup), (
            "config/.env.example est un doublon mort ; la source est la racine."
        )

    def test_gitignore_has_coverage(self):
        """.gitignore doit couvrir .coverage et .pytest-temp/ (basetemp de pytest)."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        gitignore = os.path.join(project_root, ".gitignore")
        assert os.path.exists(gitignore)
        with open(gitignore, encoding="utf-8") as f:
            content = f.read()
        assert ".coverage" in content, ".gitignore doit contenir .coverage"
        assert ".pytest-temp" in content, ".gitignore doit contenir .pytest-temp"
