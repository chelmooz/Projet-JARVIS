"""Vérifie la suppression du code mort MT-D4 — API typée config/__init__.py + shim kill_coding.

Le module racine ``config/__init__.py`` exposait une API typée (dataclasses,
getters, reload) qui n'était référencée nulle part (vérifié par grep exhaustif :
production, scripts, tests). ``services/kill_coding.py`` est un shim de réexport
créé lors du renommage Kill Coding → Analysis, jamais importé (les routes
importent ``Analyzer`` depuis ``services.analysis`` directement).
"""

from __future__ import annotations

import importlib.util

DEAD_ROOT_CONFIG_SYMBOLS = (
    "get_agent_profiles",
    "get_model_preferences",
    "get_cyber_workflows",
    "get_components",
    "reload",
    "ConfigError",
    "AgentProfileConfig",
    "ModelPreference",
    "CyberWorkflow",
    "ComponentAsset",
    "ComponentsConfig",
)


def test_config_root_package_does_not_expose_dead_api() -> None:
    """Le package racine ``config`` ne doit plus exposer l'API typée morte."""
    import config

    exported = {name for name in DEAD_ROOT_CONFIG_SYMBOLS if hasattr(config, name)}
    assert exported == set(), f"Symboles morts encore exposés par config : {exported}"


def test_config_root_all_does_not_list_dead_symbols() -> None:
    import config

    exported = set(getattr(config, "__all__", []))
    assert not exported.intersection(DEAD_ROOT_CONFIG_SYMBOLS), (
        f"__all__ de config contient encore : {exported.intersection(DEAD_ROOT_CONFIG_SYMBOLS)}"
    )


def test_kill_coding_shim_module_removed() -> None:
    assert importlib.util.find_spec("services.kill_coding") is None, (
        "services/kill_coding.py (shim de réexport) doit être supprimé"
    )
