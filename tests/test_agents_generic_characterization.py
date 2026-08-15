"""Tests de caractérisation pour ``agents.generic.GenericAgent`` (Lot 6).

Dernier fichier du dossier ``agents/`` non couvert (61%) — implémentation
concrète de ``BaseAgent`` pour les profils sans logique métier dédiée
(techlead, devops, orchestrateur, designer, network, hardware). Le filet
Lot 4 couvre déjà ``BaseAgent`` ; on isole ici ``run()``, ``_build_prompt``
(orpheline en production, conservée pour héritage — testée directement) et
``_suggest_skill``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agents.generic import DEFAULT_DOMAIN_PROMPT, GenericAgent


class _FakeModelProvider:
    """Fournisseur d'inférence factice : réponse configurable, capture les appels."""

    def __init__(self, response: str = "réponse", backend: str = "ollama") -> None:
        self.response = response
        self.backend = backend
        self.calls: list[dict[str, Any]] = []

    def query(self, prompt: str, model: str, system: str | None = None) -> str:
        self.calls.append({"prompt": prompt, "model": model, "system": system})
        return self.response

    def get_active_backend(self) -> str:
        return self.backend


class _FakeToolbox:
    """Toolbox factice exposant ``tool_results_to_prompt``."""

    def __init__(self, results_text: str = "") -> None:
        self.results_text = results_text

    def describe_tools(self) -> str:
        return ""

    def tool_results_to_prompt(self, results: dict[str, Any]) -> str:
        return self.results_text


@pytest.fixture
def isolated_generic_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isole ``PROFILES_PATH`` + cache de classe de ``GenericAgent`` (Lot 4, même risque).

    ``_profile_cache``/``_profile_mtime`` sont des attributs de classe hérités de
    ``BaseAgent`` (partagés par toutes les sous-classes tant qu'elles ne les
    redéfinissent pas). Sans isolation, ces tests dépendraient du contenu réel
    de ``config/agent_profiles.json`` (le profil ``techlead`` y a de vrais
    outils) et pourraient lire un cache pollué par d'autres tests/lots.
    """
    empty_profiles = tmp_path / "empty_profiles.json"
    empty_profiles.write_text('{"profiles": {}}', encoding="utf-8")
    monkeypatch.setattr(GenericAgent, "PROFILES_PATH", empty_profiles)
    monkeypatch.setattr(GenericAgent, "_profile_cache", {})
    monkeypatch.setattr(GenericAgent, "_profile_mtime", 0.0)


# ---------------------------------------------------------------------------
# __init__ / profile_key
# ---------------------------------------------------------------------------


def test_init_valeurs_par_defaut() -> None:
    provider = _FakeModelProvider()
    agent = GenericAgent(provider)
    assert agent.profile_key == "techlead"
    assert agent._domain_prompt == DEFAULT_DOMAIN_PROMPT
    assert agent.memory is None
    assert agent.model_provider is provider


def test_init_profile_key_et_domain_prompt_personnalises() -> None:
    agent = GenericAgent(_FakeModelProvider(), profile_key="network", domain_prompt="Tu es réseau.")
    assert agent.profile_key == "network"
    assert agent._domain_prompt == "Tu es réseau."


def test_init_domain_prompt_vide_est_respecte_et_non_ecrase() -> None:
    """Piège du ``or`` documenté dans le code : ``\"\"`` doit être conservé tel quel."""
    agent = GenericAgent(_FakeModelProvider(), domain_prompt="")
    assert agent._domain_prompt == ""


def test_init_memory_injectee() -> None:
    memory = object()
    agent = GenericAgent(_FakeModelProvider(), memory=memory)
    assert agent.memory is memory


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


