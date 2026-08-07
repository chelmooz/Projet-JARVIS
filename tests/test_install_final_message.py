"""TDD — print_final() ne doit pas afficher `bin\\ollama.exe serve` quand seul un
Ollama système (PATH) a été détecté par setup_ollama() (pas de binaire portable
copié dans bin\\).

Bug réel constaté sur déploiement Windows réel (H:\\Projet-JARVIS) : PC avec Ollama
système installé -> setup_ollama() dit "deja installe" et s'arrête -> print_final()
affichait quand même "1. Lancer Ollama : bin\\ollama.exe serve" -> Start-Process
échouait ("fichier introuvable") car bin\\ollama.exe n'existait pas.
"""
import importlib.util
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_install_module():
    """Charge scripts/install.py comme module (ce n'est pas un package)."""
    path = os.path.join(PROJECT_ROOT, "scripts", "install.py")
    spec = importlib.util.spec_from_file_location("jarvis_install_script", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["jarvis_install_script"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_print_final_no_portable_binary_does_not_reference_bin_ollama(capsys, monkeypatch):
    mod = _load_install_module()
    monkeypatch.setattr(mod, "SYSTEM", "windows")

    mod.print_final(ollama_portable_path=None)

    out = capsys.readouterr().out
    assert "bin\\ollama.exe serve" not in out
    assert "ollama serve" in out


def test_print_final_with_portable_binary_references_bin_ollama(capsys, monkeypatch):
    mod = _load_install_module()
    monkeypatch.setattr(mod, "SYSTEM", "windows")

    mod.print_final(ollama_portable_path="H:\\Projet-JARVIS\\bin\\ollama.exe")

    out = capsys.readouterr().out
    assert "bin\\ollama.exe serve" in out
