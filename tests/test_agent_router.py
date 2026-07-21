"""Tests RED → GREEN pour AgentRouter."""
from services.router import AgentRouter


def test_select_agent_returns_cyber_for_security_task():
    router = AgentRouter()
    agent = router.select_agent("Analyse ce log de firewall")
    assert agent == "cyber"


def test_select_agent_returns_dev_for_code_task():
    router = AgentRouter()
    agent = router.select_agent("Ecris un script python pour parser ce fichier")
    assert agent == "dev"


def test_select_agent_returns_network_for_network_task():
    router = AgentRouter()
    agent = router.select_agent("Verifie la connectivite du vlan 10")
    assert agent == "network"


def test_select_agent_returns_hardware_for_hardware_task():
    router = AgentRouter()
    agent = router.select_agent("La ram est defectueuse, le cpu surchauffe")
    assert agent == "hardware"


def test_select_agent_returns_fallback_for_empty_task():
    router = AgentRouter()
    agent = router.select_agent("")
    assert agent == "dev"


def test_select_agent_uses_prefix():
    router = AgentRouter()
    agent = router.select_agent("@vision decris cette image")
    assert agent == "vision"


def test_select_agent_accepts_task_object():
    from models import Task
    router = AgentRouter()
    agent = router.select_agent(Task(text="Analyse ce log de securite"))
    assert agent == "cyber"