def test_run_retourne_le_dict_attendu(isolated_generic_agent: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    provider = _FakeModelProvider(response="voici la réponse", backend="ollama")
    agent = GenericAgent(provider, profile_key="devops")
    result = agent.run("déploie le service", "modele-x", {})
    assert result == {
        "agent": "devops",
        "model": "modele-x",
        "backend": "ollama",
        "response": "voici la réponse",
        "suggested_skill": None,
    }


def test_run_construit_le_prompt_via_build_messages(
    isolated_generic_agent: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    provider = _FakeModelProvider()
    agent = GenericAgent(provider, profile_key="hardware", domain_prompt="Tu es hardware.")
    agent.run("diagnostique le matériel", "modele-x", {"recent_tasks": ["a"]})
    call = provider.calls[0]
    assert call["model"] == "modele-x"
    assert call["system"] == "Tu es hardware."
    assert "diagnostique le matériel" in call["prompt"]


def test_run_detecte_une_skill_depuis_une_fence_de_code(
    isolated_generic_agent: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    provider = _FakeModelProvider(response="```bash\nls -la\n```")
    agent = GenericAgent(provider, profile_key="devops")
    result = agent.run("liste les fichiers", "modele-x", {})
    assert result["suggested_skill"] == "devops_script.sh"


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


def test_build_prompt_sans_toolbox_ni_tool_results(
    isolated_generic_agent: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    agent = GenericAgent(_FakeModelProvider(), profile_key="techlead", domain_prompt="Tu es techlead.")
    prompt = agent._build_prompt("revoir le design", {"recent_tasks": ["a"]})
    assert prompt == "Tu es techlead.\nContexte récent : ['a']\nTâche : revoir le design"


def test_build_prompt_ajoute_la_section_tool_results_si_toolbox_et_resultats(
    isolated_generic_agent: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    agent = GenericAgent(_FakeModelProvider(), profile_key="techlead", domain_prompt="Tu es techlead.")
    agent.inject_toolbox(_FakeToolbox(results_text="[Résultats outils]\ngrep -> 3 occurrences"))
    prompt = agent._build_prompt("analyse le code", {"tool_results": {"grep": {"count": 3}}})
    assert prompt.endswith("Tâche : analyse le code\n[Résultats outils]\ngrep -> 3 occurrences")


def test_build_prompt_sans_tool_results_ignore_la_toolbox(
    isolated_generic_agent: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    agent = GenericAgent(_FakeModelProvider(), profile_key="techlead", domain_prompt="Tu es techlead.")
    agent.inject_toolbox(_FakeToolbox(results_text="ne doit pas apparaître"))
    prompt = agent._build_prompt("analyse le code", {})
    assert "ne doit pas apparaître" not in prompt


def test_build_prompt_toolbox_sans_render_defensif(
    isolated_generic_agent: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``getattr`` défensif : toolbox sans ``tool_results_to_prompt`` -> pas de crash."""

    class _BareToolbox:
        def describe_tools(self) -> str:
            return ""

    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    agent = GenericAgent(_FakeModelProvider(), profile_key="techlead", domain_prompt="Tu es techlead.")
    agent.inject_toolbox(_BareToolbox())
    prompt = agent._build_prompt("analyse le code", {"tool_results": {"grep": {}}})
    assert prompt == "Tu es techlead.\nContexte récent : []\nTâche : analyse le code"


def test_build_prompt_render_falsy_n_ajoute_rien(isolated_generic_agent: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    agent = GenericAgent(_FakeModelProvider(), profile_key="techlead", domain_prompt="Tu es techlead.")
    agent.inject_toolbox(_FakeToolbox(results_text=""))
    prompt = agent._build_prompt("analyse le code", {"tool_results": {"grep": {}}})
    assert prompt == "Tu es techlead.\nContexte récent : []\nTâche : analyse le code"


# ---------------------------------------------------------------------------
# _suggest_skill
# ---------------------------------------------------------------------------


def test_suggest_skill_aucune_fence_retourne_none() -> None:
    agent = GenericAgent(_FakeModelProvider(), profile_key="devops")
    assert agent._suggest_skill("juste du texte") is None


def test_suggest_skill_prefixe_par_le_profil() -> None:
    agent = GenericAgent(_FakeModelProvider(), profile_key="network")
    result = agent._suggest_skill("```python\nprint('ok')\n```")
    assert result == "network_script.py"
