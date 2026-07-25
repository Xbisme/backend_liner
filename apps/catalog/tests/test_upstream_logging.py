"""Upstream Jamendo failures are logged with diagnostic context (BE-004 FR-014)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest

from apps.catalog.services import catalog
from core.exceptions import AppError


@pytest.mark.django_db
def test_timeout_logs_entity_and_latency(
    jamendo: Any, caplog: pytest.LogCaptureFixture
) -> None:
    jamendo.raise_timeout()
    with caplog.at_level(logging.WARNING, logger="apps.catalog.services.jamendo"):
        with pytest.raises(AppError):
            catalog.trending()
    msg = caplog.text
    assert "Jamendo upstream error on tracks" in msg
    assert "latency=" in msg
    # The client_id-bearing URL and raw body must never be logged.
    assert "client_id" not in msg


@pytest.mark.django_db
def test_http_status_error_logs_status(
    jamendo: Any, caplog: pytest.LogCaptureFixture
) -> None:
    jamendo.respond(lambda r: httpx.Response(503, json={}))
    with caplog.at_level(logging.WARNING, logger="apps.catalog.services.jamendo"):
        with pytest.raises(AppError):
            catalog.trending()
    assert "status=503" in caplog.text
