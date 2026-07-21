"""Classe de base abstraite de tous les agents JARVIS.

Définit le contrat commun (``run``) et les helpers de construction de
prompt à partir des profils (``config/agent_profiles.json``).

Responsabilités (SRP)
---------------------
- Contrat d'exécution d'un agent (``run``).
- Composition du prompt (profil + skills + outils + contexte).
- Lecture *cachée* des profils, avec invalidation par mtime et protection
  par verrou (le serveur FastAPI est multi-thread via le threadpool).

Le cache de profils reste un attribut de **classe** volontairement :
``PROFILES_PATH`` est un *hook* de substitution (tests, sous-classes) et
doit rester override-able. Le verrou garantit l'atomicité du refresh.

NOTE: Le contexte (`context: dict[str, Any]`) est non typé. Cible :
TypedDict `AgentContext` dans models/ pour typer le contrat d'entrée.
"""

from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol, TypedDict

from config.paths import PROFILES_FILE

_logger = logging.getLogger("jarvis.agents.base")


# ---------------------------------------------------------------------------
# Contrat de retour de ``run`` (dict typé — compat runtime avec les
# consommateurs graph/controllers qui lisent par clé ``result["response"]``).
# ---------------------------------------------------------------------------

class AgentRunResult(TypedDict, total=False):
    """Forme du dict retourné par :meth:`BaseAgent.run`.

    ``response``, ``agent`` et ``model`` sont toujours présents par
    convention ; les autres clés sont optionnelles.
    """

    response: str
    agent: str
    model: str
    backend: str
    suggested_skill: str | None
    error: str | None
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Contrat structurel de la toolbox injectée (diagnostics + fichiers).
# ---------------------------------------------------------------------------

class _ToolboxLike(Protocol):
    """Tout objet exposant ``describe_tools() -> str`` fait l'affaire."""

    def describe_tools(self) -> str: ...


# ---------------------------------------------------------------------------
# Mapping data-driven des fences de code -> extension de fichier.
# L'ordre d'insertion fixe la priorité de détection (powershell > bash > py).
# ---------------------------------------------------------------------------

_CODE_FENCE_TO_EXT: MappingProxyType[str, str] = MappingProxyType({
    "```powershell": "ps1",
    "```bash": "sh",
    "```python": "py",
})


