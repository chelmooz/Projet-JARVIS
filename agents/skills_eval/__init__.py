from pathlib import Path

_ROLES = frozenset({"judge", "advocate", "evaluator"})


def load_skill_eval(role: str) -> str:
    """Charge le prompt SKILL.md pour role ∈ {"judge", "advocate", "evaluator"}.
    Retourne le contenu du fichier. Lève ValueError si rôle inconnu.
    """
    if role not in _ROLES:
        raise ValueError(f"Rôle inconnu: {role!r}. Rôles disponibles: {sorted(_ROLES)}")
    return (Path(__file__).parent / f"{role}.md").read_text(encoding="utf-8")
