"""Tests pour services.dataset_converter_v2 — fonctions pures de conversion JSONL."""

from __future__ import annotations

from services.dataset_converter_v2 import (
    ALLOWED_AD_CATEGORIES,
    EXCLUDED_AD_TOOLS,
    ad_attack_allowed,
    convert_ad_attacks,
    convert_multios,
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

_AD_ATTACK_LATERAL_CLEAN = {
    "id": "T1021.002",
    "name": "PSExec",
    "description": "Microsoft tool enabling remote command execution via hidden admin share.",
    "category": "lateral_movement",
    "mitre_technique_ids": ["T1021.002"],
    "severity": "High",
    "prerequisites": ["Valid admin credentials", "SMB/445 connectivity"],
    "tools": ["PsExec", "Impacket psexec", "Invoke-PSExec"],
    "detection": "Temporary service creation",
    "mitigation": "Monitor C$ access",
    "source_url": "https://attack.mitre.org/techniques/T1021/002/",
}

_MULTIOS_WINDOWS = {
    "instruction": "Find the PID of 'mysql'",
    "input": "",
    "output": '{"description": "Find the PID of \'mysql\'", "linux": "pgrep mysql", "windows": "tasklist | findstr mysql", "mac": "pgrep mysql"}',
}

_MULTIOS_WINDOWS_ONLY = {
    "instruction": "Check AppArmor status",
    "input": "[WINDOWS]",
    "output": "echo N/A",
}

_MULTIOS_NO_WINDOWS = {
    "instruction": "List files",
    "input": "[LINUX]",
    "output": '{"description": "List files", "linux": "ls -la", "windows": "", "mac": "ls -la"}',
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_filter_ad_keeps_network_pure() -> None:
    """category='discovery' (réseau pur) → gardée."""
    assert ad_attack_allowed(_AD_ATTACK_DISCOVERY) is True


def test_filter_ad_excludes_credential_access() -> None:
    """category='credential_access' → exclue."""
    assert ad_attack_allowed(_AD_ATTACK_CREDENTIAL_ACCESS) is False


def test_filter_ad_excludes_mimikatz() -> None:
    """category='lateral_movement' + tools=['Mimikatz'] → exclue."""
    assert ad_attack_allowed(_AD_ATTACK_LATERAL_MIMIKATZ) is False


def test_convert_multios_keeps_windows_only() -> None:
    """Entrée avec commande windows non vide → gardée, texte contient instruction + commande.
    Entrée windows vide → exclue."""
    converted = convert_multios([_MULTIOS_WINDOWS, _MULTIOS_WINDOWS_ONLY, _MULTIOS_NO_WINDOWS])
    # 1 entrée gardée (seule _MULTIOS_WINDOWS a une vraie commande Windows)
    assert len(converted) == 1
    # Vérifier que le texte contient l'instruction et la commande windows
    assert "Find the PID" in converted[0]["text"]
    assert "tasklist | findstr mysql" in converted[0]["text"]


def test_schema_jsonl() -> None:
    """Sortie = exactement {id, agent, source, text, metadata}."""
    converted_ad = convert_ad_attacks([_AD_ATTACK_DISCOVERY])
    converted_multios = convert_multios([_MULTIOS_WINDOWS])

    for entry in converted_ad + converted_multios:
        assert set(entry.keys()) == {"id", "agent", "source", "text", "metadata"}

    assert converted_ad[0]["agent"] == "@network"
    assert converted_ad[0]["source"] == "ad-attacks-en"
    assert converted_multios[0]["agent"] == "@hardware"
    assert converted_multios[0]["source"] == "multios-terminal-commands"


def test_allowed_categories_constant() -> None:
    """ALLOWED_AD_CATEGORIES contient les 4 catégories réseau pur."""
    assert "reconnaissance" in ALLOWED_AD_CATEGORIES
    assert "discovery" in ALLOWED_AD_CATEGORIES
    assert "lateral_movement" in ALLOWED_AD_CATEGORIES
    assert "command_and_control" in ALLOWED_AD_CATEGORIES
    assert "credential_access" not in ALLOWED_AD_CATEGORIES
    assert "persistence" not in ALLOWED_AD_CATEGORIES
    assert "privilege_escalation" not in ALLOWED_AD_CATEGORIES
    assert "defense_evasion" not in ALLOWED_AD_CATEGORIES


def test_excluded_tools_constant() -> None:
    """EXCLUDED_AD_TOOLS contient Mimikatz et Rubeus."""
    assert "Mimikatz" in EXCLUDED_AD_TOOLS
    assert "Rubeus" in EXCLUDED_AD_TOOLS
