"""Tests de caractérisation pour ``agents.vision.VisionAgent`` et
``agents.cyber.CyberAgent`` (Lot 5).

Deux derniers agents non couverts : ``vision.py`` (47%) délègue l'OCR à
RapidOCR (`services/ocr.py`) puis l'analyse à un LLM texte ; ``cyber.py``
(57%) détecte un workflow par mots-clés (regex précompilés) et compose un
prompt de domaine cyber. Les deux héritent de ``BaseAgent``/``GenericAgent``
(filet Lot 4 déjà en place) — on isole ici la logique propre à chaque agent :
OCR (succès/erreur/texte vide/repli sur exception LLM) et détection de
workflow (priorité, absence, skill suggéré).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from agents.cyber import CYBER_DOMAIN_PROMPT, CyberAgent
from agents.vision import (
    VISION_ANALYSIS_MODEL,
    VISION_ANALYSIS_SYSTEM,
    VISION_DOMAIN_PROMPT,
    VisionAgent,
)

# ---------------------------------------------------------------------------
# Double commun : fournisseur d'inférence
# ---------------------------------------------------------------------------


class _FakeModelProvider:
    """Fournisseur d'inférence factice : réponse configurable, capture les appels."""

    def __init__(self, response: str = "réponse", backend: str = "ollama", raises: Exception | None = None) -> None:
        self.response = response
        self.backend = backend
        self.raises = raises
        self.calls: list[dict[str, Any]] = []

    def query(self, prompt: str, model: str, system: str | None = None) -> str:
        self.calls.append({"prompt": prompt, "model": model, "system": system})
        if self.raises is not None:
            raise self.raises
        return self.response

    def get_active_backend(self) -> str:
        return self.backend


# ===========================================================================
# VisionAgent
# ===========================================================================


def test_vision_agent_sans_image_traite_en_mode_texte(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    provider = _FakeModelProvider(response="réponse texte")
    agent = VisionAgent(provider)
    result = agent.run("explique ce concept", "modele-x", {})
    assert result["response"] == "réponse texte"
    assert result["model"] == "modele-x"
    assert result["agent"] == "designer"
    assert result["backend"] == "ollama"
    assert result["suggested_skill"] is None
    assert provider.calls[0]["model"] == "modele-x"


def test_vision_agent_avec_image_delegue_a_run_vision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    monkeypatch.setattr(
        "agents.vision.run_ocr",
        lambda image_b64: {"text": "texte détecté", "lines": 1, "error": None},
    )
    provider = _FakeModelProvider(response="analyse du texte")
    agent = VisionAgent(provider)
    result = agent.run("que dit ce document ?", "modele-x", {"image": "data:image/png;base64,ZmFrZQ=="})
    assert result["response"] == "analyse du texte"
    assert result["model"] == VISION_ANALYSIS_MODEL
    assert result["backend"] == "ollama"
    assert result["suggested_skill"] is None
    assert provider.calls[0]["model"] == VISION_ANALYSIS_MODEL
    assert provider.calls[0]["system"] == VISION_ANALYSIS_SYSTEM
    assert "texte détecté" in provider.calls[0]["prompt"]
    assert "que dit ce document ?" in provider.calls[0]["prompt"]


def test_run_vision_ocr_en_erreur_retourne_message_avertissement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agents.vision.run_ocr",
        lambda image_b64: {"text": "", "lines": 0, "error": "Image invalide (base64) : padding"},
    )
    provider = _FakeModelProvider()
    agent = VisionAgent(provider)
    response = agent._run_vision("tâche", "ZmFrZQ==")
    assert response == "⚠️ Image invalide (base64) : padding"
    assert provider.calls == []  # le LLM n'est jamais interrogé si l'OCR échoue


def test_run_vision_texte_vide_apres_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agents.vision.run_ocr",
        lambda image_b64: {"text": "   ", "lines": 0, "error": None},
    )
    provider = _FakeModelProvider()
    agent = VisionAgent(provider)
    response = agent._run_vision("tâche", "ZmFrZQ==")
    assert response == "⚠️ Aucun texte détecté dans l'image."
    assert provider.calls == []


def test_run_vision_llm_echoue_replie_sur_texte_ocr_brut(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        "agents.vision.run_ocr",
        lambda image_b64: {"text": "texte OCR brut", "lines": 1, "error": None},
    )
    provider = _FakeModelProvider(raises=RuntimeError("backend indisponible"))
    agent = VisionAgent(provider)
    with caplog.at_level(logging.WARNING, logger="jarvis.agents.vision"):
        response = agent._run_vision("tâche", "ZmFrZQ==")
    assert response == "texte OCR brut"
    assert "analyse llm échouée" in caplog.text.lower()


