"""Tests LogService."""
import json
import os
import sys

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

import config.constants as constants
import services.log as log_module
from services.log import LogService


class TestLogService:
    def test_log_creates_entry(self, tmpdir):
        log_path = os.path.join(tmpdir, "api.json")
        _orig = log_module.LOG_PATH
        try:
            log_module.LOG_PATH = log_path
            svc = LogService()
            svc.log("INFO", "test message")
            with open(log_path) as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["level"] == "INFO"
            assert data[0]["message"] == "test message"
        finally:
            log_module.LOG_PATH = _orig

    def test_log_appends(self, tmpdir):
        log_path = os.path.join(tmpdir, "api.json")
        _orig = log_module.LOG_PATH
        try:
            log_module.LOG_PATH = log_path
            svc = LogService()
            svc.log("INFO", "first")
            svc.log("WARN", "second")
            with open(log_path) as f:
                data = json.load(f)
            assert len(data) == 2
            assert data[1]["level"] == "WARN"
        finally:
            log_module.LOG_PATH = _orig

    def test_log_trims_at_500(self, tmpdir):
        log_path = os.path.join(tmpdir, "api.json")
        _orig = log_module.LOG_PATH
        try:
            log_module.LOG_PATH = log_path
            svc = LogService()
            for i in range(constants.MAX_LOG_ENTRIES + 10):
                svc.log("INFO", f"msg{i}")
            with open(log_path) as f:
                data = json.load(f)
            assert len(data) == constants.MAX_LOG_ENTRIES
            assert data[0]["message"] == "msg10"
        finally:
            log_module.LOG_PATH = _orig


class TestRootLogging:
    def test_configure_adds_handler_idempotent(self):
        import logging
        saved = logging.getLogger().handlers[:]
        try:
            logging.getLogger().handlers.clear()
            log_module._configure_root_logging()
            assert logging.getLogger().handlers
            count = len(logging.getLogger().handlers)
            log_module._configure_root_logging()
            assert len(logging.getLogger().handlers) == count
        finally:
            logging.getLogger().handlers[:] = saved
