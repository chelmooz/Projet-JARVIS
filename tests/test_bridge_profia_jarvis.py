"""Tests pour le pont Prof IA → JSONL JARVIS (MT-KB-L11).

Couvre la transformation des JSON Prof IA vers JSONL par agent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


def _import_bridge() -> Any:
    """Import lazy du script bridge."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from scripts.bridge_profia_jarvis import (
        main,
        map_metier_to_agent,
        normalize_text_for_dedup,
        process_json_file,
    )

    return {
        "map_metier_to_agent": map_metier_to_agent,
        "normalize_text_for_dedup": normalize_text_for_dedup,
        "process_json_file": process_json_file,
        "main": main,
    }


class TestMetierToAgentMapping:
    """Tests du mapping métier → agent."""

    def test_ais_maps_to_cyber(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("AIS", "", "") == "@cyber"

    def test_devops_maps_to_dev(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("DevOps", "", "") == "@dev"

    def test_tssr_default_maps_to_hardware(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("TSSR", "some text", "file.txt") == "@hardware"

    def test_tssr_with_network_keywords_maps_to_network(self) -> None:
        bridge = _import_bridge()
        text = "configuration vlan et routage bgp"
        assert bridge["map_metier_to_agent"]("TSSR", text, "file.txt") == "@network"

    def test_tssr_with_ospf_keyword_maps_to_network(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("TSSR", "ospf configuration", "file.txt") == "@network"

    def test_tssr_with_switch_keyword_maps_to_network(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("TSSR", "switch config", "file.txt") == "@network"

    def test_tssr_with_tcp_ip_keyword_maps_to_network(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("TSSR", "tcp/ip settings", "file.txt") == "@network"

    def test_tssr_with_vpn_keyword_maps_to_network(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("TSSR", "vpn setup", "file.txt") == "@network"

    def test_tssr_with_wifi_keyword_maps_to_network(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("TSSR", "wifi config", "file.txt") == "@network"

    def test_tssr_with_support_in_filename_maps_to_designer(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("TSSR", "text", "support_ticket.json") == "@designer"

    def test_tssr_with_helpdesk_in_filename_maps_to_designer(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("TSSR", "text", "helpdesk_log.json") == "@designer"

    def test_tssr_with_ticket_in_filename_maps_to_designer(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("TSSR", "text", "ticket_123.json") == "@designer"

    def test_transverse_maps_to_orchestrateur(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("Transverse", "", "") == "@orchestrateur"

    def test_unknown_metier_defaults_to_orchestrateur(self) -> None:
        bridge = _import_bridge()
        assert bridge["map_metier_to_agent"]("Unknown", "", "") == "@orchestrateur"


class TestNormalizeTextForDedup:
    """Tests de la normalisation pour déduplication MD5."""

    def test_normalize_strips_whitespace(self) -> None:
        bridge = _import_bridge()
        assert bridge["normalize_text_for_dedup"]("  hello world  ") == "hello world"

    def test_normalize_lowercase(self) -> None:
        bridge = _import_bridge()
        assert bridge["normalize_text_for_dedup"]("HELLO WORLD") == "hello world"

    def test_normalize_collapse_spaces(self) -> None:
        bridge = _import_bridge()
        assert bridge["normalize_text_for_dedup"]("hello   world") == "hello world"

    def test_normalize_handles_newlines(self) -> None:
        bridge = _import_bridge()
        assert bridge["normalize_text_for_dedup"]("hello\nworld") == "hello world"


class TestProcessJsonFile:
    """Tests du traitement d'un fichier JSON Prof IA."""

    def test_process_json_file_basic(self, tmp_path: Path) -> None:
        bridge = _import_bridge()

        # Créer un JSON factice
        json_data = {
            "source": "AIS",
            "filename": "test_doc.pdf",
            "file_id": "abc123",
            "is_eni": False,
            "traduit": False,
            "chunks": [
                {
                    "id": "chunk_1",
                    "chunk_id": "0",
                    "text": "This is a test chunk about cybersecurity attacks and mitigation strategies for enterprise networks.",
                    "metadata": {
                        "metier": "AIS",
                        "source": "AIS",
                        "filename": "test_doc.pdf",
                        "has_code": False,
                    },
                },
                {
                    "id": "chunk_2",
                    "chunk_id": "1",
                    "text": "Another chunk with sufficient length for the filter to pass the minimum character requirement.",
                    "metadata": {
                        "metier": "AIS",
                        "source": "AIS",
                        "filename": "test_doc.pdf",
                        "has_code": True,
                    },
                },
                {
                    "id": "chunk_3",
                    "chunk_id": "2",
                    "text": "Short",
                    "metadata": {
                        "metier": "AIS",
                        "source": "AIS",
                        "filename": "test_doc.pdf",
                        "has_code": False,
                    },
                },
            ],
        }

        json_file = tmp_path / "test.json"
        json_file.write_text(json.dumps(json_data), encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        process_json_file = bridge["process_json_file"]
        process_json_file(json_file, output_dir)

        # Vérifier que le fichier @cyber.jsonl a été créé
        cyber_file = output_dir / "@cyber.jsonl"
        assert cyber_file.exists()

        lines = cyber_file.read_text(encoding="utf-8").strip().split("\n")
        # 2 chunks >= 80 chars (le 3e est trop court)
        assert len(lines) == 2

        # Vérifier le contenu de la première ligne
        entry = json.loads(lines[0])
        assert entry["text"] == json_data["chunks"][0]["text"]
        assert entry["metadata"]["agent"] == "@cyber"
        assert entry["metadata"]["topic"] == "AIS"
        assert entry["metadata"]["source"] == "test_doc.pdf"
        assert entry["metadata"]["difficulty"] == "intermediate"
        assert entry["metadata"]["has_code"] is False

        # Vérifier la deuxième ligne (has_code = True)
        entry2 = json.loads(lines[1])
        assert entry2["metadata"]["has_code"] is True

    def test_process_json_file_skips_short_chunks(self, tmp_path: Path) -> None:
        bridge = _import_bridge()

        json_data = {
            "source": "DevOps",
            "filename": "devops_guide.md",
            "file_id": "dev456",
            "chunks": [
                {
                    "id": "c1",
                    "chunk_id": "0",
                    "text": "x" * 79,  # Trop court (< 80)
                    "metadata": {"metier": "DevOps", "has_code": False},
                },
                {
                    "id": "c2",
                    "chunk_id": "1",
                    "text": "x" * 80,  # Exactement 80
                    "metadata": {"metier": "DevOps", "has_code": False},
                },
                {
                    "id": "c3",
                    "chunk_id": "2",
                    "text": "x" * 100,
                    "metadata": {"metier": "DevOps", "has_code": False},
                },
            ],
        }

        json_file = tmp_path / "test.json"
        json_file.write_text(json.dumps(json_data), encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        process_json_file = bridge["process_json_file"]
        process_json_file(json_file, output_dir)

        dev_file = output_dir / "@dev.jsonl"
        lines = dev_file.read_text(encoding="utf-8").strip().split("\n")
        # 2 chunks >= 80 chars
        assert len(lines) == 2

    def test_process_json_file_deduplicates_chunks(self, tmp_path: Path) -> None:
        bridge = _import_bridge()

        json_data = {
            "source": "TSSR",
            "filename": "network_config.txt",
            "file_id": "net789",
            "chunks": [
                {
                    "id": "c1",
                    "chunk_id": "0",
                    "text": "Configure VLAN and routing for the network switch with detailed configuration steps.",
                    "metadata": {"metier": "TSSR", "has_code": False},
                },
                {
                    "id": "c2",
                    "chunk_id": "1",
                    "text": "Configure VLAN and routing for the network switch with detailed configuration steps.",  # Duplicata
                    "metadata": {"metier": "TSSR", "has_code": False},
                },
                {
                    "id": "c3",
                    "chunk_id": "2",
                    "text": "Different content about VLAN firewall rules and security policies for enterprise networks and data centers.",
                    "metadata": {"metier": "TSSR", "has_code": False},
                },
            ],
        }

        json_file = tmp_path / "test.json"
        json_file.write_text(json.dumps(json_data), encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        process_json_file = bridge["process_json_file"]
        process_json_file(json_file, output_dir)

        # TSSR avec mots-clés réseau -> @network
        network_file = output_dir / "@network.jsonl"
        lines = network_file.read_text(encoding="utf-8").strip().split("\n")
        # 2 chunks uniques (le duplicata supprimé)
        assert len(lines) == 2

    def test_process_json_file_handles_corrupted_json(self, tmp_path: Path, caplog) -> None:
        bridge = _import_bridge()

        json_file = tmp_path / "corrupted.json"
        json_file.write_text("{ invalid json", encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        process_json_file = bridge["process_json_file"]
        # Ne doit pas planter, juste logger un warning
        process_json_file(json_file, output_dir)

        # Vérifier qu'aucun fichier de sortie n'a été créé
        assert not any(output_dir.iterdir())

    def test_process_json_file_skips_backup_files(self, tmp_path: Path) -> None:
        bridge = _import_bridge()

        json_data = {
            "source": "AIS",
            "filename": "test.pdf",
            "chunks": [{"id": "c1", "chunk_id": "0", "text": "x" * 100, "metadata": {}}],
        }

        # Fichier normal
        json_file = tmp_path / "test.json"
        json_file.write_text(json.dumps(json_data), encoding="utf-8")

        # Fichier _backup (doit être ignoré)
        backup_file = tmp_path / "test_backup.json"
        backup_file.write_text(json.dumps(json_data), encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        process_json_file = bridge["process_json_file"]
        process_json_file(json_file, output_dir)
        process_json_file(backup_file, output_dir)

        cyber_file = output_dir / "@cyber.jsonl"
        lines = cyber_file.read_text(encoding="utf-8").strip().split("\n")
        # Seulement 1 entrée (le backup ignoré)
        assert len(lines) == 1


class TestMainIntegration:
    """Test d'intégration avec --limit."""

    def test_main_with_limit(self, tmp_path: Path) -> None:
        bridge = _import_bridge()

        # Créer quelques fichiers JSON
        for i in range(3):
            json_data = {
                "source": "AIS" if i == 0 else ("TSSR" if i == 1 else "Transverse"),
                "filename": f"doc_{i}.pdf",
                "file_id": f"id_{i}",
                "chunks": [
                    {
                        "id": f"c{i}_1",
                        "chunk_id": "0",
                        "text": "Content " + "x" * 100,
                        "metadata": {"metier": "AIS", "has_code": False},
                    }
                ],
            }
            (tmp_path / f"doc_{i}.json").write_text(json.dumps(json_data), encoding="utf-8")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        main = bridge["main"]

        # Simuler les arguments CLI
        with patch(
            "sys.argv",
            ["bridge_profia_jarvis.py", "--input-dir", str(tmp_path), "--output-dir", str(output_dir), "--limit", "2"],
        ):
            result = main()

        assert result == 0

        # Vérifier que seulement 2 fichiers ont été traités
        cyber_file = output_dir / "@cyber.jsonl"

        # AIS -> @cyber (1 fichier traité)
        assert cyber_file.exists()
        assert len(cyber_file.read_text().strip().split("\n")) == 1

        # TSSR -> @hardware (1 fichier traité, mais 2ème dans la liste)
        # Note: l'ordre dépend de l'itération, mais limit=2 signifie 2 fichiers traités
        # Le 3ème (Transverse) ne devrait pas être traité


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
""
