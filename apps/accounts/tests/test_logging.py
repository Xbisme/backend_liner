from core.logging import SensitiveDataFilter


def _redact(message: str) -> str:
    import logging

    record = logging.LogRecord("t", logging.INFO, __file__, 1, message, None, None)
    SensitiveDataFilter().filter(record)
    return record.getMessage()


def test_password_is_redacted():
    out = _redact("login password=SuperSecret123 ok")
    assert "SuperSecret123" not in out
    assert "***" in out


def test_tokens_and_app_key_redacted():
    out = _redact(
        "headers authorization=Bearerabc x-app-key=topsecret refresh_token=rrr"
    )
    assert "topsecret" not in out
    assert "rrr" not in out
    assert out.count("***") >= 2
