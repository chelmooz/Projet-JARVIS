"""Vérification SHA256 des binaires."""
import hashlib


def verify_sha256(tool_name: str, binary_path: str, expected: str,
                  verified: set, audit_log_fn) -> bool:
    if tool_name in verified:
        return True
    try:
        with open(binary_path, "rb") as f:
            actual = hashlib.sha256(f.read()).hexdigest().upper()
        if actual != expected.upper():
            audit_log_fn("ERROR", f"SHA256 mismatch {tool_name}: "
                         f"attendu={expected} obtenu={actual}")
            return False
        verified.add(tool_name)
        return True
    except Exception as e:
        audit_log_fn("ERROR", f"SHA256 check failed {tool_name}: {e}")
        return False
