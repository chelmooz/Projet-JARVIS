"""Tests TDD — AgentRouter : config YAML source de vérité (Phase 7 witr).

RED → GREEN : le routage lit ``config/agent_routing.yaml`` (ROUTING_CONFIG),
plus aucun mapping hardcodé. Dégradation gracieuse si le YAML manque.
"""
import pytest
import yaml

from services.router import AgentRouter, AgentRoutingConfig, load_routing_config


def _write_yaml(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)


class TestLoadRoutingConfig:

    def test_load_from_yaml(self, tmp_path):
        yaml_path = tmp_path / "routing.yaml"
        _write_yaml(yaml_path, {
            "prefix_map": {"@ghost": "ghost"},
            "keyword_map": {"ghost": ["zork"]},
            "fallback": "ghost",
        })
        config = load_routing_config(yaml_path)
        assert config.prefix_map == {"@ghost": "ghost"}
        assert config.keyword_map == {"ghost": ["zork"]}
        assert config.fallback == "ghost"

    def test_missing_yaml_degrades_gracefully(self, tmp_path):
        config = load_routing_config(tmp_path / "absent.yaml")
        assert config.prefix_map == {}
        assert config.keyword_map == {}
        assert config.fallback == "dev"

    def test_corrupt_yaml_degrades_gracefully(self, tmp_path):
        yaml_path = tmp_path / "corrupt.yaml"
        yaml_path.write_text("{{{{ not yaml", encoding="utf-8")
        config = load_routing_config(yaml_path)
        assert config.prefix_map == {}
        assert config.fallback == "dev"

    def test_partial_yaml_defaults_fallback_dev(self, tmp_path):
        yaml_path = tmp_path / "partial.yaml"
        _write_yaml(yaml_path, {"keyword_map": {"cyber": ["scan"]}})
        config = load_routing_config(yaml_path)
        assert config.keyword_map == {"cyber": ["scan"]}
        assert config.fallback == "dev"


class TestAgentRouterConfigDriven:

    def test_keywords_from_yaml_are_used(self, tmp_path):
        yaml_path = tmp_path / "routing.yaml"
        _write_yaml(yaml_path, {
            "keyword_map": {"ghost": ["zork"]},
            "fallback": "dev",
        })
        router = AgentRouter(load_routing_config(yaml_path))
        assert router.select_agent("analyse zork 42") == "ghost"

    def test_prefix_from_yaml_are_used(self, tmp_path):
        yaml_path = tmp_path / "routing.yaml"
        _write_yaml(yaml_path, {
            "prefix_map": {"@ghost": "ghost"},
            "fallback": "dev",
        })
        router = AgentRouter(load_routing_config(yaml_path))
        assert router.select_agent("@ghost mission") == "ghost"

    def test_fallback_from_yaml(self, tmp_path):
        yaml_path = tmp_path / "routing.yaml"
        _write_yaml(yaml_path, {"fallback": "cyber"})
        router = AgentRouter(load_routing_config(yaml_path))
        assert router.select_agent("bonjour") == "cyber"

    def test_missing_yaml_router_does_not_crash(self, tmp_path):
        config = load_routing_config(tmp_path / "absent.yaml")
        router = AgentRouter(config)
        assert router.select_agent("bonjour") == "dev"

    def test_default_config_loads_real_yaml(self):
        router = AgentRouter()
        # Le YAML réel déclare les mots-clés witr hardware (Phase 7)
        assert router.select_agent("pourquoi le processus explorer tourne") == "hardware"
        assert router.select_agent("why is port 8080 running") == "hardware"

    def test_injected_config_without_disk(self):
        config = AgentRoutingConfig(
            prefix_map={"@cyber": "cyber"},
            keyword_map={"cyber": ["zork"]},
            fallback="dev",
        )
        router = AgentRouter(config)
        assert router.select_agent("zork attack") == "cyber"
        assert router.select_agent("@cyber scan") == "cyber"
        assert router.select_agent("salut") == "dev"

    def test_config_is_immutable(self):
        config = AgentRoutingConfig(prefix_map={}, keyword_map={}, fallback="dev")
        with pytest.raises((AttributeError, TypeError)):
            config.fallback = "cyber"
