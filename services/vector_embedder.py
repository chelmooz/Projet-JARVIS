"""Embedder — Calcul d'embedding sémantique via le backend d'inférence.

Refacto DevOps / SOLID / KISS :
- Suppression du "fallback histogramme" : il produisait des vecteurs de 16 dimensions,
  causant des crashes ou une corruption silencieuse de l'index RAG (attendu : 768 dims).
- Principe "Fail-Fast" : si le backend d'embedding est indisponible, une exception 
  explicite est levée plutôt que de retourner des données corrompues.
- Service stateless : suppression de la mutation d'état `self.using_fallback`.
- Typage strict et gestion ciblée des exceptions.
"""
import logging
from typing import List

# Si vous avez une exception custom pour les services, importez-la. 
# Sinon, RuntimeError est approprié ici.
from services.exceptions import ServiceUnavailableError # (À créer si n'existe pas, ou utiliser RuntimeError)

_logger = logging.getLogger("jarvis.vector")


class Embedder:
    """Calcule les embeddings sémantiques via le service d'inférence injecté."""

    def __init__(self, inference_service):
        """
        Injection de dépendance stricte : l'embedder a besoin d'un service d'inférence valide.
        """
        if inference_service is None:
            raise ValueError("Le service d'inférence ne peut pas être None pour l'Embedder.")
        self._inference = inference_service

    def embed(self, text: str) -> List[float]:
        """
        Retourne le vecteur d'embedding du texte.
        
        :raises ServiceUnavailableError: Si le backend d'embedding est injoignable.
        :raises ValueError: Si le texte est vide ou invalide.
        """
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Le texte à embedder ne peut pas être vide.")

        try:
            # Délégation pure au service d'inférence (qui gère déjà ses propres retries/timeouts)
            return self._inference.embed(text)
            
        except RuntimeError as e:
            # Erreur spécifique remontée par l'OllamaAdapter (ex: modèle non trouvé, timeout)
            _logger.critical(
                "ÉCHEC CRITIQUE d'embedding : Le backend d'inférence a échoué. "
                "La fonctionnalité RAG sera indisponible pour cette requête. Détail : %s", e
            )
            raise ServiceUnavailableError(
                "Le moteur de recherche sémantique (RAG) est temporairement indisponible."
            ) from e
            
        except Exception as e:
            # Catch-all de sécurité, mais loggé en ERROR pour ne pas masquer le bug
            _logger.exception("Erreur inattendue lors du calcul de l'embedding : %s", e)
            raise ServiceUnavailableError("Erreur interne lors du calcul de l'embedding.") from e

    # ==============================================================================
    # NOTE SUR LE FALLBACK :
    # Un fallback par histogramme de bytes (16 dimensions) a été délibérément supprimé.
    # Le modèle RAG configuré (nomic-embed-text-v2-moe) produit des vecteurs de 768 dimensions.
    # Injecter un vecteur de 16 dimensions corrompt l'index vectoriel (crash NumPy/FAISS) 
    # ou génère des similarités aléatoires. La dégradation gracieuse du RAG doit se faire 
    # en désactivant la recherche, pas en inventant des données.
    # ==============================================================================
