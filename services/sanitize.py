"""Sanitize — Fonctions de validation et nettoyage d'entrées.

Fournit des fonctions pures pour :
- Nettoyer les textes libres (caractères imprimables, troncation).
- Valider/sécuriser les noms de modèles, chemins, clés JSON.
- Valider les images base64.
- Scrubber les PII (emails, IPs privées, tokens, clés API).

Toutes les fonctions sont déterministes et sans état partagé.
"""

from __future__ import annotations

import base64
import re
import string
from typing import Callable, Match

# Caractères ASCII imprimables autorisés dans les entrées textuelles libres
_PRINTABLE: set[str] = set(string.printable) - {chr(127)}

_MAX_TASK_LEN: int = 20_000
_MAX_MODEL_NAME: int = 128
_MAX_PATH_LEN: int = 1024


def clean_text(text: str, max_len: int = _MAX_TASK_LEN) -> str:
    """Nettoie une chaîne libre : tronque et remplace les caractères non imprimables.

    Conserve les caractères ASCII imprimables et les caractères Unicode (>127).
    Les caractères de contrôle non imprimables (0-31, 127) sont remplacés par
    le caractère de remplacement Unicode ``\\ufffd`` ().

    Args:
        text: Chaîne à nettoyer.
        max_len: Longueur maximale (troncation).

    Returns:
        Chaîne nettoyée, ou chaîne vide si l'entrée n'est pas une chaîne.
    """
    if not isinstance(text, str):
        return ""
    cleaned = text[:max_len]
    return "".join(
        c if c in _PRINTABLE or ord(c) > 127 else "\ufffd"
        for c in cleaned
    )


def safe_model_name(name: str) -> str:
    """Valide un nom de modèle (lettres, chiffres, ``./:-_`` uniquement).

    Args:
        name: Nom de modèle à valider.

    Returns:
        Nom filtré, ou chaîne vide si invalide ou trop long.
    """
    if not name or len(name) > _MAX_MODEL_NAME:
        return ""
    allowed = set(string.ascii_letters + string.digits + "./:-_")
    return "".join(c for c in name if c in allowed)


def safe_path_segment(segment: str) -> str:
    """Nettoie un segment de chemin : supprime les caractères null et les traversées.

    Supprime les séquences ``../`` et ``..\\`` pour prévenir les path traversal.
    Supprime également les caractères null (``\\x00``) et la séquence littérale
    ``\\0`` (deux caractères, parfois injectée par des clients malveillants).

    Args:
        segment: Segment de chemin à nettoyer.

    Returns:
        Segment nettoyé, tronqué à ``_MAX_PATH_LEN``.
    """
    if not segment:
        return ""
    # Supprime le caractère null et la séquence littérale "\\0"
    cleaned = segment.replace("\\0", "").replace("\0", "")
    # Supprime les tentatives de traversée de répertoire
    cleaned = re.sub(r"(\.\.[/\\])+", "", cleaned)
    return cleaned[:_MAX_PATH_LEN]


def validate_base64_image(data: str, max_mb: int = 4) -> bool:
    """Valide une image base64 : non vide, taille max, décodage valide.

    Accepte les data URIs complètes (``data:image/png;base64,...``) en
    extrayant automatiquement la partie après la virgule.

    Args:
        data: Chaîne base64 ou data URI.
        max_mb: Taille maximale en mégaoctets.

    Returns:
        ``True`` si l'image est valide et dans la limite de taille.
    """
    if not data or not isinstance(data, str):
        return False
    try:
        base64_part = data.split(",", 1)[1] if "," in data else data
        raw = base64.b64decode(base64_part, validate=True)
        return len(raw) <= max_mb * 1024 * 1024
    except Exception:
        # ValueError (base64 invalide), binascii.Error (padding incorrect), etc.
        return False


def strip_data_uri(data: str) -> str:
    """Retire le préfixe ``data:image/...;base64,`` d'une data URI.

    Args:
        data: Data URI ou chaîne base64 brute.

    Returns:
        Partie base64 uniquement, ou chaîne vide si l'entrée est invalide.
    """
    if not data or not isinstance(data, str):
        return ""
    if "," in data:
        return data.split(",", 1)[1]
    return data


def safe_json_key(key: str) -> str:
    """Nettoie une clé JSON : alphanumérique et underscore uniquement.

    Args:
        key: Clé à nettoyer.

    Returns:
        Clé filtrée (peut être vide si aucun caractère valide).
    """
    allowed = string.ascii_letters + string.digits + "_"
    return "".join(c for c in key if c in allowed)


# ---------------------------------------------------------------------------
# Patterns PII pour scrub()
# ---------------------------------------------------------------------------

def _redact_ip(m: Match[str]) -> str:
    """Remplace une IP privée/loopback par ``[REDACTED]``, sinon laisse l'IP.

    Gère les plages RFC1918 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    et loopback (127.0.0.0/8). Les IPs publiques sont conservées.
    """
    ip = m.group(0)
    try:
        parts = list(map(int, ip.split(".")))
    except ValueError:
        # Format IP invalide (ex: "999.999.999.999") — on laisse tel quel
        return ip
    
    if len(parts) != 4:
        return ip
    
    # Loopback
    if parts[0] == 127:
        return "[REDACTED]"
    # RFC1918 : 10.0.0.0/8
    if parts[0] == 10:
        return "[REDACTED]"
    # RFC1918 : 172.16.0.0/12
    if parts[0] == 172 and 16 <= parts[1] <= 31:
        return "[REDACTED]"
    # RFC1918 : 192.168.0.0/16
    if parts[0] == 192 and parts[1] == 168:
        return "[REDACTED]"
    
    return ip


_PII_PATTERNS: list[tuple[re.Pattern[str], str | Callable[[Match[str]], str]]] = [
    # Clés AWS
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED]"),
    # Tokens GitHub
    (re.compile(r"gh[opru]_[A-Za-z0-9_]{36,}"), "[REDACTED]"),
    # Clés OpenAI / similaires
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "[REDACTED]"),
    # JWT tokens
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "[REDACTED]"),
    # Clés privées PEM
    (re.compile(r"-----BEGIN[A-Z ]+-----"), "[REDACTED]"),
    # Credentials (password=xxx, api_key: xxx, etc.)
    (re.compile(r"(?:password|passwd|pwd|secret|token|api[_-]?key)\s*[=:]\s*\S+", re.I), "[REDACTED]"),
    # Adresses IP (filtrage via _redact_ip pour ne masquer que les privées)
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), _redact_ip),
    # Emails
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[REDACTED]"),
]


def scrub(text: str) -> str:
    """Nettoie un texte des PII (emails, clés, tokens, IPs privées).

    Applique successivement tous les patterns PII définis dans ``_PII_PATTERNS``.
    Les IPs publiques sont conservées ; seules les IPs privées (RFC1918, loopback)
    sont remplacées par ``[REDACTED]``.

    Args:
        text: Texte à nettoyer.

    Returns:
        Texte avec les PII remplacées, ou chaîne vide si l'entrée est invalide.
    """
    if not isinstance(text, str) or not text:
        return ""
    result = text
    for pattern, replacement in _PII_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


__all__ = [
    "clean_text",
    "safe_model_name",
    "safe_path_segment",
    "validate_base64_image",
    "strip_data_uri",
    "safe_json_key",
    "scrub",
]
