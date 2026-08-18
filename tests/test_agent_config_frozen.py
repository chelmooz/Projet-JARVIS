"""Tests MT-KB-L3h-bis — config agents figée (source unique ``config/agent_profiles.json``).

Gel de la configuration exacte décidée par l'utilisateur : chaque agent de
routage (cyber, dev, network, hardware) doit résoudre son modèle GGUF réel via
``config.agent_profiles.model_for_agent`` (mapping ``AGENT_TO_PROFILE`` →
``profiles.<key>.model``), et ``@vision`` reste un court-circuit RapidOCR
(sentinelle ``rapidocr``, aucun profil JSON).

Ces tests échouent si ``agent_profiles.json`` retombe sur les mauvais modèles
(HEAD 83e10cd : techlead=Qwen2.5, devops=granite).
"""

from __future__ import annotations

from config.agent_profiles import model_for_agent
from services.selector import VISION_OCR_SENTINEL, select_model

CYBER = "hf.co/GGUF-A-Lot/DeepHat-V1-7B-GGUF:Q4_K_M"
DEV = "hf.co/bartowski/ibm-granite_granite-4.1-8b-GGUF:Q4_K_M"
NETWORK = "hf.co/fdtn-ai/Foundation-Sec-8B-Reasoning-Q8_0-GGUF:Q8_0"
HARDWARE = "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"


def test_cyber_is_deephat() -> None:
    assert model_for_agent("cyber") == CYBER


def test_dev_is_granite() -> None:
    assert model_for_agent("dev") == DEV


def test_network_is_foundation_sec() -> None:
    assert model_for_agent("network") == NETWORK


def test_hardware_is_qwen() -> None:
    assert model_for_agent("hardware") == HARDWARE


def test_vision_is_rapidocr_sentinel() -> None:
    assert select_model("vision", None) == VISION_OCR_SENTINEL == "rapidocr"
