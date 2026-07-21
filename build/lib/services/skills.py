"""Service Skills — Chargement et filtrage des skills activés."""
import json

from config.paths import SKILLS_CONFIG


def load_skills() -> dict:
    try:
        with open(SKILLS_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"version": "1.0", "skills": []}


def get_enabled_skills_text() -> str:
    """Retourne le texte concaténé des skills activés pour injection dans le contexte LLM."""
    data = load_skills()
    enabled = [s for s in data.get("skills", []) if s.get("enabled")]
    if not enabled:
        return ""
    sections = "\n\n".join(s["prompt"] for s in enabled)
    return f"[Skills actifs]\n{sections}"
