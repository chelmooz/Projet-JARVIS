"""Service Skills — Chargement et filtrage des skills activés."""

from __future__ import annotations

import json
from typing import Any

from config.paths import SKILLS_CONFIG


def load_skills() -> dict[str, Any]:
    """Charge la configuration des skills depuis le fichier JSON.

    Returns:
        Dictionnaire contenant la version et la liste des skills.
        Retourne une structure par défaut en cas d'erreur ou de fichier manquant.
    """
    try:
        with open(SKILLS_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
            # Sécurité : s'assurer que la racine du JSON est bien un dictionnaire
            return data if isinstance(data, dict) else {"version": "1.0", "skills": []}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"version": "1.0", "skills": []}


def get_enabled_skills_text() -> str:
    """Retourne le texte concaténé des skills activés pour injection dans le contexte LLM.

    Filtre les skills désactivés ou sans prompt pour éviter les blocs vides.
    """
    data = load_skills()
    enabled = [
        s for s in data.get("skills", [])
        if s.get("enabled") and s.get("prompt")
    ]
    if not enabled:
        return ""
    
    sections = "\n\n".join(s["prompt"] for s in enabled)
    return f"[Skills actifs]\n{sections}"


__all__ = ["load_skills", "get_enabled_skills_text"]
