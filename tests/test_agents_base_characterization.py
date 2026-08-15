"""Tests de caractérisation pour ``agents.base.BaseAgent`` (Lot 4).

``BaseAgent`` est la classe mère de tous les agents (dev, network, hardware,
cyber, vision) — effet de levier maximal, 45% de couverture avant ce fichier.
Ces tests figent le comportement observé du code ACTUEL (cache de profils par
mtime + verrou, composition de prompt, détection de skill par fence de code)
sans en modifier une seule assertion produit.

Convention : une sous-classe concrète minimale (``_ConcreteAgent``) permet
d'instancier ``BaseAgent`` (ABC) sans dépendre d'un agent métier réel.
``PROFILES_PATH`` est surchargé par sous-classe (hook documenté dans
``agents/base.py``) plutôt que monkeypatché globalement, pour ne jamais
polluer le cache de classe partagé entre tests.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

import pytest

from agents.base import AgentRunResult, BaseAgent

# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


def _make_agent_class(profiles_path: Path) -> type[BaseAgent]:
    """Fabrique une sous-classe concrète isolée (cache de classe dédié).

    Chaque test obtient sa propre classe (donc son propre ``_profile_cache``
    / ``_profile_mtime``) : le cache étant un attribut de classe partagé
    documenté comme volontaire, on ne le partage pas *entre tests*.
    """

    class _ConcreteAgent(BaseAgent):
        PROFILES_PATH: Path = profiles_path
        _profile_cache: dict[str, dict[str, Any]] = {}
        _profile_mtime: float = 0.0
        _cache_lock: threading.Lock = threading.Lock()

        def run(self, task: str, model: str, context: dict[str, Any]) -> AgentRunResult:
            return {"response": "ok", "agent": "concrete", "model": model}

    return _ConcreteAgent


class _FakeToolbox:
    """Toolbox factice : ``describe_tools`` + ``tool_results_to_prompt`` configurables."""

    def __init__(self, description: str = "", results_text: str = "") -> None:
        self.description = description
        self.results_text = results_text
        self.last_results: dict[str, Any] | None = None

    def describe_tools(self) -> str:
        return self.description

    def tool_results_to_prompt(self, results: dict[str, Any]) -> str:
        self.last_results = results
        return self.results_text


class _BareToolbox:
    """Toolbox sans ``tool_results_to_prompt`` (contrat optionnel — defensif)."""

    def describe_tools(self) -> str:
        return "outils basiques"


def _write_profiles(path: Path, profiles: dict[str, Any]) -> None:
    path.write_text(json.dumps({"profiles": profiles}), encoding="utf-8")


# ---------------------------------------------------------------------------
# __init__ / inject_toolbox / profile_key
# ---------------------------------------------------------------------------


def test_init_toolbox_none_par_defaut(tmp_path: Path) -> None:
    agent_cls = _make_agent_class(tmp_path / "profiles.json")
    agent = agent_cls()
    assert agent.toolbox is None


def test_inject_toolbox_branche_l_attribut(tmp_path: Path) -> None:
    agent_cls = _make_agent_class(tmp_path / "profiles.json")
    agent = agent_cls()
    toolbox = _FakeToolbox()
    agent.inject_toolbox(toolbox)
    assert agent.toolbox is toolbox


def test_inject_toolbox_none_reset(tmp_path: Path) -> None:
    agent_cls = _make_agent_class(tmp_path / "profiles.json")
    agent = agent_cls()
    agent.inject_toolbox(_FakeToolbox())
    agent.inject_toolbox(None)
    assert agent.toolbox is None


def test_profile_key_none_par_defaut(tmp_path: Path) -> None:
    agent_cls = _make_agent_class(tmp_path / "profiles.json")
    agent = agent_cls()
    assert agent.profile_key is None


def test_base_agent_est_abstrait() -> None:
    with pytest.raises(TypeError):
        BaseAgent()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# _load_profile — cache mtime + verrou
# ---------------------------------------------------------------------------


def test_load_profile_fichier_absent_retourne_dict_vide(tmp_path: Path) -> None:
    agent_cls = _make_agent_class(tmp_path / "absent.json")
    agent = agent_cls()
    assert agent._load_profile("dev") == {}


def test_load_profile_charge_le_profil_demande(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    _write_profiles(path, {"dev": {"system_prompt": "Tu es dev."}})
    agent = _make_agent_class(path)()
    assert agent._load_profile("dev") == {"system_prompt": "Tu es dev."}


def test_load_profile_clef_inconnue_retourne_dict_vide(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    _write_profiles(path, {"dev": {"system_prompt": "Tu es dev."}})
    agent = _make_agent_class(path)()
    assert agent._load_profile("inconnu") == {}


def test_load_profile_json_corrompu_log_warning_et_dict_vide(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = tmp_path / "profiles.json"
    path.write_text("{ceci n'est pas du json", encoding="utf-8")
    agent = _make_agent_class(path)()
    with caplog.at_level(logging.WARNING, logger="jarvis.agents.base"):
        result = agent._load_profile("dev")
    assert result == {}
    assert "corrompus" in caplog.text.lower()


def test_load_profile_cache_evite_une_relecture_disque(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    _write_profiles(path, {"dev": {"system_prompt": "v1"}})
    agent_cls = _make_agent_class(path)
    agent = agent_cls()
    assert agent._load_profile("dev") == {"system_prompt": "v1"}

    # Le fichier change sur disque mais le mtime ne bouge pas explicitement :
    # on simule un fichier verrouillé/illisible pour prouver que le cache
    # (déjà chaud, même mtime) est bien servi sans relecture.
    original_open = Path.open

    def _boom(self: Path, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - garde
        raise AssertionError("le disque n'aurait pas dû être relu (cache valide)")

    # mtime inchangé => la relecture ne doit jamais être déclenchée.
    Path.open = _boom  # type: ignore[method-assign]
    try:
        assert agent._load_profile("dev") == {"system_prompt": "v1"}
    finally:
        Path.open = original_open  # type: ignore[method-assign]


def test_load_profile_invalide_le_cache_si_mtime_change(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    _write_profiles(path, {"dev": {"system_prompt": "v1"}})
    agent_cls = _make_agent_class(path)
    agent = agent_cls()
    assert agent._load_profile("dev") == {"system_prompt": "v1"}

    # mtime doit changer : on force explicitement une valeur future pour
    # éviter la flakiness des systèmes de fichiers à faible résolution.
    _write_profiles(path, {"dev": {"system_prompt": "v2"}})
    import os
    import time

    future = time.time() + 5
    os.utime(path, (future, future))

    assert agent._load_profile("dev") == {"system_prompt": "v2"}


def test_load_profile_open_leve_filenotfound_entre_stat_et_open(tmp_path: Path) -> None:
    """Course : ``stat()`` réussit puis le fichier disparaît avant ``open()``."""
    path = tmp_path / "profiles.json"
    _write_profiles(path, {"dev": {"system_prompt": "v1"}})
    agent = _make_agent_class(path)()

    original_open = Path.open

    def _vanished(self: Path, *args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("disparu entre stat() et open()")

    Path.open = _vanished  # type: ignore[method-assign]
    try:
        assert agent._load_profile("dev") == {}
    finally:
        Path.open = original_open  # type: ignore[method-assign]


def test_load_profile_fichier_devient_absent_apres_premier_chargement(tmp_path: Path) -> None:
    """OSError sur ``stat()`` (ex. fichier supprimé entre deux appels) -> dict vide."""
    path = tmp_path / "profiles.json"
    _write_profiles(path, {"dev": {"system_prompt": "v1"}})
    agent = _make_agent_class(path)()
    assert agent._load_profile("dev") == {"system_prompt": "v1"}
    path.unlink()
    assert agent._load_profile("dev") == {}


# ---------------------------------------------------------------------------
# _with_skills / _enabled_skills
# ---------------------------------------------------------------------------


def test_with_skills_ajoute_le_texte_si_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    agent_cls = _make_agent_class(tmp_path / "profiles.json")
    monkeypatch.setattr(
        "services.skills.get_enabled_skills_text",
        lambda: "[Skills actifs]\nrestez concis",
    )
    result = agent_cls._with_skills("Tu es un assistant.")
    assert result == "Tu es un assistant.\n\n[Skills actifs]\nrestez concis"


def test_with_skills_ne_touche_pas_au_system_si_aucun_skill(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    agent_cls = _make_agent_class(tmp_path / "profiles.json")
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    assert agent_cls._with_skills("Tu es un assistant.") == "Tu es un assistant."


@pytest.mark.parametrize("exc", [ImportError("x"), OSError("x"), ValueError("x")])
def test_enabled_skills_degrade_silencieusement_sur_erreurs_attendues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, exc: Exception
) -> None:
    agent_cls = _make_agent_class(tmp_path / "profiles.json")

    def _raise() -> str:
        raise exc

    monkeypatch.setattr("services.skills.get_enabled_skills_text", _raise)
    with caplog.at_level(logging.WARNING, logger="jarvis.agents.base"):
        result = agent_cls._enabled_skills()
    assert result == ""
    assert "skills ignor" in caplog.text.lower()


# ---------------------------------------------------------------------------
# _similar_cases_block
# ---------------------------------------------------------------------------


def test_similar_cases_block_vide_sans_cas(tmp_path: Path) -> None:
    agent_cls = _make_agent_class(tmp_path / "profiles.json")
    assert agent_cls._similar_cases_block({}) == ""
    assert agent_cls._similar_cases_block({"similar_cases": []}) == ""


def test_similar_cases_block_limite_a_trois_et_tronque_a_200(tmp_path: Path) -> None:
    agent_cls = _make_agent_class(tmp_path / "profiles.json")
    long_text = "x" * 250
    cases = [{"text": f"cas-{i}"} for i in range(5)]
    cases[0]["text"] = long_text
    result = agent_cls._similar_cases_block({"similar_cases": cases})
    assert result.startswith("\nCas similaires récents :\n")
    # Seuls les 3 premiers apparaissent.
    assert "cas-3" not in result
    assert "cas-4" not in result
    assert "cas-1" in result and "cas-2" in result
    # Troncature à 200 caractères du premier élément.
    assert ("x" * 200) in result
    assert ("x" * 201) not in result


def test_similar_cases_block_texte_absent_devient_chaine_vide(tmp_path: Path) -> None:
    agent_cls = _make_agent_class(tmp_path / "profiles.json")
    result = agent_cls._similar_cases_block({"similar_cases": [{}]})
    assert result == "\nCas similaires récents :\n  - "


# ---------------------------------------------------------------------------
# _render_context_blocks
# ---------------------------------------------------------------------------


def test_render_context_blocks_sans_outils_ni_cas(tmp_path: Path) -> None:
    agent_cls = _make_agent_class(tmp_path / "profiles.json")
    tools_desc, similar_text = agent_cls._render_context_blocks({}, {})
    assert tools_desc == ""
    assert similar_text == ""


def test_render_context_blocks_avec_outils(tmp_path: Path) -> None:
    agent_cls = _make_agent_class(tmp_path / "profiles.json")
    profile = {"tools": {"grep": "recherche de texte", "ls": "liste un dossier"}}
    tools_desc, _ = agent_cls._render_context_blocks(profile, {})
    assert tools_desc.startswith("\nOutils disponibles :\n")
    assert "grep: recherche de texte" in tools_desc
    assert "ls: liste un dossier" in tools_desc


# ---------------------------------------------------------------------------
# _toolbox_block
# ---------------------------------------------------------------------------


def test_toolbox_block_vide_si_toolbox_absente(tmp_path: Path) -> None:
    agent = _make_agent_class(tmp_path / "profiles.json")()
    assert agent._toolbox_block() == ""


def test_toolbox_block_vide_si_description_vide(tmp_path: Path) -> None:
    agent = _make_agent_class(tmp_path / "profiles.json")()
    agent.inject_toolbox(_FakeToolbox(description=""))
    assert agent._toolbox_block() == ""


def test_toolbox_block_prefixe_d_un_saut_de_ligne(tmp_path: Path) -> None:
    agent = _make_agent_class(tmp_path / "profiles.json")()
    agent.inject_toolbox(_FakeToolbox(description="outils : grep, ls"))
    assert agent._toolbox_block() == "\noutils : grep, ls"


# ---------------------------------------------------------------------------
# _tool_results_section
# ---------------------------------------------------------------------------


def test_tool_results_section_vide_sans_resultats(tmp_path: Path) -> None:
    agent = _make_agent_class(tmp_path / "profiles.json")()
    agent.inject_toolbox(_FakeToolbox(results_text="section"))
    assert agent._tool_results_section({}) == ""


def test_tool_results_section_vide_si_toolbox_sans_render(tmp_path: Path) -> None:
    agent = _make_agent_class(tmp_path / "profiles.json")()
    agent.inject_toolbox(_BareToolbox())
    assert agent._tool_results_section({"tool_results": {"grep": {}}}) == ""


def test_tool_results_section_delegue_a_la_toolbox(tmp_path: Path) -> None:
    agent = _make_agent_class(tmp_path / "profiles.json")()
    toolbox = _FakeToolbox(results_text="[Résultats outils]\ngrep -> 3 occurrences")
    agent.inject_toolbox(toolbox)
    context = {"tool_results": {"grep": {"count": 3}}}
    assert agent._tool_results_section(context) == "[Résultats outils]\ngrep -> 3 occurrences"
    assert toolbox.last_results == {"grep": {"count": 3}}


def test_tool_results_section_render_falsy_devient_chaine_vide(tmp_path: Path) -> None:
    agent = _make_agent_class(tmp_path / "profiles.json")()
    agent.inject_toolbox(_FakeToolbox(results_text=""))
    assert agent._tool_results_section({"tool_results": {"grep": {}}}) == ""


# ---------------------------------------------------------------------------
# _compose_parts / _profile_prompt / _build_messages
# ---------------------------------------------------------------------------


def test_compose_parts_utilise_le_system_prompt_du_profil(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "profiles.json"
    _write_profiles(path, {"dev": {"system_prompt": "Tu es dev.", "tools": {"grep": "recherche"}}})
    agent = _make_agent_class(path)()
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    system, tools_desc, similar_text, toolbox_desc = agent._compose_parts("dev", {})
    assert system == "Tu es dev."
    assert "grep: recherche" in tools_desc
    assert similar_text == ""
    assert toolbox_desc == ""


def test_compose_parts_default_prompt_remplace_le_profil(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "profiles.json"
    _write_profiles(path, {"cyber": {"system_prompt": "Ignoré."}})
    agent = _make_agent_class(path)()
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    system, *_ = agent._compose_parts("cyber", {}, default_prompt="Tu es un expert cyber.")
    assert system == "Tu es un expert cyber."


def test_profile_prompt_assemble_toutes_les_sections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "profiles.json"
    _write_profiles(path, {"dev": {"system_prompt": "Tu es dev.", "tools": {"grep": "recherche"}}})
    agent = _make_agent_class(path)()
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    context = {"recent_tasks": ["tâche A"], "similar_cases": [{"text": "cas 1"}]}
    prompt = agent._profile_prompt("dev", "corriger le bug", context)
    assert prompt.startswith("Tu es dev.\nOutils disponibles :\n  - grep: recherche")
    assert "Contexte récent : ['tâche A']" in prompt
    assert "Cas similaires récents :\n  - cas 1" in prompt
    assert prompt.endswith("Tâche : corriger le bug")


def test_build_messages_separe_system_et_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "profiles.json"
    _write_profiles(path, {"dev": {"system_prompt": "  Tu es dev.  ", "tools": {"grep": "recherche"}}})
    agent = _make_agent_class(path)()
    agent.inject_toolbox(_FakeToolbox(description="toolbox dispo"))
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    context = {"recent_tasks": ["tâche A"], "tool_results": {"grep": {}}}
    system, user = agent._build_messages("dev", "corriger le bug", context)
    assert system == "Tu es dev."
    assert "Outils disponibles :\n  - grep: recherche" in user
    assert "toolbox dispo" in user
    assert "Contexte récent : ['tâche A']" in user
    assert user.endswith("Tâche : corriger le bug")


def test_build_messages_default_prompt_et_contexte_minimal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "profiles.json"
    _write_profiles(path, {"cyber": {}})
    agent = _make_agent_class(path)()
    monkeypatch.setattr("services.skills.get_enabled_skills_text", lambda: "")
    system, user = agent._build_messages("cyber", "scanner le réseau", {}, default_prompt="Tu es cyber.")
    assert system == "Tu es cyber."
    # ``_build_messages`` fait un ``.strip()`` final : le saut de ligne de
    # tête (absence de tools_desc/toolbox_desc) disparaît.
    assert user == "Contexte récent : []\nTâche : scanner le réseau"


# ---------------------------------------------------------------------------
# _detect_skill_from_code
# ---------------------------------------------------------------------------


def test_detect_skill_from_code_aucune_fence_retourne_none() -> None:
    assert BaseAgent._detect_skill_from_code("juste du texte") is None


def test_detect_skill_from_code_powershell() -> None:
    result = BaseAgent._detect_skill_from_code("voici :\n```powershell\nGet-Process\n```")
    assert result == "script.ps1"


def test_detect_skill_from_code_bash() -> None:
    result = BaseAgent._detect_skill_from_code("voici :\n```bash\nls -la\n```")
    assert result == "script.sh"


def test_detect_skill_from_code_python() -> None:
    result = BaseAgent._detect_skill_from_code("voici :\n```python\nprint('ok')\n```")
    assert result == "script.py"


def test_detect_skill_from_code_priorite_powershell_sur_bash_et_python() -> None:
    """Ordre d'insertion du mapping = ordre de priorité (powershell > bash > python)."""
    mixed = "```python\nprint(1)\n```\n```bash\nls\n```\n```powershell\nGet-Process\n```"
    assert BaseAgent._detect_skill_from_code(mixed) == "script.ps1"


def test_detect_skill_from_code_priorite_bash_sur_python() -> None:
    mixed = "```python\nprint(1)\n```\n```bash\nls\n```"
    assert BaseAgent._detect_skill_from_code(mixed) == "script.sh"


def test_detect_skill_from_code_prefix_personnalise() -> None:
    result = BaseAgent._detect_skill_from_code("```bash\nls\n```", prefix="dev_script")
    assert result == "dev_script.sh"


# ---------------------------------------------------------------------------
# Intégration légère : run() d'une sous-classe concrète
# ---------------------------------------------------------------------------


def test_sous_classe_concrete_implemente_run(tmp_path: Path) -> None:
    agent = _make_agent_class(tmp_path / "profiles.json")()
    result = agent.run("tâche", "modele-x", {})
    assert result == {"response": "ok", "agent": "concrete", "model": "modele-x"}


def test_run_abstrait_leve_notimplementederror_si_appele_directement(tmp_path: Path) -> None:
    """Corps de la méthode abstraite : filet si une sous-classe appelle ``super().run()``."""
    agent = _make_agent_class(tmp_path / "profiles.json")()
    with pytest.raises(NotImplementedError):
        BaseAgent.run(agent, "tâche", "modele-x", {})
