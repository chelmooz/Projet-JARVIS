"""Agent générique — développement, réseau, matériel.

Implémentation concrète de :class:`BaseAgent` pour les profils sans logique
métier dédiée (techlead, devops, orchestrateur, designer, network, hardware).
Les comportements spécialisés (cyber, vision) vivent dans leurs modules.
"""

from __future__ import annotations

from typing import Any, Protocol

from agents.base import AgentRunResult, BaseAgent

# Prompt de domaine par défaut (évite le magic string + le piège du ``or``
# qui écraserait une chaîne vide intentionnelle).
DEFAULT_DOMAIN_PROMPT: str = "Tu es un assistant technique."


# ---------------------------------------------------------------------------
# Contrat minimal du fournisseur d'inférence (ISP : GenericAgent ne dépend
# que des deux méthodes qu'il appelle réellement).
# ---------------------------------------------------------------------------

class _ModelProvider(Protocol):
    """Sous-ensemble d'inférence requis par l'agent générique."""

    def query(self, prompt: str, model: str, system: str | None = None) -> str: ...
    def get_active_backend(self) -> str: ...


class GenericAgent(BaseAgent):
    """Agent générique piloté par un profil et un prompt de domaine."""

    def __init__(
        self,
        model_provider: _ModelProvider,
        memory: Any | None = None,
        profile_key: str = "techlead",
        domain_prompt: str | None = None,
    ) -> None:
        super().__init__()
        self.model_provider: _ModelProvider = model_provider
        # ``memory`` est injecté par la factory ; non exploité par run().
        self.memory: Any | None = memory
        self._profile_key: str = profile_key
        self._domain_prompt: str = (
            domain_prompt if domain_prompt is not None else DEFAULT_DOMAIN_PROMPT
        )

    def run(self, task: str, model: str, context: dict[str, Any]) -> AgentRunResult:
        """Exécute la tâche via le profil et retourne un :class:`AgentRunResult`."""
        system, user = self._build_messages(
            self._profile_key, task, context, default_prompt=self._domain_prompt,
        )
        response = self.model_provider.query(user, model, system=system)
        return {
            "agent": self._profile_key,
            "model": model,
            "backend": self.model_provider.get_active_backend(),
            "response": response,
            "suggested_skill": self._suggest_skill(response),
        }

    def _build_prompt(self, task: str, context: dict[str, Any]) -> str:
        """Prompt monolithe enrichi des résultats d'outils éventuels.

        Conservé pour les sous-classes / appels hérités (``run`` utilise
        :meth:`BaseAgent._build_messages`). Ajoute la section ``tool_results``
        de la toolbox si elle est disponible. L'accès à la méthode de rendu
        est défensif (``getattr``) car le contrat de base ne l'impose pas.
        """
        base = self._profile_prompt(
            self._profile_key, task, context, default_prompt=self._domain_prompt,
        )
        tool_results = context.get("tool_results", {})
        render = getattr(self.toolbox, "tool_results_to_prompt", None)
        if tool_results and render is not None:
            tool_section = render(tool_results)
            if tool_section:
                base = f"{base}\n{tool_section}"
        return base

    def _suggest_skill(self, result: str) -> str | None:
        """Infère une skill à sauvegarder depuis les fences de code de la réponse."""
        return self._detect_skill_from_code(
            result, prefix=f"{self._profile_key}_script",
        )


__all__ = ["GenericAgent", "DEFAULT_DOMAIN_PROMPT"]
