"""Tests agents — GenericAgent, CyberAgent, VisionAgent."""
import json
from unittest.mock import MagicMock, patch

import pytest

from agents.base import BaseAgent
from agents.cyber import CyberAgent
from agents.generic import GenericAgent
from agents.vision import VisionAgent

# ─── BaseAgent ─────────────────────────────────────────────────────────────────

class TestBaseAgent:

    def test_is_abstract(self):
        with pytest.raises(TypeError):
            BaseAgent()

    def test_inject_toolbox(self):
        class ConcreteAgent(BaseAgent):
            def run(self, task, model, context):
                return {}
        agent = ConcreteAgent()
        assert agent.toolbox is None
        agent.inject_toolbox("fake_toolbox")
        assert agent.toolbox == "fake_toolbox"

    def test_build_messages_with_profile(self, tmp_path):
        profile_file = tmp_path / "profiles.json"
        profile_file.write_text(json.dumps({
            "profiles": {
                "techlead": {
                    "system_prompt": "Tu es un tech lead.",
                    "tools": {"python": "executer du code"}
                }
            }
        }))
        class ConcreteAgent(BaseAgent):
            def run(self, task, model, context):
                return {}
        agent = ConcreteAgent()
        with patch("agents.base.PROFILES_FILE", str(profile_file)):
            system, user = agent._build_messages("techlead", "fix bug", {})
            assert "tech lead" in system.lower()
            assert "fix bug" in user

    def test_build_messages_with_similar_cases(self):
        class ConcreteAgent(BaseAgent):
            def run(self, task, model, context):
                return {}
        agent = ConcreteAgent()
        ctx = {"similar_cases": [{"text": "previous case"}]}
        with patch.object(agent, "_load_profile", return_value={}):
            system, user = agent._build_messages("techlead", "task", ctx)
            assert "previous case" in user

    def test_enabled_skills_injected_in_system_prompt(self, tmp_path, monkeypatch):
        cfg = tmp_path / "skills.json"
        cfg.write_text(json.dumps({
            "version": "1.0",
            "skills": [
                {"id": "s1", "enabled": True, "prompt": "Reponds en francais."},
                {"id": "s2", "enabled": False, "prompt": "Reponds en anglais."},
            ],
        }), encoding="utf-8")
        monkeypatch.setattr("services.skills.SKILLS_CONFIG", str(cfg))

        class ConcreteAgent(BaseAgent):
            def run(self, task, model, context):
                return {}

        agent = ConcreteAgent()
        with patch.object(agent, "_load_profile", return_value={}):
            system, user = agent._build_messages("techlead", "task", {})
            assert "[Skills actifs]" in system
            assert "Reponds en francais." in system
            assert "Reponds en anglais." not in system

    def test_detect_skill_from_code_powershell(self):
        assert BaseAgent._detect_skill_from_code("```powershell\nGet-Process\n```", prefix="audit") == "audit.ps1"

    def test_detect_skill_from_code_bash(self):
        assert BaseAgent._detect_skill_from_code("```bash\nls\n```", prefix="audit") == "audit.sh"

    def test_detect_skill_from_code_python(self):
        assert BaseAgent._detect_skill_from_code("```python\nprint()\n```", prefix="audit") == "audit.py"

    def test_detect_skill_from_code_none(self):
        assert BaseAgent._detect_skill_from_code("plain text", prefix="audit") is None


# ─── GenericAgent ──────────────────────────────────────────────────────────────

