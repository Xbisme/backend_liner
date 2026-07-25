"""Logging filter that redacts secrets from log records (Principle IX/FR-020)."""

from __future__ import annotations

import logging
import re

# Matches `key = value` / `key: value` / `key"="value` for known secret keys.
_SECRET_RE = re.compile(
    r"(?i)\b(password|token|authorization|secret|id_token|refresh_token|"
    r"access_token|x[-_]app[-_]key|client_id)\b(\"?\s*[:=]\s*\"?)([^\s\"',}]+)"
)


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            redacted = _SECRET_RE.sub(r"\1\2***", message)
            if redacted != message:
                record.msg = redacted
                record.args = ()
        except Exception:  # pragma: no cover - never break logging
            pass
        return True
