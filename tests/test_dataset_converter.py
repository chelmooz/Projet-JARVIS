"""Tests pour services.dataset_converter — fonctions pures de conversion JSONL."""

from __future__ import annotations

from services.dataset_converter import (
    ALLOWED_CATEGORIES,
    EXCLUDED_TOOLS,
    convert_ad_attacks,
    convert_multios,
    filter_ad_attacks,
)

# ---------------------------------------------------------------------------
# Fixtures d'entrées synthétiques
# ---------------------------------------------------------------------------

_AD_ATTACK_DISCOVERY = {
    "id": "T1018",
    "name": "Remote System Discovery",
    "description": "Adversaries may attempt to get a listing of other systems by IP address.",
    "category": "discovery",
    "mitre_technique_ids": ["T1018"],
    "severity": "Medium",
    "prerequisites": ["Network access"],
    "tools": ["PowerShell", "net view"],
    "detection": "EventID 4624",
    "mitigation": "Network segmentation",
    "source_url": "https://attack.mitre.org/techniques/T1018/",
}

_AD_ATTACK_CREDENTIAL_ACCESS = {
    "id": "T1558.003",
    "name": "Kerberoasting",
    "description": "Adversaries may request service tickets to crack offline.",
    "category": "credential_access",
    "mitre_technique_ids": ["T1558.003"],
    "severity": "High",
    "prerequisites": ["Domain user"],
    "tools": ["Rubeus", "Impacket"],
    "detection": "EventID 4769",
    "mitigation": "Strong service account passwords",
    "source_url": "https://attack.mitre.org/techniques/T1558/003/",
}

_AD_ATTACK_LATERAL_MIMIKATZ = {
    "id": "T1550.002",
    "name": "Pass-the-Hash",
    "description": "Adversaries may use stolen hashes for lateral movement.",
    "category": "lateral_movement",
    "mitre_technique_ids": ["T1550.002"],
    "severity": "High",
    "prerequisites": ["Hash dump"],
    "tools": ["Mimikatz", "Impacket"],
    "detection": "EventID 4624",
    "mitigation": "Credential Guard",
    "source_url": "https://attack.mitre.org/techniques/T1550/002/",
}

_MULTIOS_ENTRY = {
    "instruction": "Find the PID of 'mysql'",
    "input": "",
    "output": '{"description": "Find the PID of \'mysql\'", "linux": "pgrep mysql", "windows": "tasklist | findstr mysql", "mac": "pgrep mysql"}',
}

_MULTIOS_ENTRY_WINDOWS_ONLY = {
    "instruction": "Check AppArmor status",
    "input": "[WINDOWS]",
    "output": "echo N/A",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_filter_keeps_discovery_category() -> None:
    """Entrée category='discovery' (enum LDAP) → gardée."""
    kept = filter_ad_attacks([_AD_ATTACK_DISCOVERY])
    assert len(kept) == 1
    assert kept[0]["id"] == "T1018"


def test_filter_excludes_credential_access() -> None:
    """Entrée category='credential_access' (Kerberoasting) → exclue."""
    kept = filter_ad_attacks([_AD_ATTACK_CREDENTIAL_ACCESS])
    assert len(kept) == 0


def test_filter_excludes_mimikatz_even_if_allowed_category() -> None:
    """category='lateral_movement' mais tools=['Mimikatz'] → exclue."""
    kept = filter_ad_attacks([_AD_ATTACK_LATERAL_MIMIKATZ])
    assert len(kept) == 0


def test_convert_ad_attacks_schema() -> None:
    """Sortie a les 5 clés, agent == '@network', text = '{name}: {description}'."""
    filtered = filter_ad_attacks([_AD_ATTACK_DISCOVERY])
    converted = convert_ad_attacks(filtered)
    assert len(converted) == 1
    entry = converted[0]
    # 5 clés requises
    assert set(entry.keys()) == {"id", "agent", "source", "text", "metadata"}
    assert entry["agent"] == "@network"
    assert entry["source"] == "AYI-NEDJIMI/ad-attacks-en"
    assert (
        entry["text"]
        == "Remote System Discovery: Adversaries may attempt to get a listing of other systems by IP address."
    )
    assert "mitre_technique_ids" in entry["metadata"]
    assert entry["metadata"]["category"] == "discovery"


def test_convert_multios_schema_windows() -> None:
    """Sortie agent == '@hardware', text contient la commande Windows, metadata contient linux/mac."""
    converted = convert_multios([_MULTIOS_ENTRY])
    assert len(converted) == 1
    entry = converted[0]
    assert set(entry.keys()) == {"id", "agent", "source", "text", "metadata"}
    assert entry["agent"] == "@hardware"
    assert entry["source"] == "Eng-Elias/multios-terminal-commands"
    # text doit contenir la commande Windows
    assert "tasklist | findstr mysql" in entry["text"]
    # metadata doit contenir les 3 OS
    assert "linux" in entry["metadata"]
    assert "windows" in entry["metadata"]
    assert "mac" in entry["metadata"]
    assert entry["metadata"]["windows"] == "tasklist | findstr mysql"
    assert entry["metadata"]["linux"] == "pgrep mysql"
    assert entry["metadata"]["mac"] == "pgrep mysql"


def test_allowed_categories_constant() -> None:
    """ALLOWED_CATEGORIES contient les 4 catégories réseau pur."""
    assert "reconnaissance" in ALLOWED_CATEGORIES
    assert "discovery" in ALLOWED_CATEGORIES
    assert "lateral_movement" in ALLOWED_CATEGORIES
    assert "command_and_control" in ALLOWED_CATEGORIES
    # credential_access n'est PAS dedans
    assert "credential_access" not in ALLOWED_CATEGORIES


def test_excluded_tools_constant() -> None:
    """EXCLUDED_TOOLS contient Mimikatz et Rubeus."""
    assert "Mimikatz" in EXCLUDED_TOOLS
    assert "Rubeus" in EXCLUDED_TOOLS
