"""AnalysisReport — rapport unifié des analyseurs statiques.

Classe standalone (sans dépendance d'analyse) : dictionnaire enrichi
avec findings classés par criticité (critical/major/minor).
"""


class AnalysisReport(dict):
    """Rapport unifié avec findings classés par criticité (critical/major/minor)."""

    def __init__(self, path: str):
        super().__init__()
        self["path"] = path
        self["findings"] = []
        self["score"] = 100
        self["summary"] = {}

    def add(self, category: str, severity: str, line: int, msg: str, snippet: str = ""):
        self["findings"].append({
            "category": category, "severity": severity,
            "line": line, "message": msg, "snippet": snippet,
        })

    @property
    def total(self) -> int:
        return len(self["findings"])

    def penalize(self, n: int):
        self["score"] = max(0, self["score"] - n)

    def finalize(self):
        f = self["findings"]
        self["summary"] = {
            "total": len(f),
            "critical": sum(1 for x in f if x["severity"] == "critical"),
            "major": sum(1 for x in f if x["severity"] == "major"),
            "minor": sum(1 for x in f if x["severity"] == "minor"),
        }
        if not f:
            self["score"] = 100
        return self

    @property
    def violations(self) -> list:
        return self["findings"]
