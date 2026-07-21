"""Tests — SYSTEM source unique (audit DevOps 3.3).

Avant : `services/system.py` redefinissait SYSTEM.
Apres : importe `config.paths.SYSTEM` (source unique).
"""
import config.paths
import services.system as system


def test_system_source_unique():
    assert system.SYSTEM is config.paths.SYSTEM
    assert system.SYSTEM == "windows" or system.SYSTEM in ("linux", "darwin")
