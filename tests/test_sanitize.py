import pytest

from services import sanitize


# --- clean_text ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hello", "hello"),
        ("a\x00b", "a\ufffdb"),
        ("café ☕", "café ☕"),  # unicode préservé (>127)
        ("tab\there", "tab\there"),  # \t (0x09) fait partie de string.printable -> conservé
    ],
)
def test_clean_text_chars(text: str, expected: str) -> None:
    assert sanitize.clean_text(text) == expected


def test_clean_text_non_str_returns_empty() -> None:
    assert sanitize.clean_text(None) == ""  # type: ignore[arg-type]
    assert sanitize.clean_text(123) == ""  # type: ignore[arg-type]


def test_clean_text_truncation() -> None:
    assert sanitize.clean_text("x" * 50, max_len=10) == "x" * 10
    assert len(sanitize.clean_text("x" * 1000, max_len=20)) == 20


# --- safe_model_name ----------------------------------------------------------
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Qwen2.5-7B", "Qwen2.5-7B"),
        ("hf.co/Model:Q4_K_M", "hf.co/Model:Q4_K_M"),
        ("Bad Model!", "BadModel"),
        ("", ""),
    ],
)
def test_safe_model_name(name: str, expected: str) -> None:
    assert sanitize.safe_model_name(name) == expected


def test_safe_model_name_too_long() -> None:
    assert sanitize.safe_model_name("a" * (sanitize.MAX_MODEL_NAME + 1)) == ""


# --- safe_path_segment --------------------------------------------------------
@pytest.mark.parametrize(
    ("segment", "expected"),
    [
        ("", ""),
        ("..", ""),
        ("a/../b", "a/b"),
        ("a\\..\\b", "a\\b"),
        ("....//", ""),  # point fixe : la traversée ne réapparaît pas
        ("foo\x00bar", "foobar"),
        ("foo\\0bar", "foobar"),
        ("normal_segment", "normal_segment"),
    ],
)
def test_safe_path_segment(segment: str, expected: str) -> None:
    assert sanitize.safe_path_segment(segment) == expected


def test_safe_path_segment_truncation() -> None:
    long = "a" * (sanitize.MAX_PATH_LEN + 10)
    assert len(sanitize.safe_path_segment(long)) == sanitize.MAX_PATH_LEN


# --- validate_base64_image ----------------------------------------------------
def test_validate_base64_invalid_inputs() -> None:
    assert sanitize.validate_base64_image("") is False
    assert sanitize.validate_base64_image(None) is False  # type: ignore[arg-type]
    assert sanitize.validate_base64_image("not base64 !!!") is False


def test_validate_base64_valid_and_uri() -> None:
    assert sanitize.validate_base64_image("AA==") is True  # 1 octet
    assert sanitize.validate_base64_image("data:image/png;base64,AA==") is True


def test_validate_base64_too_large() -> None:
    assert sanitize.validate_base64_image("AA==", max_mb=0) is False


# --- strip_data_uri -----------------------------------------------------------
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("", ""),
        (None, ""),  # type: ignore[arg-type]
        ("iVBORw0KGgo=", "iVBORw0KGgo="),
        ("data:image/png;base64,iVBORw0KGgo=", "iVBORw0KGgo="),
    ],
)
def test_strip_data_uri(data: str | None, expected: str) -> None:
    assert sanitize.strip_data_uri(data) == expected  # type: ignore[arg-type]


# --- safe_json_key ------------------------------------------------------------
@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("valid_key1", "valid_key1"),
        ("bad key!", "badkey"),
        ("", ""),
    ],
)
def test_safe_json_key(key: str, expected: str) -> None:
    assert sanitize.safe_json_key(key) == expected


# --- scrub (PII) --------------------------------------------------------------
def test_scrub_empty_and_non_str() -> None:
    assert sanitize.scrub("") == ""
    assert sanitize.scrub(None) == ""  # type: ignore[arg-type]


def test_scrub_email_and_token() -> None:
    text = "Contact alice@example.com token sk-ABCD1234abcd5678EFGH9012ijkl3456MNOP"
    result = sanitize.scrub(text)
    assert "alice@example.com" not in result
    assert "sk-ABCD" not in result
    assert "[REDACTED]" in result


def test_scrub_ips() -> None:
    assert "[REDACTED]" in sanitize.scrub("ip 192.168.1.1")
    assert "[REDACTED]" in sanitize.scrub("ip 127.0.0.1")
    assert "[REDACTED]" in sanitize.scrub("ip 10.0.0.5")
    assert "[REDACTED]" in sanitize.scrub("ip 172.16.5.5")
    assert "8.8.8.8" in sanitize.scrub("ip 8.8.8.8")  # publique conservée
    assert "172.32.0.1" in sanitize.scrub("ip 172.32.0.1")  # hors plage RFC1918
    assert "999.999.999.999" in sanitize.scrub("ip 999.999.999.999")  # format invalide conservé
    assert "1.2.3" in sanitize.scrub("ip 1.2.3")  # 3 octets conservé


def test_scrub_aws_github_jwt_pem() -> None:
    text = (
        "aws AKIAIOSFODNN7EXAMPLE "
        "ghp_0123456789abcdefABCDEF0123456789abcdef "
        "jwt eyJhbGciOiJIUzI1Ni.eyJzdWIiOiIxMjM0NTY3ODkw.eyJpYXQiOjE1MTY "
        "pem -----BEGIN PRIVATE KEY-----"
    )
    result = sanitize.scrub(text)
    assert "AKIAIOSFODNN7EXAMPLE" not in result
    assert "ghp_0123456789" not in result
    assert "eyJhbGciOiJIUzI1Ni" not in result
    assert "BEGIN PRIVATE KEY" not in result


def test_scrub_password_assignment() -> None:
    result = sanitize.scrub("password=supersecret123")
    assert "supersecret123" not in result
    assert "[REDACTED]" in result
