"""Classe de base abstraite pour tous les agents JARVIS.

Définit le contrat commun (méthode `run` abstraite) et les helpers de
construction de prompt à partir des profils (`config/agent_profiles.json`).
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from config.paths import PROFILES_FILE

_logger = logging.getLogger("jarvis.agents.base")


class BaseAgent(ABC):
    """Contrat commun à tous les agents (dev, network, hardware, cyber, vision)."""

    PROFILES_PATH = PROFILES_FILE
    _profile_cache: dict[str, dict] = {}
    _profile_mtime: float = 0.0

    def __init__(self) -> None:
        self.toolbox = None

    def inject_toolbox(self, toolbox: Any) -> None:
        """Branche la toolbox (diagnostics + fichiers) utilisée pour décrire les outils."""
        self.toolbox = toolbox

    @abstractmethod
    def run(self, task: str, model: str, context: dict[str, Any]) -> dict:
        """Exécute une tâche et retourne {'response', 'agent', 'model', ...}."""
        raise NotImplementedError

    def _load_profile(self, profile_key: str) -> dict:
        """Charge un profil depuis PROFILES_PATH (section `profiles`).

        Cache classe avec invalidation au mtime pour eviter I/O disque
        a chaque requete (sur cle USB lente, 5-15 ms par read).
        Retourne un dict vide si le fichier est absent ou corrompu.
        """
        try:
            current_mtime = os.path.getmtime(self.PROFILES_PATH)
        except OSError:
            return {}
        if current_mtime != self._profile_mtime:
            try:
                with open(self.PROFILES_PATH, encoding="utf-8") as f:
                    profiles = json.load(f).get("profiles", {})
            except (FileNotFoundError, json.JSONDecodeError):
                return {}
            self.__class__._profile_cache.clear()
            self.__class__._profile_cache.update(profiles)
            self.__class__._profile_mtime = current_mtime
        return self._profile_cache.get(profile_key, {})

    @staticmethod
    def _similar_cases_block(context: dict) -> str:
        """Retourne le texte des cas similaires récents (limité à 3), ou ''."""
        similar = context.get("similar_cases", [])
        if not similar:
            return ""
        items = "\n".join(f"  - {s['text'][:200]}" for s in similar[:3])
        return f"\nCas similaires récents :\n{items}"

    @staticmethod
    def _enabled_skills() -> str:
        """Texte des skills activés (toggle Skills), '' si aucun ou erreur I/O.

        Import paresseux pour éviter tout cycle avec services.skills ; jamais
        levé pour ne pas casser le prompt LLM si skills.json est illisible.
        """
        from services.skills import get_enabled_skills_text

        try:
            return get_enabled_skills_text()
        except Exception as e:  # noqa: BLE001 - dégradations silencieuses tolérées
            _logger.warning("Skills ignorés (toggle inactif): %s", e)
            return ""

    @staticmethod
    def _render_context_blocks(profile: dict, context: dict) -> tuple[str, str]:
        """Construit les blocs de texte réutilisables (outils + cas similaires).

        Retourne ``(tools_desc, similar_text)`` prêts à injecter dans un prompt.
        Évite la duplication entre `_profile_prompt` et `_build_messages`.
        """
        tools = profile.get("tools", {})
        tools_desc = (
            "\nOutils disponibles :\n" + "\n".join(
                f"  - {k}: {v}" for k, v in tools.items()
            )
            if tools
            else ""
        )
        return tools_desc, BaseAgent._similar_cases_block(context)

    def _profile_prompt(
        self,
        profile_key: str,
        task: str,
        context: dict[str, Any],
        default_prompt: str | None = None,
    ) -> str:
        """Assemble un prompt monolitaire (system + outils + contexte + tâche).

        `default_prompt` (optionnel) remplace le system prompt du profil chargé
        (utilisé par les agents spécialisés : domaine cyber, prompt métier…).
        """
        profile = self._load_profile(profile_key)
        system = default_prompt if default_prompt is not None else profile.get("system_prompt", "")
        skills_text = self._enabled_skills()
        if skills_text:
            system = f"{system}\n\n{skills_text}"
        tools_desc, similar_text = self._render_context_blocks(profile, context)
        history = context.get("recent_tasks", [])
        return f"{system}{tools_desc}\nContexte récent : {history}{similar_text}\nTâche : {task}"

    def _toolbox_block(self) -> str:
        """Retourne la description de la toolbox (diagnostics + fichiers), préfixée d'un saut de ligne.

        Helper extrait pour respecter la limite d'arguments/longueur (Clean Code §3.B).
        """
        if not self.toolbox:
            return ""
        toolbox_desc = self.toolbox.describe_tools()
        return f"\n{toolbox_desc}" if toolbox_desc else ""

    def _build_messages(
        self,
        profile_key: str,
        task: str,
        context: dict[str, Any],
        default_prompt: str | None = None,
    ) -> tuple[str, str]:
        """Retourne ``(system_prompt, user_prompt)`` séparés pour l'appel LLM.

        Ajoute la description de la toolbox (diagnostics + fichiers) si injectée.
        `default_prompt` (optionnel) remplace le system prompt du profil chargé.
        """
        profile = self._load_profile(profile_key)
        system = default_prompt if default_prompt is not None else profile.get("system_prompt", "")
        skills_text = self._enabled_skills()
        if skills_text:
            system = f"{system}\n\n{skills_text}"
        tools_desc, similar_text = self._render_context_blocks(profile, context)
        toolbox_desc = self._toolbox_block()
        history = context.get("recent_tasks", [])
        user = f"{tools_desc}{toolbox_desc}\nContexte récent : {history}{similar_text}\nTâche : {task}"
        return system.strip(), user.strip()

    @staticmethod
    def _detect_skill_from_code(result: str, prefix: str = "script") -> str | None:
        """Détecte l'extension de fichier à partir des blocs de code (```powershell/bash/python)."""
        if "```powershell" in result:
            return f"{prefix}.ps1"
        if "```bash" in result:
            return f"{prefix}.sh"
        if "```python" in result:
            return f"{prefix}.py"
        return None
