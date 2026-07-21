"""Tests for services/sanitize.py — TDD par l'exemple."""
import base64

import pytest

import services.sanitize as sanitize


class TestCleanText:
    def test_preserves_normal(self):
        assert sanitize.clean_text("hello world") == "hello world"

    def test_truncates_long(self):
        long = "a" * 30_000
        result = sanitize.clean_text(long, max_len=100)
        assert len(result) == 100

    def test_non_string_returns_empty(self):
        assert sanitize.clean_text(None) == ""
        assert sanitize.clean_text(42) == ""

    def test_replaces_non_printable(self):
        result = sanitize.clean_text("a\x00b\x01c")
        assert result == "a\ufffdb\ufffdc"


class TestSafeModelName:
    def test_preserves_normal(self):
        assert sanitize.safe_model_name("llama3:8b") == "llama3:8b"

    def test_too_long_returns_empty(self):
        assert sanitize.safe_model_name("a" * 200) == ""

    def test_strips_special_chars(self):
        assert sanitize.safe_model_name("hello@world!") == "helloworld"

    def test_empty_returns_empty(self):
        assert sanitize.safe_model_name("") == ""


class TestSafePathSegment:
    def test_preserves_normal(self):
        assert sanitize.safe_path_segment("logs/app.log") == "logs/app.log"

    @pytest.mark.parametrize("segment", ["../secret.txt", "..\\secret.txt"])
    def test_removes_dotdot(self, segment):
        assert "/" not in sanitize.safe_path_segment(segment) and "\\" not in segment.replace("..\\", "")

    def test_removes_null_bytes(self):
        result = sanitize.safe_path_segment("file\x00.txt")
        assert "\0" not in result

    def test_empty_returns_empty(self):
        assert sanitize.safe_path_segment("") == ""

    def test_truncates_long(self):
        result = sanitize.safe_path_segment("a" * 2000)
        assert len(result) == 1024


class TestValidateBase64Image:
    def test_valid_returns_true(self):
        valid = base64.b64encode(b"hello").decode()
        assert sanitize.validate_base64_image(valid) is True

    def test_empty_returns_false(self):
        assert sanitize.validate_base64_image("") is False

    @pytest.mark.parametrize("bad", [None, 123, 4.5])
    def test_non_string_returns_false(self, bad):
        assert sanitize.validate_base64_image(bad) is False

    def test_oversized_returns_false(self):
        valid = base64.b64encode(b"x" * 10).decode()
        assert sanitize.validate_base64_image(valid, max_mb=0) is False

    def test_invalid_base64_returns_false(self):
        assert sanitize.validate_base64_image("!!!not-base64!!!") is False


class TestStripDataUri:
    def test_strips_data_prefix(self):
        assert sanitize.strip_data_uri("data:image/png;base64,iVBOR") == "iVBOR"

    def test_no_prefix_returns_original(self):
        assert sanitize.strip_data_uri("plaintext") == "plaintext"

    def test_empty_returns_empty(self):
        assert sanitize.strip_data_uri("") == ""

    def test_non_string_returns_empty(self):
        assert sanitize.strip_data_uri(None) == ""


class TestSafeJsonKey:
    def test_preserves_alphanumeric_and_underscore(self):
        assert sanitize.safe_json_key("abc123_") == "abc123_"

    def test_strips_special_chars(self):
        assert sanitize.safe_json_key("hello-world!@#") == "helloworld"
