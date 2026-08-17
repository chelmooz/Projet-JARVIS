#!/usr/bin/env python3
"""Script temporaire MT-KB-L2b : téléchargement + conversion JSONL (non commité).

- Télécharge ad-attacks-en + multios-terminal-commands via httpx
- Applique les convertisseurs purs (services.dataset_converter)
- Écrit wiki/sources/ad-attacks-network.jsonl + wiki/sources/multios-commands.jsonl
- Audit @dev : requête GitHub API sur microsoft/PowerShell-Scripts
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

# Ajouter le répertoire racine au path pour importer services
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.dataset_converter import (
    convert_ad_attacks,
    convert_multios,
    filter_ad_attacks,
)


# ---------------------------------------------------------------------------
# Configuration URLs
# ---------------------------------------------------------------------------

AD_ATTACKS_BASE = "https://huggingface.co/datasets/AYI-NEDJIMI/ad-attacks-en/resolve/main/data"
AD_ATTACKS_FILES = [
    "attacks.json",
    "tools.json",
    "detection_rules.json",
    "qa_dataset.json",
]

MULTIOS_URL = "https://huggingface.co/datasets/Eng-Elias/multios-terminal-commands/resolve/main/datasets/generated/processed/train.json"

GITHUB_API = "https://api.github.com/repos/microsoft/PowerShell-Scripts"

OUTPUT_DIR = Path(__file__).parent.parent / "wiki" / "sources"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def download_json(client: httpx.Client, url: str) -> list[dict] | dict:
    """Télécharge et parse du JSON."""
    resp = client.get(url, timeout=60.0)
    resp.raise_for_status()
    return resp.json()


def write_jsonl(path: Path, entries: list[dict], max_entries: int = 1000) -> int:
    """Écrit une liste d'entrées en JSONL. Retourne le nombre d'entrées écrites (max max_entries)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8") as f:
        for entry in entries[:max_entries]:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            written += 1
    return written


# ---------------------------------------------------------------------------
# Conversion datasets
# ---------------------------------------------------------------------------

def convert_ad_attacks_dataset(client: httpx.Client) -> tuple[int, int]:
    """Télécharge, filtre, convertit ad-attacks-en. Retourne (gardées, exclues)."""
    all_entries: list[dict] = []
    for fname in AD_ATTACKS_FILES:
        url = f"{AD_ATTACKS_BASE}/{fname}"
        print(f"  Téléchargement {fname}...")
        data = download_json(client, url)
        if isinstance(data, list):
            all_entries.extend(data)
        elif isinstance(data, dict) and "train" in data:
            # Format HF dataset
            all_entries.extend(data["train"])
        else:
            all_entries.append(data)

    print(f"  Total entrées brutes : {len(all_entries)}")
    filtered = filter_ad_attacks(all_entries)
    excluded = len(all_entries) - len(filtered)
    print(f"  Après filtre : {len(filtered)} gardées, {excluded} exclues")

    converted = convert_ad_attacks(filtered)
    out_path = OUTPUT_DIR / "ad-attacks-network.jsonl"
    written = write_jsonl(out_path, converted)
    print(f"  Écrit : {out_path} ({written} entrées)")
    return written, excluded


def convert_multios_dataset(client: httpx.Client) -> int:
    """Télécharge, convertit multios-terminal-commands. Retourne nb entrées."""
    print(f"  Telechargement multios-terminal-commands...")
    data = download_json(client, MULTIOS_URL)
    entries = data if isinstance(data, list) else data.get("train", [])
    print(f"  Total entrees : {len(entries)}")

    converted = convert_multios(entries)
    out_path = OUTPUT_DIR / "multios-commands.jsonl"
    written = write_jsonl(out_path, converted, max_entries=1000)
    print(f"  Ecrit : {out_path} ({written} entrees, limite 1000)")
    return written


# ---------------------------------------------------------------------------
# Audit @dev : microsoft/PowerShell-Scripts
# ---------------------------------------------------------------------------