def test_run_ocr_appelle_strip_data_uri_puis_run_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def _fake_run_ocr(image_b64: str) -> dict[str, Any]:
        captured["image_b64"] = image_b64
        return {"text": "ok", "lines": 1, "error": None}

    monkeypatch.setattr("agents.vision.run_ocr", _fake_run_ocr)
    agent = VisionAgent(_FakeModelProvider())
    result = agent._run_ocr("data:image/png;base64,ZmFrZQ==")
    assert captured["image_b64"] == "ZmFrZQ=="
    assert result == {"text": "ok", "lines": 1, "error": None}


def test_run_ocr_log_warning_si_erreur(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(
        "agents.vision.run_ocr",
        lambda image_b64: {"text": "", "lines": 0, "error": "Erreur OCR : boom"},
    )
    agent = VisionAgent(_FakeModelProvider())
    with caplog.at_level(logging.WARNING, logger="jarvis.agents.vision"):
        result = agent._run_ocr("ZmFrZQ==")
    assert result["error"] == "Erreur OCR : boom"
    assert "ocr échoué" in caplog.text.lower()


def test_run_text_construit_les_messages_via_generic_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    provider = _FakeModelProvider(response="réponse texte")
    agent = VisionAgent(provider)
    response = agent._run_text("modele-x", "décris la photo", {"recent_tasks": ["a"]})
    assert response == "réponse texte"
    call = provider.calls[0]
    assert call["model"] == "modele-x"
    assert VISION_DOMAIN_PROMPT in (call["system"] or "")


# ===========================================================================
# CyberAgent
# ===========================================================================


def _write_workflows(path: Path, workflows: dict[str, Any]) -> None:
    path.write_text(json.dumps({"workflows": workflows}), encoding="utf-8")


def test_load_workflows_fichier_absent_retourne_dict_vide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", tmp_path / "absent.json")
    agent = CyberAgent(_FakeModelProvider())
    assert agent.get_workflows() == {}


def test_load_workflows_json_corrompu_log_warning_et_dict_vide(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "cyber_workflows.json"
    path.write_text("{pas du json", encoding="utf-8")
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", path)
    with caplog.at_level(logging.WARNING, logger="jarvis.agents.cyber"):
        agent = CyberAgent(_FakeModelProvider())
    assert agent.get_workflows() == {}
    assert "illisibles" in caplog.text.lower()


def test_load_workflows_section_non_dict_retourne_dict_vide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "cyber_workflows.json"
    path.write_text(json.dumps({"workflows": ["pas un dict"]}), encoding="utf-8")
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", path)
    agent = CyberAgent(_FakeModelProvider())
    assert agent.get_workflows() == {}


def test_load_workflows_charge_les_workflows_valides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "cyber_workflows.json"
    _write_workflows(path, {"NETWORK_SCAN": {"name": "Scan réseau", "steps": ["nmap"]}})
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", path)
    agent = CyberAgent(_FakeModelProvider())
    assert agent.get_workflows() == {"NETWORK_SCAN": {"name": "Scan réseau", "steps": ["nmap"]}}


def test_get_workflows_retourne_une_copie(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "cyber_workflows.json"
    _write_workflows(path, {"NETWORK_SCAN": {"name": "Scan"}})
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", path)
    agent = CyberAgent(_FakeModelProvider())
    copy = agent.get_workflows()
    copy["INJECTE"] = {"name": "intrus"}
    assert "INJECTE" not in agent.get_workflows()


def test_profile_key_est_datasecu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", tmp_path / "absent.json")
    agent = CyberAgent(_FakeModelProvider())
    assert agent.profile_key == "datasecu"


def test_match_workflow_priorite_au_premier_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``NETWORK_SCAN`` précède ``LOG_ANALYSIS`` dans l'ordre d'insertion."""
    path = tmp_path / "cyber_workflows.json"
    _write_workflows(
        path,
        {
            "NETWORK_SCAN": {"name": "Scan réseau", "steps": ["nmap"]},
            "LOG_ANALYSIS": {"name": "Analyse logs", "steps": ["grep"]},
        },
    )
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", path)
    agent = CyberAgent(_FakeModelProvider())
    matched = agent._match_workflow("lance un scan network puis consulte les log")
    assert matched is not None
    assert matched["name"] == "Scan réseau"


def test_match_workflow_aucun_mot_cle_retourne_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", tmp_path / "absent.json")
    agent = CyberAgent(_FakeModelProvider())
    assert agent._match_workflow("bonjour, comment vas-tu ?") is None


def test_match_workflow_cle_matchee_absente_des_workflows_charges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mot-clé matché mais workflow non défini dans le JSON -> ``None`` (``.get``)."""
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", tmp_path / "absent.json")
    agent = CyberAgent(_FakeModelProvider())
    assert agent._match_workflow("lance un scan réseau") is None


def test_workflow_prompt_vide_sans_workflow() -> None:
    assert CyberAgent._workflow_prompt(None) == ""
    assert CyberAgent._workflow_prompt({}) == ""


def test_workflow_prompt_formate_les_etapes_numerotees() -> None:
    workflow = {"name": "Scan réseau", "steps": ["nmap -sV", "analyser les ports ouverts"]}
    result = CyberAgent._workflow_prompt(workflow)
    assert result == "\nWorkflow détecté : Scan réseau\nÉtapes :\n  1. nmap -sV\n  2. analyser les ports ouverts\n"


def test_workflow_prompt_nom_absent_devient_point_interrogation() -> None:
    result = CyberAgent._workflow_prompt({"steps": ["étape unique"]})
    assert result.startswith("\nWorkflow détecté : ?\n")


def test_suggest_skill_priorite_au_skill_du_workflow() -> None:
    workflow = {"suggested_skill": "network_scan.yaml"}
    assert CyberAgent._suggest_skill("réponse quelconque", workflow) == "network_scan.yaml"


def test_suggest_skill_replie_sur_detection_fence_code() -> None:
    result = CyberAgent._suggest_skill("```bash\nnmap -sV 10.0.0.1\n```", workflow=None)
    assert result == "security_audit.sh"


def test_suggest_skill_aucun_workflow_ni_fence_retourne_none() -> None:
    assert CyberAgent._suggest_skill("juste du texte", workflow=None) is None


def test_build_cyber_messages_sans_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", tmp_path / "absent.json")
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    agent = CyberAgent(_FakeModelProvider())
    system, user = agent._build_cyber_messages("analyse ces logs", {})
    assert system == CYBER_DOMAIN_PROMPT
    assert user == "Workflows disponibles : aucun\nTâche : analyse ces logs"


def test_build_cyber_messages_avec_workflow_et_cas_similaires(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "cyber_workflows.json"
    _write_workflows(path, {"NETWORK_SCAN": {"name": "Scan réseau", "steps": ["nmap"]}})
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", path)
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    agent = CyberAgent(_FakeModelProvider())
    workflow = agent._workflows["NETWORK_SCAN"]
    context = {"similar_cases": [{"text": "cas déjà vu"}]}
    system, user = agent._build_cyber_messages("scan le réseau", context, workflow)
    assert system == CYBER_DOMAIN_PROMPT
    assert "Workflows disponibles : NETWORK_SCAN" in user
    assert "Workflow détecté : Scan réseau" in user
    assert "Cas similaires récents :\n  - cas déjà vu" in user
    assert user.endswith("Tâche : scan le réseau")


def test_run_assemble_workflow_et_appelle_le_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "cyber_workflows.json"
    _write_workflows(path, {"NETWORK_SCAN": {"name": "Scan réseau", "steps": ["nmap"], "suggested_skill": "scan.yaml"}})
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", path)
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    provider = _FakeModelProvider(response="voici l'analyse", backend="ollama")
    agent = CyberAgent(provider)
    result = agent.run("lance un scan réseau", "modele-cyber", {})
    assert result == {
        "agent": "datasecu",
        "model": "modele-cyber",
        "backend": "ollama",
        "response": "voici l'analyse",
        "suggested_skill": "scan.yaml",
    }
    assert provider.calls[0]["model"] == "modele-cyber"
    assert provider.calls[0]["system"] == CYBER_DOMAIN_PROMPT


def test_run_sans_workflow_detecte_ni_skill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agents.cyber.CYBER_WORKFLOWS_CONFIG", tmp_path / "absent.json")
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    provider = _FakeModelProvider(response="bonjour")
    agent = CyberAgent(provider)
    result = agent.run("bonjour, comment vas-tu ?", "modele-cyber", {})
    assert result["suggested_skill"] is None
