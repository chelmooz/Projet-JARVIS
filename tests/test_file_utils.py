"""Tests for services/file_utils.py — TDD par l'exemple."""
import json

import pytest

import services.file_utils as fu


class TestReadJson:
    def test_valid_file_returns_parsed_dict(self, tmp_path):
        d = tmp_path / "data.json"
        d.write_text('{"key": "val"}', encoding="utf-8")
        assert fu.read_json(str(d)) == {"key": "val"}

    def test_missing_file_returns_default_empty_dict(self, tmp_path):
        p = tmp_path / "nonexistent.json"
        assert fu.read_json(str(p)) == {}

    def test_missing_file_returns_custom_default(self, tmp_path):
        p = tmp_path / "missing.json"
        assert fu.read_json(str(p), default={"fallback": True}) == {"fallback": True}

    def test_malformed_json_returns_default(self, tmp_path):
        d = tmp_path / "bad.json"
        d.write_text("{invalid", encoding="utf-8")
        assert fu.read_json(str(d)) == {}


class TestWriteJsonAtomic:
    def test_writes_file_correctly(self, tmp_path):
        p = tmp_path / "out.json"
        fu.write_json_atomic(str(p), {"a": 1})
        assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1}

    def test_content_matches_written(self, tmp_path):
        p = tmp_path / "out.json"
        data = {"list": [1, 2, 3], "nested": {"x": "y"}}
        fu.write_json_atomic(str(p), data)
        assert json.loads(p.read_text(encoding="utf-8")) == data

    def test_atomic_creates_tmp_then_replaces(self, tmp_path):
        p = tmp_path / "atomic.json"
        fu.write_json_atomic(str(p), {"done": True})
        assert p.exists()
        # tmp file should be gone after replace
        assert not (tmp_path / "atomic.json.tmp").exists()


class TestRetry:
    def test_succeeds_first_time(self):
        calls = []

        @fu.retry(max_attempts=3, delay=0.01)
        def ok():
            calls.append(1)
            return 42

        assert ok() == 42
        assert len(calls) == 1

    def test_retries_on_failure_then_succeeds(self):
        n = 0

        @fu.retry(max_attempts=3, delay=0.01)
        def flaky():
            nonlocal n
            n += 1
            if n < 2:
                raise ValueError("not yet")
            return "ok"

        assert flaky() == "ok"
        assert n == 2

    def test_all_retries_exhausted_raises(self):
        @fu.retry(max_attempts=2, delay=0.01)
        def fails():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            fails()
