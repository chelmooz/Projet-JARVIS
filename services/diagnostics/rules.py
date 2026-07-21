"""Rules — Sévérité, recommandations, verdict.

Registre unique des ports. Tables de règles au lieu de cascades if/elif/else.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from services.system import VENV_DIR


class Severity(IntEnum):
    """Niveaux de sévérité pour les diagnostics."""

    OK = 0
    WARN = 1
    FAIL = 2
    INFO = 3


# Registre unique des ports sondés (check_network + generate_recommendations)
PORTS: dict[int, str] = {
    11434: "Ollama (système)",
    11436: "Ollama (local)",
    8000: "API JARVIS",
    3000: "OpenWebUI",
}

_PORT_SHORT_NAMES: dict[int, str] = {
    11436: "Ollama",
    8000: "API",
    3000: "OpenWebUI",
}


def _port_short_name(port: int) -> str:
    """Retourne le nom court d'un port, ou le numéro si inconnu."""
    return _PORT_SHORT_NAMES.get(port, str(port))


def _tag(severity: Severity, msg: str) -> str:
    """Formate un message avec un préfixe de sévérité."""
    prefix = {
        Severity.OK: "[OK]  ",
        Severity.WARN: "[WARN]",
        Severity.FAIL: "[FAIL]",
        Severity.INFO: "[INFO]",
    }
    return f"{prefix[severity]} {msg}"


def _first(rules: list, r: dict[str, Any]) -> str:
    """Retourne le message de la première règle dont la condition est vraie."""
    for cond, sev, msg in rules:
        if cond(r):
            return _tag(sev, msg(r))
    return ""


def _pick(cond: bool, a: str, b: str) -> str:
    """Renvoie `a` si `cond` est vrai, sinon `b`."""
    return a if cond else b


def _plural(n: int) -> str:
    """Retourne 's' si n > 1, sinon chaîne vide."""
    return "s" if n > 1 else ""


# Tables de décision : (condition, severity, message_generator)
_THRESHOLD_RULES = [
    (
        lambda r: r["ram"]["total_gb"] < 8,
        Severity.FAIL,
        lambda r: f"RAM : {r['ram']['total_gb']} GiB insuffisant (minimum 8 GiB)",
    ),
    (
        lambda r: r["ram"]["total_gb"] < 16,
        Severity.WARN,
        lambda r: f"RAM : {r['ram']['total_gb']} GiB -> modèles lourds limités",
    ),
    (
        lambda r: True,
        Severity.OK,
        lambda r: f"RAM : {r['ram']['total_gb']} GiB suffisant",
    ),
]

_BOOL_RULES = [
    (
        lambda r: r["gpu"]["detected"],
        Severity.OK,
        lambda r: f"GPU : {r['gpu']['detail']}",
    ),
    (
        lambda r: not r["gpu"]["detected"],
        Severity.WARN,
        lambda r: "GPU : aucun -> inférence CPU-only",
    ),
    (
        lambda r: not r["python"]["missing_deps"],
        Severity.OK,
        lambda r: "Dépendances Python : complètes",
    ),
    (
        lambda r: bool(r["python"]["missing_deps"]),
        Severity.FAIL,
        lambda r: f"Dépendances manquantes : {', '.join(r['python']['missing_deps'])} -> lancer : pip install -r requirements.txt",
    ),
    (
        lambda r: r["python"].get("python_env_ok", r["python"]["venv_ok"]),
        Severity.OK,
        lambda r: "Python portable/venv : présent",
    ),
    (
        lambda r: not r["python"].get("python_env_ok", r["python"]["venv_ok"]),
        Severity.WARN,
        lambda r: f"Python portable/venv non trouvé -> lancer : python3 -m venv {VENV_DIR}",
    ),
    (
        lambda r: r["network"]["internet"],
        Severity.OK,
        lambda r: "Internet : accessible",
    ),
    (
        lambda r: not r["network"]["internet"],
        Severity.WARN,
        lambda r: "Internet : non accessible (installation offline)",
    ),
    (
        lambda r: r["disk"]["free_gb"] >= 5,
        Severity.OK,
        lambda r: f"Disque : {r['disk']['free_gb']} GiB libre",
    ),
    (
        lambda r: r["disk"]["free_gb"] < 5,
        Severity.FAIL,
        lambda r: f"Disque : {r['disk']['free_gb']} GiB libre -> insuffisant",
    ),
]


def generate_recommendations(results: dict[str, Any]) -> list[str]:
    """Génère une liste de recommandations formatées à partir des résultats de diagnostic."""
    recs: list[str] = []
    r = results

    first_rec = _first(_THRESHOLD_RULES, r)
    if first_rec:
        recs.append(first_rec)

    for cond, sev, msg in _BOOL_RULES:
        if cond(r):
            recs.append(_tag(sev, msg(r)))

    for b in r.get("binaries", []):
        tag = _pick(
            b.get("exists", False),
            _tag(Severity.OK, f"{b['name'].ljust(7)}: {b['path']}"),
            _tag(Severity.FAIL, f"{b['name']} : binaire introuvable -> lancer : python3 scripts/install.py"),
        )
        recs.append(tag)

    for port_num in (p for p in PORTS if p != 11434):
        port_name = _port_short_name(port_num)
        in_use = r.get("network", {}).get("ports", {}).get(str(port_num)) == "in_use"
        tag = _pick(
            in_use,
            _tag(Severity.OK, f"Port {port_num} ({port_name}) : occupé (déjà lancé ?)"),
            _tag(Severity.INFO, f"Port {port_num} ({port_name}) : libre"),
        )
        recs.append(tag)

    return [r for r in recs if r]


def compute_verdict(recommendations: list[str]) -> str:
    """Calcule le verdict global en comptant les FAIL et WARN."""
    fails = sum(1 for r in recommendations if r.startswith("[FAIL]"))
    warns = sum(1 for r in recommendations if r.startswith("[WARN]"))
    
    if fails:
        return f"FAIL ({fails} critique{_plural(fails)})"
    if warns:
        return f"WARNING ({warns} avertissement{_plural(warns)})"
    return "OK"


__all__ = ["Severity", "PORTS", "generate_recommendations", "compute_verdict"]
