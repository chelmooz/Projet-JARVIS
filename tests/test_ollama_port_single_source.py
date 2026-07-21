"""Tests — OLLAMA_PORT source unique (audit DevOps 2.4 / backlog #7).

Avant : `jarvis.py` et `controllers/context.py` redefinissaient OLLAMA_PORT.
Apres : tous lisent `config.paths.OLLAMA_PORT` (source unique).
Verifie aussi que les adapters utilisent la source unique.
"""
import controllers.context as ctx
import jarvis
import services.adapters.ollama_adapter as oa_mod
from config.paths import OLLAMA_PORT as PATHS_PORT


def test_ollama_port_single_source():
    assert PATHS_PORT == 11436
    assert jarvis.OLLAMA_PORT is PATHS_PORT
    assert ctx.OLLAMA_PORT is PATHS_PORT
    assert oa_mod.OLLAMA_PORT is PATHS_PORT
