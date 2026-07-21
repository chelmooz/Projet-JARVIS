"""Tests ProcessManager — port 11436 orphan."""
import os
import sys
from unittest.mock import MagicMock, patch

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from services.launcher import ProcessManager
from services.port_manager import kill_existing


class TestProcessManager:
    def test_start_ollama_calls_kill_existing(self):
        with patch("services.launcher.kill_existing") as mock_kill, \
             patch("services.launcher.get_ollama_path", return_value="/fake/ollama"), \
             patch("services.launcher.subprocess.Popen") as mock_popen, \
             patch("services.launcher._open_log"):
            mock_popen.return_value.poll.return_value = None
            mock_popen.return_value = MagicMock()

            pm = ProcessManager()
            pm.start_ollama()

            mock_kill.assert_called_once_with("ollama", 11436)

    def test_start_ollama_kill_not_called_if_no_ollama(self):
        with patch("services.launcher.kill_existing") as mock_kill, \
             patch("services.launcher.get_ollama_path", return_value=None):

            pm = ProcessManager()
            pm.start_ollama()

            mock_kill.assert_not_called()

    def test_kill_existing_does_not_crash_on_free_port(self):
        kill_existing("test", 19999)

    def test_kill_existing_valid_port(self):
        with patch("services.port_manager.SYSTEM", "linux"), \
             patch("services.port_manager.subprocess.run") as mock_run:
            kill_existing("ollama", 11436)
            mock_run.assert_called_once_with(["fuser", "-k", "11436/tcp"], capture_output=True, timeout=5)
