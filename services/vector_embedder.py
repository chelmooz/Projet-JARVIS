"""Embedder — Calcul d'embedding sémantique via le backend d'inférence.

Refacto DevOps / SOLID / KISS :
- Suppression du "fallback histogramme" : il produisait des vecteurs de 16 dimensions,
  causant des crashes ou une corruption silencieuse de l'index RAG (attendu : 768 dims).
- Principe "Fail-Fast" : si le backend d'embedding est indisponible, une exception 
  explicite est levée plutôt que de retourner des données corrompues.
- Service stateless : suppression de la mutation d'état `self.using_fallback`.
- Typage strict et gestion ciblée des exceptions.
"""
from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger("jarvis.vector")


class Embedder:
    """Calcule les embeddings sémantiques via le service d'inférence injecté."""

    def __init__(self, inference_service: Any) -> None:
        """
        Injection de dépendance stricte : l'embedder a besoin d'un service d'inférence valide.
        """
        if inference_service is None:
            raise ValueError("Le service d'inférence ne peut pas être None pour l'Embedder.")
        self._inference = inference_service

    def embed(self, text: str) -> list[float]:
        """
        Retourne le vecteur d'embedding du texte.
        
        :raises RuntimeError: Si le backend d'embedding est injoignable ou échoue.
        :raises ValueError: Si le texte est vide ou invalide.
        """
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Le texte à embedder ne peut pas être vide.")

        try:
            # Délégation pure au service d'inférence (qui gère déjà ses propres retries/timeouts)
            return self._inference.embed(text)
            
        except RuntimeError as e:
            # Erreur spécifique remontée par l'adaptateur (ex: modèle non trouvé, timeout)
            _logger.critical(
                "ÉCHEC CRITIQUE d'embedding : Le backend d'inférence a échoué. "
                "La fonctionnalité RAG sera indisponible pour cette requête. Détail : %s", e
            )
            raise RuntimeError(
                "Le moteur de recherche sémantique (RAG) est temporairement indisponible."
            ) from e
            
        except Exception as e:
            # Catch-all de sécurité, mais loggé en ERROR pour ne pas masquer le bug
            _logger.exception("Erreur inattendue lors du calcul de l'embedding : %s", e)
            raise RuntimeError("Erreur interne lors du calcul de l'embedding.") from e


__all__ = ["Embedder"]
