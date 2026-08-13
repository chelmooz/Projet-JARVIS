"""Exceptions du module diagnostic externe."""

from __future__ import annotations


class DiagnosticExtError(Exception):
    """Erreur contrôlée du service de diagnostic externe.

    Levée en cas d'échec de chargement de configuration, de vérification
    SHA256, ou d'exécution d'un outil externe.
    """


__all__ = ["DiagnosticExtError"]
