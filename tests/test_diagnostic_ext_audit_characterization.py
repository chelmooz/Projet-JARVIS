from __future__ import annotations

from services.diagnostic_ext.audit import audit_log


def test_audit_log_without_service_is_noop() -> None:
    audit_log(None, "INFO", "message")


def test_audit_log_delegates_to_service() -> None:
    class Service:
        def __init__(self):
            self.calls = []

        def log(self, level, message):
            self.calls.append((level, message))

    service = Service()
    audit_log(service, "WARN", "message")
    assert service.calls == [("WARN", "message")]


def test_audit_log_is_fail_safe_when_service_raises() -> None:
    class Broken:
        def log(self, level, message):
            raise RuntimeError("broken")

    audit_log(Broken(), "ERROR", "message")
