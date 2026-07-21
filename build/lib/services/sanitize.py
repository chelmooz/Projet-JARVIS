"""Sanitize — Fonctions de validation et nettoyage d'entrées."""
import base64
import re
import string

# Caractères autorisés par défaut dans les entrées textuelles libres
_PRINTABLE = set(string.printable) - {chr(127)}
_MAX_TASK_LEN = 20_000
_MAX_MODEL_NAME = 128
_MAX_PATH_LEN = 1024


def clean_text(text: str, max_len: int = _MAX_TASK_LEN) -> str:
    """Nettoie une chaîne libre : tronque, garde l'imprimable UTF-8."""
    if not isinstance(text, str):
        return ""
    cleaned = text[:max_len]
    return "".join(c if c in _PRINTABLE or ord(c) > 127 else "\ufffd" for c in cleaned)


def safe_model_name(name: str) -> str:
    """Valide un nom de modèle (lettres, chiffres, ./:/- uniquement)."""
    if not name or len(name) > _MAX_MODEL_NAME:
        return ""
    allowed = set(string.ascii_letters + string.digits + "./:-_")
    return "".join(c for c in name if c in allowed)


def safe_path_segment(segment: str) -> str:
    """Nettoie un segment de chemin : interdit '../'."""
    if not segment:
        return ""
    cleaned = segment.replace("\\0", "").replace("\0", "")
    cleaned = re.sub(r"(\.\.[/\\])+", "", cleaned)
    return cleaned[: _MAX_PATH_LEN]


def validate_base64_image(data: str, max_mb: int = 4) -> bool:
    """Valide une image base64 : non vide, taille max, decodage valide."""
    if not data or not isinstance(data, str):
        return False
    try:
        base64_part = data.split(",", 1)[1] if "," in data else data
        raw = base64.b64decode(base64_part, validate=True)
        return len(raw) <= max_mb * 1024 * 1024
    except (ValueError, IndexError, Exception):
        return False


def strip_data_uri(data: str) -> str:
    """Retire le prefixe 'data:image/...;base64,' d'une data URI."""
    if not data or not isinstance(data, str):
        return ""
    if "," in data:
        return data.split(",", 1)[1]
    return data


def safe_json_key(key: str) -> str:
    """Nettoie une clé JSON : alphanumérique et underscore uniquement."""
    return "".join(c for c in key if c in string.ascii_letters + string.digits + "_")


# Patterns PII pour scrub()
def _redact_ip(m: re.Match) -> str:
    """Remplace une IP privée/loopback par [REDACTED], sinon laisse."""
    ip = m.group(0)
    parts = list(map(int, ip.split(".")))
    if parts[0] == 10 or parts[0] == 127:
        return "[REDACTED]"
    if parts[0] == 192 and parts[1] == 168:
        return "[REDACTED]"
    if parts[0] == 172 and 16 <= parts[1] <= 31:
        return "[REDACTED]"
    return ip


_PII_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED]"),
    (re.compile(r"gh[opru]_[A-Za-z0-9_]{36,}"), "[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "[REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "[REDACTED]"),
    (re.compile(r"-----BEGIN[A-Z ]+-----"), "[REDACTED]"),
    (re.compile(r"(?:password|passwd|pwd|secret|token|api[_-]?key)\s*[=:]\s*\S+", re.I), "[REDACTED]"),
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), _redact_ip),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[REDACTED]"),
]


def scrub(text: str) -> str:
    """Nettoie un texte des PII (emails, cles, tokens, IPs privees)."""
    if not isinstance(text, str):
        return ""
    if not text:
        return ""
    result = text
    for pattern, replacement in _PII_PATTERNS:
        result = pattern.sub(replacement, result)
    return result
