"""Catalog test fixtures — a mocked Jamendo upstream (no live network)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.catalog.services import jamendo as jamendo_mod


@pytest.fixture
def app_key() -> str:
    return settings.X_APP_KEY


@pytest.fixture
def api(app_key: str) -> APIClient:
    """Client that always sends a valid X-App-Key (Layer-1)."""
    client = APIClient()
    client.credentials(HTTP_X_APP_KEY=app_key)
    return client


@pytest.fixture(autouse=True)
def _local_cache(settings: Any) -> Any:
    """Use an in-process cache for tests (no live Redis) and isolate state."""
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    cache.clear()
    yield
    cache.clear()


class JamendoMock:
    """Installs a MockTransport-backed httpx client and records call count."""

    def __init__(self) -> None:
        self.calls = 0
        self._handler: Callable[[httpx.Request], httpx.Response] = (
            lambda r: httpx.Response(
                200, json={"headers": {"status": "success"}, "results": []}
            )
        )

    def _dispatch(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return self._handler(request)

    def respond(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self._handler = handler

    def respond_json(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._handler = lambda r: httpx.Response(status_code, json=payload)

    def raise_timeout(self) -> None:
        def _boom(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timeout", request=request)

        self._handler = _boom


@pytest.fixture
def jamendo(monkeypatch: pytest.MonkeyPatch) -> Any:
    mock = JamendoMock()
    client = httpx.Client(
        transport=httpx.MockTransport(mock._dispatch),
        base_url=settings.JAMENDO_API_BASE_URL,
    )
    monkeypatch.setattr(jamendo_mod, "_HTTP", client)
    yield mock
    client.close()