def audit_powershell_scripts(client: httpx.Client) -> dict:
    """Audite le repo GitHub microsoft/PowerShell-Scripts."""
    print(f"  Audit GitHub : {GITHUB_API}...")
    try:
        resp = client.get(GITHUB_API, timeout=30.0)
        if resp.status_code == 404:
            return {"status": "NOT_FOUND", "error": "Repo 404 - n'existe pas"}
        resp.raise_for_status()
        repo_info = resp.json()

        # Vérifier la licence
        license_info = repo_info.get("license")
        license_key = license_info.get("key") if license_info else None
        license_name = license_info.get("name") if license_info else None

        # Compter les fichiers .ps1 via l'API contents (racine)
        contents_resp = client.get(f"{GITHUB_API}/contents", timeout=30.0)
        contents_resp.raise_for_status()
        contents = contents_resp.json()
        ps1_files = [c for c in contents if c["name"].endswith(".ps1")]

        return {
            "status": "OK",
            "full_name": repo_info.get("full_name"),
            "description": repo_info.get("description"),
            "license_key": license_key,
            "license_name": license_name,
            "stars": repo_info.get("stargazers_count"),
            "forks": repo_info.get("forks_count"),
            "ps1_files_root": len(ps1_files),
            "default_branch": repo_info.get("default_branch"),
            "url": repo_info.get("html_url"),
        }
    except httpx.HTTPStatusError as e:
        return {"status": "HTTP_ERROR", "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("MT-KB-L2b : Conversion datasets valides + audit @dev")
    print("=" * 60)

    client = httpx.Client(
        headers={"User-Agent": "JARVIS-KB/1.0"},
        follow_redirects=True,
    )

    try:
        # 1. ad-attacks-en -> @network
        print("\n[1/3] ad-attacks-en (@network)...")
        kept, excluded = convert_ad_attacks_dataset(client)

        # 2. multios-terminal-commands -> @hardware
        print("\n[2/3] multios-terminal-commands (@hardware)...")
        multios_count = convert_multios_dataset(client)

        # 3. Audit @dev
        print("\n[3/3] Audit @dev : microsoft/PowerShell-Scripts...")
        audit_result = audit_powershell_scripts(client)

        # Rapport final
        print("\n" + "=" * 60)
        print("RAPPORT MT-KB-L2b")
        print("=" * 60)
        print(f"ad-attacks-network.jsonl : {kept} entrees (exclues : {excluded})")
        print(f"multios-commands.jsonl   : {multios_count} entrees")
        print()
        print("Audit @dev (microsoft/PowerShell-Scripts) :")
        print(f"  Status       : {audit_result['status']}")
        if audit_result["status"] == "OK":
            print(f"  Repo         : {audit_result['full_name']}")
            print(f"  Licence      : {audit_result['license_key']} ({audit_result['license_name']})")
            print(f"  .ps1 (racine): {audit_result['ps1_files_root']}")
            print(f"  Stars/Forks  : {audit_result['stars']}/{audit_result['forks']}")
            print(f"  URL          : {audit_result['url']}")
        else:
            print(f"  Erreur       : {audit_result.get('error', 'inconnue')}")
        print("=" * 60)

        # Decision selon audit
        if audit_result["status"] != "OK":
            print("\n[STOP] Audit @dev echoue - pas de substitution spontanee.")
            print("   Alternatives a proposer dans le rapport :")
            print("   - PowerShell/PowerShell (MIT) - repo core PowerShell")
            print("   - Microsoft Learn docs (CC-BY-4.0) - docs officielles")
            return 1

        if audit_result.get("license_key") not in ("MIT", "Apache-2.0", "BSD-3-Clause", "CC-BY-4.0"):
            print(f"\n[ATTENTION] Licence '{audit_result['license_key']}' - verifier compatibilite.")
            return 1

        print("\n[OK] Conversion reussie, audit @dev OK.")
        return 0

    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())