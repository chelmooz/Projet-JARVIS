"""Embedder — calcul d'embedding (Ollama) avec repli histogramme.

Responsabilité unique (SRP) : produire le vecteur d'un texte, que ce soit via
le backend d'inférence configuré ou via le repli déterministe (histogramme).
"""
import logging

_logger = logging.getLogger("jarvis.vector")


class Embedder:
    """Calcule les embeddings, avec fallback histogramme si le backend échoue."""

    def __init__(self, inference=None):
        self._inference = inference
        self.using_fallback = False

    def embed(self, text: str) -> list[float]:
        """Retourne l'embedding du texte (Ollama si dispo, sinon histogramme)."""
        if self._inference:
            try:
                return self._inference.embed(text)
            except Exception as e:
                _logger.error("Echec embedding Ollama (%s), fallback histogramme", e)
        self.using_fallback = True
        return self._fallback_embed(text)

    @staticmethod
    def _fallback_embed(text: str) -> list[float]:
        bins = 16
        counts = [0.0] * bins
        for b in text.encode("utf-8"):
            counts[b % bins] += 1.0
        total = sum(counts) or 1
        return [c / total for c in counts]
