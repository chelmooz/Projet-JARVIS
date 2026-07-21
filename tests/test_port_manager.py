"""Tests port_manager — kill exact sur le port (audit DevOps 1.2).

Le port doit être matché EXACTEMENT (après le dernier ':'), pas en
substring : sinon `:1143` matcherait `:11436` et `:80` matcherait `:8080`,
risquant de tuer un processus légitime de l'utilisateur.
"""
from unittest import mock

from services import port_manager as pm

NETSTAT_SAMPLE = """
  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:11436         0.0.0.0:0              LISTENING       1234
  TCP    127.0.0.1:8080        127.0.0.1:5000         ESTABLISHED     5678
  TCP    [::1]:11436           [::1]:12345            TIME_WAIT       0
  UDP    0.0.0.0:11436         *:*                                    9999
  TCP    0.0.0.0:18080         0.0.0.0:0              LISTENING       4321
"""


def test_extract_port_ipv4():
    assert pm._extract_port("0.0.0.0:11436") == 11436


def test_extract_port_ipv6():
    assert pm._extract_port("[::1]:11436") == 11436


def test_extract_port_no_colon():
    assert pm._extract_port("LOCAL") is None


def test_extract_port_pid_suffix_ignored():
    # ss/netstat n'ajoutent pas de suffixe, mais on reste robuste.
    assert pm._extract_port("0.0.0.0:11436") == 11436


def test_kill_windows_exact_port_only():
    """Port 11436 ne doit tuer QUE les PIDs 1234 et 9999 (pas 5678/4321)."""
    run = mock.patch("services.port_manager.subprocess.run").start()
    mock.patch("services.port_manager.os.getpid", return_value=1).start()
    run.return_value = mock.Mock(stdout=NETSTAT_SAMPLE.encode("utf-8"), stderr=b"")

    pm._kill_windows(11436)

    killed = [
        c.args[0]
        for c in run.call_args_list
        if isinstance(c.args[0], list) and c.args[0][0] == "taskkill"
    ]
    joined = " ".join(str(a) for a in killed)
    assert "1234" in joined
    assert "9999" in joined
    assert "5678" not in joined
    assert "4321" not in joined
    mock.patch.stopall()