class TestGenericAgent:

    def test_init_defaults(self):
        model = MagicMock()
        memory = MagicMock()
        agent = GenericAgent(model, memory)
        assert agent._profile_key == "techlead"
        assert agent._domain_prompt == "Tu es un assistant technique."

    def test_init_custom(self):
        model = MagicMock()
        memory = MagicMock()
        agent = GenericAgent(model, memory, profile_key="devops",
                             domain_prompt="Tu es DevOps.")
        assert agent._profile_key == "devops"
        assert "DevOps" in agent._domain_prompt

    def test_run_returns_dict_with_keys(self):
        model = MagicMock()
        # L'API de production : inference.query() renvoie une chaîne (le texte de réponse)
        model.query.return_value = "done"
        model.get_active_backend.return_value = "ollama"
        memory = MagicMock()
        agent = GenericAgent(model, memory)
        with patch.object(agent, "_build_messages", return_value=("system", "user")):
            result = agent.run("fix bug", "phi4-mini:latest", {})
        assert result["agent"] == "techlead"
        assert result["model"] == "phi4-mini:latest"
        assert result["backend"] == "ollama"
        assert result["response"] == "done"

    def test_run_delegates_to_model_query(self):
        model = MagicMock()
        model.query.return_value = "ok"
        memory = MagicMock()
        agent = GenericAgent(model, memory)
        with patch.object(agent, "_build_messages", return_value=("sys", "usr")):
            agent.run("task", "llava:8b", {})
        model.query.assert_called_with("usr", "llava:8b", system="sys")

    def test_run_suggests_skill(self):
        model = MagicMock()
        model.query.return_value = "```python\nx=1\n```"
        model.get_active_backend.return_value = "ollama"
        memory = MagicMock()
        agent = GenericAgent(model, memory, profile_key="dev")
        with patch.object(agent, "_build_messages", return_value=("sys", "usr")):
            result = agent.run("write script", "phi4-mini:latest", {})
        assert result["suggested_skill"] == "dev_script.py"


# ─── CyberAgent ────────────────────────────────────────────────────────────────

class TestCyberAgent:

    def test_init_loads_workflows(self, tmp_path):
        wf_path = tmp_path / "cyber_workflows.json"
        wf_path.write_text(json.dumps({
            "workflows": {
                "LOG_ANALYSIS": {"name": "Analyse de logs", "steps": ["collect", "parse"]}
            }
        }))
        model = MagicMock()
        memory = MagicMock()
        # CyberAgent charge ses workflows via CYBER_WORKFLOWS_CONFIG (SPoT config.paths) :
        # on le patch pour pointer sur le fichier temporaire de test.
        with patch("agents.cyber.CYBER_WORKFLOWS_CONFIG", str(wf_path)):
            agent = CyberAgent(model, memory)
        assert "LOG_ANALYSIS" in agent.get_workflows()

    def test_init_handles_missing_workflows(self):
        model = MagicMock()
        memory = MagicMock()
        with patch("agents.cyber.CYBER_WORKFLOWS_CONFIG", "/nonexistent/path.json"):
            agent = CyberAgent(model, memory)
        assert agent.get_workflows() == {}

    def test_run_returns_cyber_keys(self):
        model = MagicMock()
        # inference.query() renvoie une chaîne en production
        model.query.return_value = "analyse ok"
        model.get_active_backend.return_value = "ollama"
        memory = MagicMock()
        agent = CyberAgent(model, memory)
        with patch.object(agent, "_build_cyber_messages", return_value=("sys", "usr")):
            result = agent.run("analyse log", "phi4-mini:latest", {})
        assert result["agent"] == "datasecu"
        assert "analyse" in result["response"]

    def test_build_cyber_messages_includes_workflow(self):
        model = MagicMock()
        memory = MagicMock()
        agent = CyberAgent(model, memory)
        workflow = {"name": "Log Analysis", "steps": ["step1"]}
        with patch.object(agent, "_build_messages", return_value=("sys", "")):
            system, user = agent._build_cyber_messages("log analysis", {}, workflow)
            assert "Log Analysis" in user

    def test_build_cyber_messages_includes_similar_cases(self):
        model = MagicMock()
        memory = MagicMock()
        agent = CyberAgent(model, memory)
        ctx = {"similar_cases": [{"text": "previous breach"}]}
        with patch.object(agent, "_build_messages", return_value=("sys", "")):
            _, user = agent._build_cyber_messages("analyse incident", ctx)
            assert "previous breach" in user

    def test_match_workflow_cisa(self):
        model = MagicMock()
        memory = MagicMock()
        agent = CyberAgent(model, memory)
        agent._workflows = {"CISA_KNOWN_EXPLOITED_VULNS": {"name": "CISA KEV"}}
        match = agent._match_workflow("check cisa known exploited vulnerabilities")
        assert match is not None
        assert match["name"] == "CISA KEV"

    def test_match_workflow_returns_none(self):
        model = MagicMock()
        memory = MagicMock()
        agent = CyberAgent(model, memory)
        match = agent._match_workflow("hello world")
        assert match is None

    def test_suggest_skill_from_workflow(self):
        model = MagicMock()
        memory = MagicMock()
        agent = CyberAgent(model, memory)
        skill = agent._suggest_skill("", {"suggested_skill": "run_audit.ps1"})
        assert skill == "run_audit.ps1"

    def test_suggest_skill_fallback(self):
        model = MagicMock()
        memory = MagicMock()
        agent = CyberAgent(model, memory)
        skill = agent._suggest_skill("```bash\nls\n```")
        assert skill == "security_audit.sh"


