import os
import pytest


class TestPathTraversalCodeReview:
    """Teste la protection contre le Path Traversal sur l'endpoint code_review."""

    @pytest.fixture(autouse=True)
    def _force_sandbox(self, monkeypatch):
        """Force le sandbox actif pour ce test.

        Sans ceci, services/file_system.py::_is_inside_sandbox désactive
        volontairement la vérification quand 'pytest' est dans sys.modules
        (mode dev/test) : authorize_path() retourne alors True pour
        n'importe quel chemin, et ce test de sécurité ne teste rien du tout
        (5/5 échecs en apparence, mais en réalité le garde-fou n'est jamais
        sollicité). On force ici le vrai comportement de production.
        """
        monkeypatch.setenv("JARVIS_FILES_SANDBOX_ROOT", os.getcwd())

    MALICIOUS_PATHS = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "/etc/passwd",
        "C:\\Windows\\System32\\config\\sam",
        "....//....//etc/passwd"
    ]

    @pytest.mark.parametrize("bad_path", MALICIOUS_PATHS)
    def test_code_review_rejects_path_traversal(self, client, bad_path):
        """
        RED/GREEN : La route doit rejeter les tentatives de sortie du workspace.
        L'utilisation de `params` garantit un encodage URL correct des caractères spéciaux.
        """
        # Appel robuste avec encodage automatique des query params
        response = client.get("/api/code-review/file", params={"path": bad_path})
        
        # On s'attend à 400 (Bad Request) ou 403 (Forbidden)
        assert response.status_code in [400, 403], \
            f"Faille Path Traversal : la route n'a pas bloqué '{bad_path}' (Status: {response.status_code} | Réponse: {response.text})"