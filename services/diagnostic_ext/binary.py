"""Résolution du chemin d'un binaire à partir de la config."""
import os
import shutil
import sys


def resolve_binary(config: dict, tool_name: str, bin_dir: str) -> str | None:
    cfg = config.get("tools", {}).get(tool_name)
    if not cfg:
        return None
    if sys.platform == "win32":
        binary = cfg.get("binary")
        path = os.path.join(bin_dir, binary) if binary else None
    else:
        binary = cfg.get("linux_binary") or cfg.get("binary")
        path = shutil.which(binary)
        if not path and binary:
            path = os.path.join(bin_dir, binary)
    if path and os.path.exists(path):
        return path
    return None
