"""Tests Fix #4 — Vérifie qu'il n'y a plus de double définition de chemins
entre config/constants.py et config/paths.py.

L'audit a repéré que PROJECT_DIR, STATIC_DIR, CONFIG_DIR, MEMORY_DIR, LOGS_DIR
étaient définis indépendamment dans les deux fichiers, avec un risque de
divergence silencieuse si l'un est modifié sans l'autre. Ce test vérifie
directement les valeurs importées (source de vérité = ce que Python résout
à l'exécution), pas juste la présence textuelle, pour éviter les faux positifs
si une future refactorisation change la façon dont le fichier est écrit.
"""
import os

import pytest

DUPLICATED_NAMES = ["PROJECT_DIR", "STATIC_DIR", "CONFIG_DIR", "MEMORY_DIR", "LOGS_DIR"]


class TestPathsSingleSourceOfTruth:

    def _import_modules(self):
        try:
            from config import constants, paths
        except ImportError as exc:
            pytest.skip(f"Impossible d'importer config.constants / config.paths : {exc}")
        return constants, paths

    @pytest.mark.parametrize("name", DUPLICATED_NAMES)
    def test_path_constant_not_duplicated_with_diverging_value(self, name):
        """Si un nom de chemin existe dans les deux modules, la valeur doit être
        strictement identique (idéalement parce que constants.py le réexporte
        depuis paths.py plutôt que de le redéfinir)."""
        constants, paths = self._import_modules()

        value_in_constants = getattr(constants, name, None)
        value_in_paths = getattr(paths, name, None)

        if value_in_constants is None or value_in_paths is None:
            pytest.skip(f"{name} absent d'un des deux modules — pas de risque de divergence.")

        assert os.path.normpath(str(value_in_constants)) == os.path.normpath(str(value_in_paths)), (
            f"{name} diverge entre config.constants ({value_in_constants!r}) et "
            f"config.paths ({value_in_paths!r}). Source de vérité unique attendue : "
            f"config/paths.py, réexportée dans constants.py."
        )

    def test_constants_reexports_paths_not_redefines(self):
        """Vérifie (best-effort, scan texte) que constants.py importe ces noms
        depuis config.paths plutôt que de les redéfinir avec une valeur littérale
        (ex: Path(__file__).parent...)."""
        constants_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "Projet JARVIS", "config", "constants.py"
        )
        if not os.path.exists(constants_path):
            pytest.skip(f"config/constants.py introuvable à {constants_path}")

        with open(constants_path, encoding="utf-8") as f:
            content = f.read()

        for name in DUPLICATED_NAMES:
            if f"{name} =" in content and "from config.paths import" not in content and "from .paths import" not in content:
                pytest.fail(
                    f"{name} semble redéfini littéralement dans constants.py au lieu "
                    f"d'être importé depuis config.paths (Fix #4 non appliqué)."
                )
