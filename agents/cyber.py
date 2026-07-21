"""Agent spécialisé en cybersécurité et analyse de logs (profil ``datasecu``).

Responsabilités (SRP)
---------------------
- Détection *data-driven* d'un workflow cyber par mots-clés (regex précompilés).
- Composition d'un prompt de domaine cyber enrichi du workflow détecté.
- Délégation de l'inférence au fournisseur injecté.

Le mapping mots-clés -> workflow est une **constante de module** (et non un
littéral enfoui dans la méthode) : c'est testable, lisible, et ajouter un
workflow ne touche pas à la logique (OCP). Les regex y sont précompilées une
seule fois au chargement du module (pas à chaque requête).

Note : ce mapping est un candidat naturel à externalisation vers
``config/cyber_workflow_keywords.yaml`` (single source of truth prévue) ; on
le branchera dessus une fois la structure de ce YAML lue et validée. D'ici là,
cette constante reste la source de vérité runtime.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

from agents.base import AgentRunResult, BaseAgent
from config.paths import CYBER_WORKFLOWS_CONFIG

_logger = logging.getLogger("jarvis.agents.cyber")

# ---------------------------------------------------------------------------
# Prompt de domaine cyber (évite le magic string).
# ---------------------------------------------------------------------------

CYBER_DOMAIN_PROMPT: str = (
    "Tu es spécialisé en cybersécurité. Analyse les logs, identifie les "
    "vulnérabilités et propose des corrections."
)

# ---------------------------------------------------------------------------
# Mots-clés de détection des workflows (regex précompilés, ordre = priorité).
# Les clés correspondent aux clés de ``cyber_workflows.json``.
# MappingProxyType : immuable au runtime. L'ordre d'insertion fixe la priorité.
# ---------------------------------------------------------------------------

_WORKFLOW_KEYWORDS: MappingProxyType[str, tuple[re.Pattern[str], ...]] = MappingProxyType({
    "CISA_KNOWN_EXPLOITED_VULNS": tuple(
        re.compile(p) for p in (
            r"\bcisa\b", r"\bkev\b", r"\bknown exploited\b", r"\bvuln\b",
        )
    ),
    "DETECT_EDR": tuple(
        re.compile(p) for p in (
            r"\bedr\b", r"\bantivirus\b", r"\bdefense\b", r"\bsecurity product\b",
        )
    ),
    "EDR_TELEMETRY_GAPS": tuple(
        re.compile(p) for p in (r"\btelemetry\b", r"\bgap\b", r"\bedr lacune\b")
    ),
    "TTP_REPORT_ANALYSIS": tuple(
        re.compile(p) for p in (
            r"\bttp\b", r"\bmitre\b", r"\batt&ck\b", r"\breport\b", r"\badversaire\b",
        )
    ),
    "PRIVILEGE_AUDIT": tuple(
        re.compile(p) for p in (
            r"\bprivilege\b", r"\bwhoami\b", r"\badmin\b", r"\belevation\b",
        )
    ),
    "CALDERA_INTEL": tuple(re.compile(p) for p in (r"\bcaldera\b", r"\boperation\b")),
    "HELLO_CALDERA": tuple(
        re.compile(p) for p in (r"\bcaldera message\b", r"\bpopup\b", r"\bmessage box\b")
    ),
    "FORENSIC_COLLECT": tuple(
        re.compile(p) for p in (r"\bforensic\b", r"\bcollecte\b", r"\bincident response\b")
    ),
    "NETWORK_SCAN": tuple(
        re.compile(p) for p in (r"\bscan\b", r"\bnetwork\b", r"\bport\b", r"\bdecouvrir\b")
    ),
    "LOG_ANALYSIS": tuple(
        re.compile(p) for p in (r"\blog\b", r"\bevenement\b", r"\bevent\b", r"\bsecurity log\b")
    ),
})


# ---------------------------------------------------------------------------
# Contrat minimal du fournisseur d'inférence (ISP).
# ---------------------------------------------------------------------------

class _ModelProvider(Protocol):
    """Sous-ensemble d'inférence requis par l'agent cyber."""

    def query(self, prompt: str, model: str, system: str | None = None) -> str: ...
    def get_active_backend(self) -> str: ...


class CyberAgent(BaseAgent):
    """Agent cybersécurité : correspondances de workflows + prompts spécialisés."""

    PROFILE_KEY: str = "datasecu"

    def __init__(self, model_provider: _ModelProvider, memory: Any | None = None) -> None:
        super().__init__()
        self.model_provider: _ModelProvider = model_provider
        # ``memory`` injecté par la factory pour compat ; non exploité par run().
        self.memory: Any | None = memory
        self._workflows: dict[str, dict[str, Any]] = self._load_workflows()

    # ------------------------------------------------------------------
    # Chargement des workflows
    # ------------------------------------------------------------------

    @staticmethod
    def _load_workflows() -> dict[str, dict[str, Any]]:
        """Charge ``cyber_workflows.json`` (section ``workflows``).

        Dégradation gracieuse : dict vide si absent ; warning si corrompu
        (observable, mais sans crasher le LLM).
        """
        workflows_path = Path(CYBER_WORKFLOWS_CONFIG)
        try:
            with workflows_path.open(encoding="utf-8") as handle:
                return json.load(handle).get("workflows", {})
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError) as exc:
            _logger.warning("Workflows cyber illisibles (%s): %s", workflows_path, exc)
            return {}

    # ------------------------------------------------------------------
    # Exécution
    # ------------------------------------------------------------------

    def run(self, task: str, model: str, context: dict[str, Any]) -> AgentRunResult:
        """Associe un workflow, construit le prompt cyber et interroge le LLM."""
        matched_workflow = self._match_workflow(task)
        system, user = self._build_cyber_messages(task, context, matched_workflow)
        response = self.model_provider.query(user, model, system=system)
        return {
            "agent": self.PROFILE_KEY,
            "model": model,
            "backend": self.model_provider.get_active_backend(),
            "response": response,
            "suggested_skill": self._suggest_skill(response, matched_workflow),
        }

    # ------------------------------------------------------------------
    # Composition du prompt
    # ------------------------------------------------------------------

    def _build_cyber_messages(
        self,
        task: str,
        context: dict[str, Any],
        workflow: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """Construit ``(system, user)`` : domaine cyber + workflow + cas/outils.

        Optimisation : le ``system`` est dérivé directement du prompt de domaine
        (``_with_skills``) sans repasser par ``_build_messages`` qui reconstruit
        un ``user`` ici inutilisé. Le bloc « cas similaires » est obtenu sans
        recharger le profil (``_similar_cases_block`` suffit).
        """
        system = self._with_skills(CYBER_DOMAIN_PROMPT).strip()

        workflow_prompt = self._workflow_prompt(workflow)
        similar_text = self._similar_cases_block(context)
        tool_section = self._tool_results_section(context)

        workflow_names = ", ".join(self._workflows.keys()) if self._workflows else "aucun"
        user = (
            f"Workflows disponibles : {workflow_names}"
            f"{workflow_prompt}"
            f"{similar_text}"
            f"{tool_section}"
            f"\nTâche : {task}"
        )
        return system, user.strip()

    @staticmethod
    def _workflow_prompt(workflow: dict[str, Any] | None) -> str:
        """Bloc texte du workflow détecté, ou ``''``."""
        if not workflow:
            return ""
        steps = "\n".join(
            f"  {i + 1}. {s}" for i, s in enumerate(workflow.get("steps", []))
        )
        return f"\nWorkflow détecté : {workflow.get('name', '?')}\nÉtapes :\n{steps}\n"

    def _tool_results_section(self, context: dict[str, Any]) -> str:
        """Section ``tool_results`` de la toolbox, défensive (méthode optionnelle)."""
        tool_results = context.get("tool_results", {})
        render = getattr(self.toolbox, "tool_results_to_prompt", None)
        if not tool_results or render is None:
            return ""
        return render(tool_results) or ""

    # ------------------------------------------------------------------
    # Détection de workflow
    # ------------------------------------------------------------------

    def _match_workflow(self, task: str) -> dict[str, Any] | None:
        """Retourne le 1er workflow dont un mot-clé regex matche la tâche."""
        task_lower = task.lower()
        for wf_key, patterns in _WORKFLOW_KEYWORDS.items():
            if any(pattern.search(task_lower) for pattern in patterns):
                return self._workflows.get(wf_key)
        return None

    # ------------------------------------------------------------------
    # Skill suggéré & exposition API
    # ------------------------------------------------------------------

    @classmethod
    def _suggest_skill(
        cls, result: str, workflow: dict[str, Any] | None = None,
    ) -> str | None:
        """Skill du workflow si défini, sinon détection depuis les fences de code."""
        if workflow and workflow.get("suggested_skill"):
            return workflow["suggested_skill"]
        return cls._detect_skill_from_code(result, prefix="security_audit")

    def get_workflows(self) -> dict[str, dict[str, Any]]:
        """Retourne une copie des workflows chargés (exposition API, pas de fuite)."""
        return dict(self._workflows)


__all__ = ["CyberAgent", "CYBER_DOMAIN_PROMPT"]