# ─── VisionAgent ───────────────────────────────────────────────────────────────

class TestVisionAgent:

    def test_init(self):
        model = MagicMock()
        memory = MagicMock()
        agent = VisionAgent(model, memory)
        assert agent._profile_key == "designer"

    def test_run_multimodal_with_image(self):
        model = MagicMock()
        model.query_multimodal.return_value = {"content": "image description", "model": "llava", "role": "assistant"}
        memory = MagicMock()
        agent = VisionAgent(model, memory)
        result = agent.run("describe", "llava:8b", {"image": "base64data"})
        model.query_multimodal.assert_called_with("llava:8b", "describe", "base64data")
        assert result["response"] == "image description"

    def test_run_textual_without_image(self):
        model = MagicMock()
        model.query.return_value = "text response"
        memory = MagicMock()
        agent = VisionAgent(model, memory)
        with patch.object(agent, "_build_messages", return_value=("sys", "usr")):
            result = agent.run("write code", "phi4-mini:latest", {})
        assert result["response"] == "text response"
        assert result["suggested_skill"] is None

    def test_run_returns_correct_keys(self):
        model = MagicMock()
        model.query_multimodal.return_value = {"content": "desc", "model": "llava", "role": "assistant"}
        memory = MagicMock()
        agent = VisionAgent(model, memory)
        result = agent.run("describe", "llava:8b", {"image": "img"})
        assert set(result.keys()) == {"agent", "model", "backend", "response", "suggested_skill"}


# ─── Repro du bug B1 (Tech Lead) : default_prompt non déclaré ──────────────────
# Les tests ci-dessus patchent _build_messages et masquent le TypeError réel
# déclenché en conditions réelles (un vrai modèle tourne). Ces tests l'exercent
# SANS monkey-patch, donc ils échouent tant que base.py n'accepte pas
# `default_prompt`.


class _FakeModel:
    def __init__(self):
        self.calls = []

    def query(self, user, model, system=""):
        self.calls.append((user, model, system))
        return "ok"

    def query_multimodal(self, model, task, image):
        return {"content": "ok", "model": model, "role": "assistant"}

    def get_active_backend(self):
        return "ollama"


class TestDefaultPromptRealRun:
    def test_generic_run_applies_domain_prompt(self):
        model = _FakeModel()
        memory = MagicMock()
        agent = GenericAgent(model, memory, profile_key="techlead",
                             domain_prompt="Tu es un assistant technique.")
        result = agent.run("ping", "qwen2.5:7b", {})
        assert result["response"] == "ok"
        assert "assistant technique" in result["model"] or "assistant technique" in model.calls[0][2]

    def test_cyber_run_applies_domain_prompt(self):
        model = _FakeModel()
        memory = MagicMock()
        agent = CyberAgent(model, memory)
        result = agent.run("analyse les logs", "qwen2.5:7b", {})
        assert result["response"] == "ok"

    def test_vision_textual_run_applies_domain_prompt(self):
        model = _FakeModel()
        memory = MagicMock()
        agent = VisionAgent(model, memory)
        result = agent.run("decris", "qwen2.5:7b", {})
        assert result["response"] == "ok"

    def test_build_messages_accepts_default_prompt(self):
        class ConcreteAgent(BaseAgent):
            def run(self, task, model, context):
                return {}
        agent = ConcreteAgent()
        with patch.object(agent, "_load_profile", return_value={}):
            system, _ = agent._build_messages("techlead", "t", {},
                                              default_prompt="prompt par defaut")
        assert "prompt par defaut" in system

    def test_profile_prompt_accepts_default_prompt(self):
        class ConcreteAgent(BaseAgent):
            def run(self, task, model, context):
                return {}
        agent = ConcreteAgent()
        with patch.object(agent, "_load_profile", return_value={}):
            system = agent._profile_prompt("techlead", "t", {},
                                           default_prompt="prompt par defaut")
        assert "prompt par defaut" in system
