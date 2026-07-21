"""Agent spécialisé en cybersécurité et analyse de logs (profil `datasecu`)."""

import json
import re
from typing import Any

from agents.base import BaseAgent
from config.paths import CYBER_WORKFLOWS_CONFIG


class CyberAgent(BaseAgent):
    """Agent cybersécurité : correspondances de workflows + prompts spécialisés."""

    PROFILE_KEY = "datasecu"

    def __init__(self, model_provider: Any, memory: Any) -> None:
        super().__init__()
        self.model = model_provider
        self.memory = memory
        self._workflows = self._load_workflows()

    def _load_workflows(self) -> dict:
        """Charge les workflows depuis le fichier de configuration (`cyber_workflows.json`).

        Retourne un dict vide si le fichier est absent ou corrompu.
        """
        try:
            with open(CYBER_WORKFLOWS_CONFIG, encoding="utf-8") as f:
                return json.load(f).get("workflows", {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def run(self, task: str, model: str, context: dict[str, Any]) -> dict:
        """Exécute une tâche cyber : associe un workflow, construit le prompt et interroge le LLM."""
        matched_workflow = self._match_workflow(task)
        system, user = self._build_cyber_messages(task, context, matched_workflow)
        result = self.model.query(user, model, system=system)
        return {
            "agent":           self.PROFILE_KEY,
            "model":           model,
            "backend":         self.model.get_active_backend(),
            "response":        result,
            "suggested_skill": self._suggest_skill(result, matched_workflow),
        }

    def _build_cyber_messages(
        self,
        task: str,
        context: dict[str, Any],
        workflow: dict | None = None,
    ) -> tuple[str, str]:
        """Construit ``(system, user)`` : domaine cyber + workflow détecté + cas/outils."""
        domain = (
            "Tu es specialise en cybersecurite. Analyse les logs, identifie les "
            "vulnerabilites et propose des corrections."
        )
        system, _ = self._build_messages(self.PROFILE_KEY, task, context, default_prompt=domain)
        workflow_prompt = ""
        if workflow:
            steps = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(workflow.get("steps", [])))
            workflow_prompt = f"\nWorkflow detecte: {workflow.get('name','?')}\nEtapes:\n{steps}\n"
        # Réutilise le bloc « cas similaires » défini dans BaseAgent (DRY)
        profile = self._load_profile(self.PROFILE_KEY)
        _, similar_text = self._render_context_blocks(profile, context)
        tool_results = context.get("tool_results", {})
        tool_section = ""
        if tool_results and self.toolbox:
            tool_section = self.toolbox.tool_results_to_prompt(tool_results)
        user = (
            f"Workflows disponibles: {', '.join(self._workflows.keys())}"
            f"{workflow_prompt}"
            f"{similar_text}"
            f"{tool_section}"
            f"\nTache : {task}"
        )
        return system.strip(), user.strip()

    def _match_workflow(self, task: str) -> dict | None:
        """Retourne le workflow dont un mot-clé regex apparaît dans la tâche, ou None."""
        task_lower = task.lower()
        keywords = {
            "CISA_KNOWN_EXPLOITED_VULNS": [r"\bcisa\b", r"\bkev\b", r"\bknown exploited\b", r"\bvuln\b"],
            "DETECT_EDR": [r"\bedr\b", r"\bantivirus\b", r"\bdefense\b", r"\bsecurity product\b"],
            "EDR_TELEMETRY_GAPS": [r"\btelemetry\b", r"\bgap\b", r"\bedr lacune\b"],
            "TTP_REPORT_ANALYSIS": [r"\bttp\b", r"\bmitre\b", r"\batt&ck\b", r"\breport\b", r"\badversaire\b"],
            "PRIVILEGE_AUDIT": [r"\bprivilege\b", r"\bwhoami\b", r"\badmin\b", r"\belevation\b"],
            "CALDERA_INTEL": [r"\bcaldera\b", r"\boperation\b"],
            "HELLO_CALDERA": [r"\bcaldera message\b", r"\bpopup\b", r"\bmessage box\b"],
            "FORENSIC_COLLECT": [r"\bforensic\b", r"\bcollecte\b", r"\bincident response\b"],
            "NETWORK_SCAN": [r"\bscan\b", r"\bnetwork\b", r"\bport\b", r"\bdecouvrir\b"],
            "LOG_ANALYSIS": [r"\blog\b", r"\bevenement\b", r"\bevent\b", r"\bsecurity log\b"],
        }
        for wf_key, patterns in keywords.items():
            if any(re.search(p, task_lower) for p in patterns):
                return self._workflows.get(wf_key)
        return None

    def _suggest_skill(self, result: str, workflow: dict | None = None) -> str | None:
        """Propose un skill : celui du workflow si défini, sinon détection depuis le code."""
        if workflow and workflow.get("suggested_skill"):
            return workflow["suggested_skill"]
        return self._detect_skill_from_code(result, prefix="security_audit")

    def get_workflows(self) -> dict:
        """Retourne les workflows chargés (pour exposition API)."""
        return self._workflows
