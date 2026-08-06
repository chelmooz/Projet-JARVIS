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


def _parse_requirements_with_specifiers(path):
    """Retourne {nom: specifier_complete} depuis requirements.txt.
    
    Garde les spécificateurs complets (>=, <=, etc.) pour comparaison de bornes.
    Exemple: "fastapi>=0.100.0" -> {"fastapi": ">=0.100.0"}
    """
    specs = {}
    if not os.path.exists(path):
        return specs
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Supprime la partie commentaire après #
            if "#" in line:
                line = line.split("#")[0].strip()
            if not line:
                continue
            # Sépare le nom du paquet du spécificateur
            # Gère les extras: package[extra]>=version
            spec = line.split(";")[0].strip()  # Supprime les marqueurs d'environnement
            # Trouve le premier séparateur de version
            version_ops = [">=", "<=", "==", "!=", "~=", ">", "<"]
            package_name = None
            version_spec = None
            
            # Cherche l'opérateur de version
            for op in version_ops:
                if op in spec:
                    parts = spec.split(op, 1)
                    package_name = parts[0].rstrip()
                    version_spec = op + parts[1].lstrip()
                    break
            
            if package_name is None:
                # Pas de spécificateur de version, juste le nom du paquet
                package_name = spec
                version_spec = ""  # Pas de contrainte de version
            
            # Supprime les extras [standard] du nom pour la comparaison
            package_name = package_name.split("[")[0].strip().lower()
            
            specs[package_name] = version_spec
    return specs


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

    def test_requirements_specifiers_match_pyproject(self):
        """Vérifie que les spécificateurs de requirements.txt sont compatibles
        avec ceux de pyproject.toml.
        
        Pour chaque paquet commun, la version spécifiée dans requirements.txt
        doit satisfaire les contraintes de pyproject.toml.
        Exemple: si requirements.txt dit "fastapi>=0.100.0" et pyproject.toml 
        dit "fastapi>=0.135.1,<0.136", alors la borne requirements.txt doit 
        être comprise dans les bornes pyproject.toml.
        """
        req_specs = _parse_requirements_with_specifiers(ROOT_REQUIREMENTS)
        pyproject_specs = _parse_pyproject_specifiers(PYPROJECT_PATH)
        
        if not req_specs or not pyproject_specs:
            pytest.skip("requirements.txt ou pyproject.toml vide — rien à comparer.")
        
        mismatches = []
        for package_name, req_spec in req_specs.items():
            if package_name not in pyproject_specs:
                continue
                
            pyproject_spec = pyproject_specs[package_name]
            
            # Si requirements.txt n'a pas de spécificateur de version, c'est OK
            if not req_spec:
                continue
                
            # Vérifie que le spécificateur requirements.txt satisfait pyproject.toml
            # Pour cela, on transforme le spec requirements.txt en une contrainte
            # qu'on teste contre des versions hypothétiques dans la plage pyproject
            if not self._specifier_satisfies_specifier(req_spec, pyproject_spec):
                mismatches.append((package_name, req_spec, pyproject_spec))
        
        assert not mismatches, (
            "Incompatibilité de spécificateurs entre requirements.txt et pyproject.toml : "
            + "; ".join(f"{n}: requirements '{r}' non compatible avec pyproject '{p}'" 
                       for n, r, p in mismatches)
        )

    def _specifier_satisfies_specifier(self, req_spec, pyproject_spec):
        """Vérifie si un spécificateur requirements.txt est compatible avec 
        un spécificateur pyproject.toml.
        
        Pour ce test, on considère qu'ils sont compatibles s'ils sont identiques,
        ce qui est suffisant pour vérifier l'alignement des fichiers.
        """
        return req_spec == pyproject_spec

