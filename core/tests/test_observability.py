"""Sentry scrubbing + DSN-gated init (BE-004 US3, FR-012/FR-013)."""

from __future__ import annotations

from typing import Any

import sentry_sdk

from core.observability import _scrub, init_sentry


def test_scrub_redacts_request_headers_and_body() -> None:
    event = {
        "request": {
            "headers": {"Authorization": "Bearer secret", "X-App-Key": "k"},
            "data": {"password": "hunter2", "email": "a@b.com"},
        },
        "extra": {"refresh_token": "rt", "note": "ok"},
    }
    scrubbed = _scrub(event)
    assert scrubbed["request"]["headers"]["Authorization"] == "***"
    assert scrubbed["request"]["headers"]["X-App-Key"] == "***"
    assert scrubbed["request"]["data"]["password"] == "***"
    assert scrubbed["request"]["data"]["email"] == "a@b.com"  # not sensitive
    assert scrubbed["extra"]["refresh_token"] == "***"
    assert scrubbed["extra"]["note"] == "ok"


def test_init_sentry_noop_without_dsn(monkeypatch: Any) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: calls.append(kw))
    init_sentry("")
    assert calls == []


def test_init_sentry_wires_scrub_when_dsn_present(monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: calls.append(kw))
    init_sentry("https://key@example.ingest.sentry.io/1")
    assert len(calls) == 1
    assert calls[0]["before_send"] is _scrub
    assert calls[0]["send_default_pii"] is False
