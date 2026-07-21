"""Factory — Instance unique des 5 agents JARVIS."""
from agents.cyber import CyberAgent
from agents.generic import GenericAgent
from agents.vision import VisionAgent


def create_agents(inference_service, memory_service) -> dict:
    """Create agents."""
    return {
        "cyber":    CyberAgent(inference_service, memory_service),
        "dev":      GenericAgent(inference_service, memory_service, profile_key="techlead",
                                 domain_prompt="Expert scripting et developpement."),
        "network":  GenericAgent(inference_service, memory_service, profile_key="devops",
                                 domain_prompt="Expert reseaux."),
        "hardware": GenericAgent(inference_service, memory_service, profile_key="orchestrateur",
                                 domain_prompt="Expert materiel."),
        "vision":   VisionAgent(inference_service, memory_service),
    }
