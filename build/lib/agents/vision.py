"""Agent specialise en analyse d'images et vision par ordinateur."""
from agents.generic import GenericAgent


class VisionAgent(GenericAgent):
    """VisionAgent."""

    def __init__(self, model_provider, memory):
        super().__init__(model_provider, memory, profile_key="designer",
                         domain_prompt="Tu es un expert en analyse visuelle.")

    def run(self, task: str, model: str, context: dict) -> dict:
        """Run."""
        image_data = context.get("image")
        if image_data:
            # query_multimodal renvoie un dict {"content": ..., "model": ..., "role": ...}
            result = self.model.query_multimodal(model, task, image_data)
            response = result.get("content") if isinstance(result, dict) else result
        else:
            system, user = self._build_messages(self._profile_key, task, context,
                                                default_prompt=self._domain_prompt)
            response = self.model.query(user, model, system=system)
        return {
            "agent":           self._profile_key,
            "model":           model,
            "backend":         self.model.get_active_backend(),
            "response":        response,
            "suggested_skill": None
        }
