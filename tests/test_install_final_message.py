"""TDD — print_final() ne doit pas afficher `bin\\ollama.exe serve` quand aucun
binaire portable n'est présent sur la clé (installation système interdite).

Bug réel constaté sur déploiement Windows réel (H:\\Projet-JARVIS) : PC avec Ollama
système installé -> setup_ollama() disait "deja installe" et s'arrêtait ->
print_final() affichait quand même "1. Lancer Ollama : bin\\ollama.exe serve" ->
Start-Process échouait ("fichier introuvable") car bin\\ollama.exe n'existait pas.

Depuis le 08/08/2026 : 100 % portable. setup_ollama() pose le binaire portable
SUR la clé (bin\\) et n'invite plus jamais à une installation système
(irm/install.sh supprimés). print_final() renvoie au 1er lancement de JARVIS.bat
(qui télécharge via ensure_ollama_binary) — et ne mentionne plus "ollama serve".
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
    # 100 % portable : plus aucune référence à un Ollama système.
    assert "ollama serve" not in out
    # On renvoie au filet de sécurité : JARVIS.bat télécharge au 1er lancement.
    assert "JARVIS.bat" in out
    assert "jamais sur l'ordi" in out


def test_print_final_with_portable_binary_references_bin_ollama(capsys, monkeypatch):
    mod = _load_install_module()
    monkeypatch.setattr(mod, "SYSTEM", "windows")

    mod.print_final(ollama_portable_path="H:\\Projet-JARVIS\\bin\\ollama.exe")

    out = capsys.readouterr().out
    assert "bin\\ollama.exe serve" in out
    assert "portable, sur la cle" in out
