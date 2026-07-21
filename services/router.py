"""Service de routage — Selection de l'agent JARVIS par analyse de mots-clés."""
from models import Task


class AgentRouter:
    """Router détermine quel agent (cyber, dev, network, hardware, vision)
    doit traiter une tâche en fonction de son contenu textuel.

    Stratégie (par ordre de priorité) :
      1. Préfixe explicite (@cyber, @dev, etc.)
      2. Score de mots-clés (agent avec le plus de matches gagne)
      3. Agent par défaut : "dev"
    """

    def __init__(self):
        # Cartographie préfixe -> agent (priorité max)
        self._prefix_map = {
            "@cyber": "cyber", "@dev": "dev", "@network": "network",
            "@hardware": "hardware", "@vision": "vision",
            # Alias depuis les profils de l'onglet Agents
            "@orchestrateur": "dev", "@techlead": "dev",
            "@devops": "dev", "@designer": "dev", "@datasecu": "cyber",
        }
        # Mots-clés par agent (analyse par score cumulé)
        self._keyword_map = {
            "cyber":    ["securite", "security", "log", "audit", "firewall", "forensic",
                         "vulnerabilite", "malware", "virus", "hack", "attaque", "intrusion"],
            "dev":      ["script", "code", "debug", "python", "bash", "powershell",
                         "fonction", "programme", "algorithme", "developpement"],
            "network":  ["reseau", "network", "ip", "vlan", "tcp", "ping", "dns",
                         "routeur", "port", "connectivite", "wifi", "latence"],
            "hardware": ["driver", "bios", "ram", "cpu", "disque", "materiel",
                         "temperature", "panne", "ecran bleu", "ventilo"],
            "vision":   ["image", "screenshot", "capture", "photo", "visuel", "ecran"],
        }
        self._fallback = "dev"

    def select_agent(self, task_text: str | Task) -> str:
        """Retourne la clé agent la plus pertinente pour la tâche donnée."""
        if isinstance(task_text, Task):
            task_text = task_text.text
        lower = task_text.lower().strip()
        if not lower:
            return self._fallback

        # Priorité 1 : préfixe explicite @agent
        for prefix, agent in self._prefix_map.items():
            if lower.startswith(prefix):
                return agent

        # Priorité 2 : score de mots-clés (agent avec le plus de hits)
        scores = {}
        for agent, keywords in self._keyword_map.items():
            scores[agent] = sum(1 for k in keywords if k in lower)
        if scores and max(scores.values()) > 0:
            return max(scores, key=scores.get)

        # Priorité 3 : fallback par défaut
        return self._fallback
