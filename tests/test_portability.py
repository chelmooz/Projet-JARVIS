"""
Tests de portabilité (Phase 6 du ROADMAP)
Vérifie que les chemins d'installation sont corrects selon l'OS.
"""
import os
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_ollama_installer_linux_path():
    """Vérifie que _install_linux_tar retourne bien un chemin dans BIN_LINUX."""
    
    # On mocke toutes les dépendances externes pour isoler la logique de la fonction
    with patch('services.ollama_installer.platform.machine', return_value='x86_64'), \
         patch('services.ollama_installer.os.makedirs'), \
         patch('services.ollama_installer._download_file'), \
         patch('services.ollama_installer._verify_ollama_binary', return_value=True), \
         patch('services.ollama_installer._extract_tar_zst'), \
         patch('services.ollama_installer.shutil.copy'), \
         patch('services.ollama_installer.os.chmod'), \
         patch('services.ollama_installer.os.listdir', return_value=[]), \
         patch('services.ollama_installer.os.path.exists', return_value=True), \
         patch('services.ollama_installer.shutil.rmtree'), \
         patch('services.ollama_installer.os.remove'), \
         patch('services.ollama_installer.BASE_DIR', '/fake/base'), \
         patch('services.ollama_installer.BIN_LINUX', '/fake/base/bin/linux'):
        
        # On importe la fonction APRÈS le patch pour qu'elle utilise les mocks
        from services.ollama_installer import _install_linux_tar
        
        mock_log = MagicMock()
        result = _install_linux_tar(mock_log)
        
        # Le résultat doit être le chemin dans BIN_LINUX, pas BIN_DIR
        # On utilise os.path.join pour que le séparateur corresponde à l'OS du test (Windows ou Linux)
        expected = os.path.join('/fake/base/bin/linux', 'ollama')
        assert result == expected, \
            f"Le chemin de retour doit être dans BIN_LINUX. Obtenu : {result}, Attendu : {expected}"


def test_ollama_installer_source_code_uses_bin_linux():
    """Vérification statique complémentaire : le code source utilise bien BIN_LINUX."""
    installer_path = Path("services/ollama_installer.py")
    content = installer_path.read_text(encoding="utf-8")
    
    assert "BIN_LINUX" in content, "BIN_LINUX doit être importé/utilisé dans le fichier"
    assert 'os.path.join(BIN_LINUX, "ollama")' in content, \
        "Le chemin de destination du binaire doit utiliser BIN_LINUX"
    assert 'result = os.path.join(BIN_LINUX, "ollama")' in content, \
        "La variable 'result' retournée doit pointer vers BIN_LINUX/ollama"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])