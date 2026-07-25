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
       