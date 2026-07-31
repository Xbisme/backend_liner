"""Sentry wiring + PII/secret scrubbing (Constitution IX, BE-004 US3).

``init_sentry`` is a no-op without a DSN, so dev/test stay offline (FR-012).
``_scrub`` is a belt-and-suspenders companion to ``core.logging`` redaction: it
strips sensitive keys from every event before it leaves the process (FR-013).
"""

from __future__ import annotations

from typing import Any

# Keys whose values must never reach Sentry (mirrors core.logging redaction).
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "authorization",
        "x-app-key",
        "x_app_key",
        "client_id",
        "secret",
        "secret_key",
    }
)

_REDACTED = "***"


def _scrub_mapping(data: Any) -> Any:
    """Recursively redact sensitive keys in dicts/lists; other values untouched."""
    if isinstance(data, dict):
        return {
            key: (
                _REDACTED if key.lower() in _SENSITIVE_KEYS else _scrub_mapping(value)
            )
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [_scrub_mapping(item) for item in data]
    return data


def _scrub(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sentry ``before_send`` hook: redact sensitive data across the event."""
    for section in ("request", "extra", "contexts"):
        if section in event:
            event[section] = _scrub_mapping(event[section])
    # Request headers are the most common secret carrier (Authorization, X-App-Key).
    request = event.get("request")
    if isinstance(request, dict) and isinstance(request.get("headers"), dict):
        request["headers"] = _scrub_mapping(request["headers"])
    return event


def init_sentry(dsn: str) -> None:
    """Initialize Sentry when a DSN is configured; no-op otherwise (FR-012)."""
    if not dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration()],
        send_default_pii=False,
        before_send=_scrub,  # type: ignore[arg-type]  # our loose event dict typing
    )
