"""Vérification SHA256 des binaires."""

from __future__ import annotations

import hashlib
from typing import Callable


def verify_sha256(
    tool_name: str,
    binary_path: str,
    expected: str,
    verified: set[str],
    audit_log_fn: Callable[[str, str], None],
) -> bool:
    """Vérifie l'intégrité SHA256 d'un binaire externe.

    Utilise une lecture par blocs pour éviter de charger entièrement
    le fichier en mémoire (important pour les binaires volumineux).

    Args:
        tool_name: Nom de l'outil (pour le logging et le cache).
        binary_path: Chemin absolu vers le binaire à vérifier.
        expected: Hash SHA256 attendu (hexadécimal).
        verified: Ensemble des outils déjà vérifiés (cache en mémoire).
        audit_log_fn: Fonction de callback pour journaliser les erreurs.

    Returns:
        ``True`` si le hash correspond ou est en cache, ``False`` sinon.
    """
    if tool_name in verified:
        return True

    try:
        sha256 = hashlib.sha256()
        with open(binary_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        
        actual = sha256.hexdigest().upper()

        if actual != expected.upper():
            audit_log_fn(
                "ERROR",
                f"SHA256 mismatch {tool_name}: attendu={expected} obtenu={actual}",
            )
            return False

        verified.add(tool_name)
        return True

    except OSError as e:
        audit_log_fn("ERROR", f"SHA256 check failed {tool_name}: {e}")
        return False


__all__ = ["verify_sha256"]
