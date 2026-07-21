"""Tests Fix #1 — Vérifie que pyproject.toml déclare des dépendances runtime.

Bug repéré par l'audit : `dependencies = []` dans `[project]`, ce qui fait
que `pip install .` n'installe rien. Ce fichier garantit qu'on ne régresse
pas silencieusement vers une liste vide, et que les deux sources de vérité
possibles pour les dépendances (`config/requirements.txt` et le
`requirements-reference.txt` racine) ne divergent pas sans qu'on s'en
aperçoive.
"""
import os
import re

import pytest

try:
    import tomllib  # Python >= 3.11
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PYPROJECT_PATH = os.path.join(PROJECT_ROOT, "pyproject.toml")
ROOT_REQUIREMENTS = os.path.join(PROJECT_ROOT, "requirements.txt")

CORE_RUNTIME_PACKAGES = {"fastapi", "uvicorn", "httpx", "numpy", "psutil", "pyyaml"}


def _parse_requirements(path):
    if not os.path.exists(path):
        return set()
    names = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # normalise "package>=1.0" / "package[extra]>=1.0" -> "package"
            name = line.split(";")[0]
            for sep in ("==", ">=", "<=", "~=", ">", "<", "["):
                name = name.split(sep)[0]
            names.add(name.strip().lower())
    return names


def _parse_requirement_pins(path):
    """Retourne {nom: version} pour les lignes `package==x.y.z` (pins stricts)."""
    pins = {}
    if not os.path.exists(path):
        return pins
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "==" not in line:
                continue
            spec = line.split(";")[0].strip()
            name, _, ver = spec.partition("==")
            name = name.split("[")[0].strip().lower()
            pins[name] = ver.strip()
    return pins


def _parse_pyproject_specifiers(path):
    """Retourne {nom: specifier} depuis [project].dependencies de pyproject.toml.

    Le nom PEP 508 est isolé des opérateurs (>=, <=, ==, ...) et des extras
    ([standard]) pour que la comparaison de borne soit fiable."""
    specs = {}
    if not os.path.exists(path):
        return specs
    with open(path, "rb") as f:
        data = tomllib.load(f)
    for dep in data.get("project", {}).get("dependencies", []):
        spec = dep.split(";")[0].strip()
        m = re.match(r"\s*([A-Za-z0-9_.\-]+)", spec)
        if not m:
            continue
        raw_name = m.group(1)
        rest = spec[m.end():].strip()
        rest = re.sub(r"^\[[^\]]*\]", "", rest).strip()  # retire les extras [standard]
        specs[raw_name.lower()] = rest
    return specs


def _ver_tuple(vstr):
    """'1.2.3' -> (1, 2, 3) ; ignore les suffixes non numériques."""
    parts = []
    for p in vstr.split("."):
        num = ""
        for ch in p:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    return tuple(parts)


def _satisfies(pin, spec_str):
    """Vérifie (stdlib pur) qu'un pin `pin` satisfait un specifier PEP 440
    simplifié (clauses séparées par ',': >=, <=, >, <, ==, !=, ~=)."""
    pin_t = _ver_tuple(pin)
    for clause in spec_str.split(","):
        clause = clause.strip()
        if not clause:
            continue
        op = None
        for candidate in (">=", "<=", "==", "!=", "~=", ">", "<"):
            if clause.startswith(candidate):
                op = candidate
                break
        if op is None:
            continue
        ref_t = _ver_tuple(clause[len(op):])
        # pad to equal length
        n = max(len(pin_t), len(ref_t))
        pin_p = pin_t + (0,) * (n - len(pin_t))
        ref_p = ref_t + (0,) * (n - len(ref_t))
        if op == ">=" and not (pin_p >= ref_p):
            return False
        if op == "<=" and not (pin_p <= ref_p):
            return False
        if op == ">" and not (pin_p > ref_p):
            return False
        if op == "<" and not (pin_p < ref_p):
            return False
        if op == "==" and pin_p != ref_p:
            return False
        if op == "!=" and pin_p == ref_p:
            return False
        if op == "~=":
            # compatible release : >= ref ET même préfixe (hors dernier segment)
            if pin_p < ref_p:
                return False
            if pin_p[:-1] != ref_p[:-1]:
                return False
    return True


class TestPyprojectDependencies:

    @pytest.mark.skipif(tomllib is None, reason="tomllib indisponible (Python < 3.11)")
    def test_pyproject_exists(self):
        assert os.path.exists(PYPROJECT_PATH), f"pyproject.toml introuvable : {PYPROJECT_PATH}"

    @pytest.mark.skipif(tomllib is None, reason="tomllib indisponible (Python < 3.11)")
    def test_dependencies_not_empty(self):
        """Fix #1 — dependencies ne doit plus être une liste vide."""
        with open(PYPROJECT_PATH, "rb") as f:
            data = tomllib.load(f)

        deps = data.get("project", {}).get("dependencies", [])
        assert deps, (
            "pyproject.toml a `dependencies = []` — pip install . n'installera "
            "rien. Peupler avec les dépendances runtime (voir config/requirements.txt "
            "ou requirements-reference.txt à la racine)."
        )

    @pytest.mark.skipif(tomllib is None, reason="tomllib indisponible (Python < 3.11)")
    def test_core_runtime_packages_declared(self):
        """Les paquets runtime identifiés par l'audit doivent apparaître dans dependencies."""
        with open(PYPROJECT_PATH, "rb") as f:
            data = tomllib.load(f)

        deps = data.get("project", {}).get("dependencies", [])
        declared_names = set()
        for dep in deps:
            name = dep.split(";")[0]
            for sep in ("==", ">=", "<=", "~=", ">", "<", "["):
                name = name.split(sep)[0]
            declared_names.add(name.strip().lower())

        missing = CORE_RUNTIME_PACKAGES - declared_names
        assert not missing, (
            f"Paquets runtime manquants dans pyproject.toml [project.dependencies] : "
            f"{sorted(missing)}"
        )

    def test_pyproject_bounds_match_requirements_pins(self):
        """Tout pin `==` de config/requirements.txt doit rester DANS les bornes
        déclarées dans pyproject.toml. Empêche le drift qui avait cassé
        test_api_contract (requirements fastapi==0.136.3 vs pyproject
        fastapi>=0.136 non borné -> résolution 0.139 en install propre).

        Exemple de régression détectée : si pyproject passe à `fastapi>=0.137`,
        le pin `fastapi==0.136.3` n'est plus satisfiable -> ce test échoue."""
        pins = _parse_requirement_pins(ROOT_REQUIREMENTS)
        specs = _parse_pyproject_specifiers(PYPROJECT_PATH)
        if not pins or not specs:
            pytest.skip("requirements ou pyproject vide — rien à comparer.")

        mismatches = []
        for name, ver in pins.items():
            if name not in specs:
                continue
            if not _satisfies(ver, specs[name]):
                mismatches.append((name, ver, specs[name]))

        assert not mismatches, (
            "Drift de version entre config/requirements.txt (pin ==) et "
            "pyproject.toml (borne) : "
            + "; ".join(f"{n}=={v} hors borne pyproject '{s}'" for n, v, s in mismatches)
        )
