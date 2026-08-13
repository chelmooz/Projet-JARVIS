from models import Task
from services.router import (
    DEFAULT_FALLBACK,
    AgentRouter,
    AgentRoutingConfig,
    load_routing_config,
)


def test_select_prefix() -> None:
    cfg = AgentRoutingConfig(prefix_map={"@cyber": "cyber"}, keyword_map={}, fallback="dev")
    r = AgentRouter(cfg)
    assert r.select_agent("@cyber scan ports") == "cyber"


def test_select_keyword() -> None:
    cfg = AgentRoutingConfig(
        prefix_map={},
        keyword_map={"cyber": ["security", "firewall"], "dev": ["code", "python"]},
        fallback="dev",
    )
    r = AgentRouter(cfg)
    assert r.select_agent("check the firewall security") == "cyber"
    assert r.select_agent("write python code") == "dev"


def test_select_default_empty() -> None:
    cfg = AgentRoutingConfig(prefix_map={}, keyword_map={}, fallback="dev")
    r = AgentRouter(cfg)
    assert r.select_agent("") == "dev"
    assert r.select_agent("   ") == "dev"


def test_select_fallback_no_match() -> None:
    cfg = AgentRoutingConfig(prefix_map={}, keyword_map={"cyber": ["security"]}, fallback="dev")
    r = AgentRouter(cfg)
    assert r.select_agent("hello world") == "dev"


def test_select_ambiguous_tie() -> None:
    cfg = AgentRoutingConfig(prefix_map={}, keyword_map={"cyber": ["x"], "dev": ["x"]}, fallback="dev")
    r = AgentRouter(cfg)
    assert r.select_agent("x") in ("cyber", "dev")


def test_select_with_task_object() -> None:
    cfg = AgentRoutingConfig(prefix_map={}, keyword_map={"cyber": ["security"]}, fallback="dev")
    r = AgentRouter(cfg)
    assert r.select_agent(Task(task="security audit")) == "cyber"


def test_load_missing_returns_default() -> None:
    cfg = load_routing_config("nonexistent_path.yaml")
    assert cfg.prefix_map == {}
    assert cfg.keyword_map == {}
    assert cfg.fallback == DEFAULT_FALLBACK


def test_load_valid(tmp_path) -> None:
    p = tmp_path / "routing.yaml"
    p.write_text("prefix_map:\n  '@cyber': cyber\nkeyword_map:\n  dev:\n    - code\nfallback: orchestrateur\n")
    cfg = load_routing_config(p)
    assert cfg.prefix_map == {"@cyber": "cyber"}
    assert cfg.keyword_map == {"dev": ["code"]}
    assert cfg.fallback == "orchestrateur"
