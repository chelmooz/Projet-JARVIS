"""Rules — Sévérité, recommandations, verdict.
Registre unique des ports. Tables de règles au lieu de cascades if/elif/else."""
from enum import IntEnum

from services.system import VENV_DIR


class Severity(IntEnum):
    OK = 0
    WARN = 1
    FAIL = 2
    INFO = 3


# Registre unique des ports sondés (check_network + generate_recommendations)
PORTS: dict[int, str] = {
    11434: "Ollama (systeme)",
    11436: "Ollama (local)",
    8000: "API JARVIS",
    3000: "OpenWebUI",
}


_PORT_SHORT_NAMES = {
    11436: "Ollama",
    8000: "API",
    3000: "OpenWebUI",
}


def _port_short_name(port: int) -> str:
    return _PORT_SHORT_NAMES.get(port, str(port))


def _tag(severity: Severity, msg: str) -> str:
    prefix = {Severity.OK: "[OK]  ", Severity.WARN: "[WARN]", Severity.FAIL: "[FAIL]", Severity.INFO: "[INFO] "}
    return f"{prefix[severity]} {msg}"


def _first(rules, r):
    """Première règle qui match gagne (remplace if/elif/else)."""
    for cond, sev, msg in rules:
        if cond(r):
            return _tag(sev, msg(r))


def _pick(cond, a, b):
    """Renvoie a si cond est vrai, sinon b (ternaire sans if)."""
    return a if cond else b


def _plural(n):
    return "s" if n > 1 else ""


# Tables de décision : (condition, severity, message_generator)
_THRESHOLD_RULES = [
    (lambda r: r["ram"]["total_gb"] < 8, Severity.FAIL, lambda r: f"RAM : {r['ram']['total_gb']} GiB insuffisant (minimum 8 GiB)"),
    (lambda r: r["ram"]["total_gb"] < 16, Severity.WARN, lambda r: f"RAM : {r['ram']['total_gb']} GiB -> modeles lourds limites"),
    (lambda r: True, Severity.OK, lambda r: f"RAM : {r['ram']['total_gb']} GiB suffisant"),
]

_BOOL_RULES = [
    (lambda r: r["gpu"]["detected"], Severity.OK, lambda r: f"GPU : {r['gpu']['detail']}"),
    (lambda r: not r["gpu"]["detected"], Severity.WARN, lambda r: "GPU : aucun -> inference CPU-only"),
    (lambda r: not r["python"]["missing_deps"], Severity.OK, lambda r: "Dependances Python : complete"),
    (lambda r: r["python"]["missing_deps"], Severity.FAIL, lambda r: f"Dependances manquantes : {', '.join(r['python']['missing_deps'])} -> lancer : pip install -r requirements.txt"),
    (lambda r: r["python"].get("python_env_ok", r["python"]["venv_ok"]), Severity.OK, lambda r: "Python portable/venv : present"),
    (lambda r: not r["python"].get("python_env_ok", r["python"]["venv_ok"]), Severity.WARN, lambda r: f"Python portable/venv non trouve -> lancer : python3 -m venv {VENV_DIR}"),
    (lambda r: r["network"]["internet"], Severity.OK, lambda r: "Internet : accessible"),
    (lambda r: not r["network"]["internet"], Severity.WARN, lambda r: "Internet : non accessible (installation offline)"),
    (lambda r: r["disk"]["free_gb"] >= 5, Severity.OK, lambda r: f"Disque : {r['disk']['free_gb']} GiB libre"),
    (lambda r: r["disk"]["free_gb"] < 5, Severity.FAIL, lambda r: f"Disque : {r['disk']['free_gb']} GiB libre -> insuffisant"),
]


def generate_recommendations(results: dict) -> list[str]:
    recs = []
    r = results

    recs.append(_first(_THRESHOLD_RULES, r))

    for cond, sev, msg in _BOOL_RULES:
        if cond(r):
            recs.append(_tag(sev, msg(r)))

    for b in r["binaries"]:
        tag = _pick(b["exists"],
                    _tag(Severity.OK, f"{b['name'].ljust(7)}: {b['path']}"),
                    _tag(Severity.FAIL, f"{b['name']} : binaire introuvable -> lancer : python3 scripts/install.py"))
        recs.append(tag)

    for port_num in [p for p in PORTS if p != 11434]:
        port_name = _port_short_name(port_num)
        in_use = r["network"]["ports"].get(str(port_num)) == "in_use"
        tag = _pick(in_use,
                    _tag(Severity.OK, f"Port {port_num} ({port_name}) : occupe (deja lance ?)"),
                    _tag(Severity.INFO, f"Port {port_num} ({port_name}) : libre"))
        recs.append(tag)

    return [r for r in recs if r]


def compute_verdict(recommendations: list[str]) -> str:
    fails = sum(1 for r in recommendations if r.startswith("[FAIL]"))
    warns = sum(1 for r in recommendations if r.startswith("[WARN]"))
    if fails:
        return f"FAIL ({fails} critique{_plural(fails)})"
    if warns:
        return f"WARNING ({warns} avertissement{_plural(warns)})"
    return "OK"