class BaseAgent(ABC):
    """Contrat commun à tous les agents (dev, network, hardware, cyber, vision)."""

    # Hook de substitution (tests / sous-classes) : chemin du fichier de profils.
    PROFILES_PATH: Path = PROFILES_FILE

    # Cache de classe partagé + invalidation par mtime, protégés par verrou.
    _profile_cache: dict[str, dict[str, Any]] = {}
    _profile_mtime: float = 0.0
    _cache_lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self.toolbox: _ToolboxLike | None = None

    def inject_toolbox(self, toolbox: _ToolboxLike | None) -> None:
        """Branche la toolbox (diagnostics + fichiers) décrivant les outils."""
        self.toolbox = toolbox

    @abstractmethod
    def run(self, task: str, model: str, context: dict[str, Any]) -> AgentRunResult:
        """Exécute une tâche et retourne un :class:`AgentRunResult`."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Chargement des profils (cache mtime + verrou)
    # ------------------------------------------------------------------

    def _load_profile(self, profile_key: str) -> dict[str, Any]:
        """Charge un profil (section ``profiles``) avec cache invalidé au mtime.

        Évite un I/O disque par requête (5-15 ms sur clef USB lente).
        Le verrou rend le refresh atomique en environnement multi-thread.
        Retourne un dict vide si le fichier est absent ; logge en warning
        si le JSON est corrompu (dégradation gracieuse, pas de crash LLM).
        """
        profiles_path = Path(self.PROFILES_PATH)
        with self._cache_lock:
            try:
                current_mtime = profiles_path.stat().st_mtime
            except OSError:
                return {}
            if current_mtime != self._profile_mtime:
                try:
                    with profiles_path.open(encoding="utf-8") as handle:
                        profiles = json.load(handle).get("profiles", {})
                except FileNotFoundError:
                    return {}
                except json.JSONDecodeError as exc:
                    _logger.warning("Profils corrompus (%s): %s", profiles_path, exc)
                    return {}
                self.__class__._profile_cache = dict(profiles)
                self.__class__._profile_mtime = current_mtime
            return self._profile_cache.get(profile_key, {})

    # ------------------------------------------------------------------
    # Composition du prompt
    # ------------------------------------------------------------------

    @classmethod
    def _with_skills(cls, system: str) -> str:
        """Ajoute le texte des skills activés au system prompt (DRY).

        Dégradation silencieuse : si ``skills.json`` est illisible, le
        prompt LLM n'est jamais cassé (l'erreur est loggée en amont).
        """
        skills_text = cls._enabled_skills()
        return f"{system}\n\n{skills_text}" if skills_text else system

    @classmethod
    def _enabled_skills(cls) -> str:
        """Texte des skills activés (toggle Skills), ``''`` si aucun/erreur.

        Import paresseux pour éviter tout cycle avec ``services.skills``.
        """
        from services.skills import get_enabled_skills_text

        try:
            return get_enabled_skills_text()
        except (ImportError, OSError, ValueError) as exc:
            _logger.warning("Skills ignorés (toggle inactif): %s", exc)
            return ""

    @classmethod
    def _similar_cases_block(cls, context: dict[str, Any]) -> str:
        """Texte des cas similaires récents (max 3), ou ``''``."""
        similar = context.get("similar_cases", [])
        if not similar:
            return ""
        items = "\n".join(f"  - {s.get('text', '')[:200]}" for s in similar[:3])
        return f"\nCas similaires récents :\n{items}"

    @classmethod
    def _render_context_blocks(
        cls, profile: dict[str, Any], context: dict[str, Any],
    ) -> tuple[str, str]:
        """Construit les blocs réutilisables ``(tools_desc, similar_text)``."""
        tools = profile.get("tools", {})
        tools_desc = (
            "\nOutils disponibles :\n"
            + "\n".join(f"  - {k}: {v}" for k, v in tools.items())
            if tools
            else ""
        )
        return tools_desc, cls._similar_cases_block(context)

    def _toolbox_block(self) -> str:
        """Description de la toolbox injectée, préfixée d'un saut de ligne."""
        if self.toolbox is None:
            return ""
        toolbox_desc = self.toolbox.describe_tools()
        return f"\n{toolbox_desc}" if toolbox_desc else ""

    def _compose_parts(
        self,
        profile_key: str,
        context: dict[str, Any],
        default_prompt: str | None = None,
    ) -> tuple[str, str, str, str]:
        """Facteur commun : retourne ``(system, tools_desc, similar_text, toolbox_desc)``.

        ``default_prompt`` remplace le system prompt du profil (agents
        spécialisés : domaine cyber, prompt métier…).
        """
        profile = self._load_profile(profile_key)
        system = default_prompt if default_prompt is not None else profile.get("system_prompt", "")
        system = self._with_skills(system)
        tools_desc, similar_text = self._render_context_blocks(profile, context)
        toolbox_desc = self._toolbox_block()
        return system, tools_desc, similar_text, toolbox_desc

    def _profile_prompt(
        self,
        profile_key: str,
        task: str,
        context: dict[str, Any],
        default_prompt: str | None = None,
    ) -> str:
        """Prompt monolithe (system + outils + contexte + tâche)."""
        system, tools_desc, similar_text, _ = self._compose_parts(
            profile_key, context, default_prompt,
        )
        history = context.get("recent_tasks", [])
        return f"{system}{tools_desc}\nContexte récent : {history}{similar_text}\nTâche : {task}"

    def _build_messages(
        self,
        profile_key: str,
        task: str,
        context: dict[str, Any],
        default_prompt: str | None = None,
    ) -> tuple[str, str]:
        """Retourne ``(system_prompt, user_prompt)`` séparés pour le LLM.

        La description de la toolbox y est ajoutée côté *user* (contrairement
        à :meth:`_profile_prompt` qui la place côté *system*) : cette
        répartition est conservée telle quelle pour éviter toute régression
        de prompt.
        """
        system, tools_desc, similar_text, toolbox_desc = self._compose_parts(
            profile_key, context, default_prompt,
        )
        history = context.get("recent_tasks", [])
        user = f"{tools_desc}{toolbox_desc}\nContexte récent : {history}{similar_text}\nTâche : {task}"
        return system.strip(), user.strip()

    @staticmethod
    def _detect_skill_from_code(result: str, prefix: str = "script") -> str | None:
        """Détecte l'extension à partir des fences de code (```powershell/bash/python)."""
        for fence, ext in _CODE_FENCE_TO_EXT.items():
            if fence in result:
                return f"{prefix}.{ext}"
        return None


__all__ = ["BaseAgent", "AgentRunResult"]
