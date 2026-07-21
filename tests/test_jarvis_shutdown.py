"""Tests jarvis — handler SIGINT/SIGTERM fait un arret propre (audit DevOps 4.3).

Avant : `os._exit(0)` court-circuitait le cleanup (flush/atexit/uvicorn) et,
si `pm.stop_all()` levait, le handler plantait silencieusement.
Apres : `_shutdown` appelle stop_all puis `sys.exit(0)` dans un `finally`.
"""
import signal
from unittest import mock

import jarvis


def test_shutdown_calls_stop_all_and_exits_cleanly():
    pm = mock.MagicMock()
    with __import__("pytest").raises(SystemExit) as exc:
        jarvis._shutdown(pm, signal.SIGINT, None)
    assert exc.value.code == 0
    pm.stop_all.assert_called_once()


def test_shutdown_exits_even_if_stop_all_fails():
    pm = mock.MagicMock()
    pm.stop_all.side_effect = RuntimeError("boom")
    with __import__("pytest").raises(SystemExit) as exc:
        jarvis._shutdown(pm, signal.SIGTERM, None)
    assert exc.value.code == 0
