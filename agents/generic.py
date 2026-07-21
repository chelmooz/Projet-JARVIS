"""Agent generique pour le developpement, le reseau et le materiel."""
from agents.base import BaseAgent


class GenericAgent(BaseAgent):
    """GenericAgent."""

    def __init__(self, model_provider, memory, profile_key="techlead", domain_prompt=None):
        super().__init__()
        self.model = model_provider
        self.memory = memory
        self._profile_key = profile_key
        self._domain_prompt = domain_prompt or "Tu es un assistant technique."

    def run(self, task: str, model: str, context: dict) -> dict:
        """Run."""
        system, user = self._build_messages(self._profile_key, task, context,
                                            default_prompt=self._domain_prompt)
        result = self.model.query(user, model, system=system)
        return {
            "agent":           self._profile_key,
            "model":           model,
            "backend":         self.model.get_active_backend(),
            "response":        result,
            "suggested_skill": self._suggest_skill(result)
        }

    def _build_prompt(self, task: str, context: dict) -> str:
        """ build prompt."""
        base = self._profile_prompt(self._profile_key, task, context,
                                    default_prompt=self._domain_prompt)
        tool_results = context.get("tool_results", {})
        if tool_results and self.toolbox:
            tool_section = self.toolbox.tool_results_to_prompt(tool_results)
            if tool_section:
                base += "\n" + tool_section
        return base

    def _suggest_skill(self, result: str) -> str | None:
        """ suggest skill."""
        return self._detect_skill_from_code(result, prefix=f"{self._profile_key}_script")
