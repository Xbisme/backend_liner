"""Library test fixtures — two authenticated users + a mocked Jamendo upstream."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from apps.catalog.services import jamendo as jamendo_mod
from apps.library.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _local_cache(settings: Any) -> Any:
    """In-process cache (no live Redis); cleared around each test for isolation."""
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def app_key() -> str:
    return settings.X_APP_KEY


def _client_for(app_key: str, user: User) -> APIClient:
    client = APIClient()
    client.credentials(
        HTTP_X_APP_KEY=app_key,
        HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}",
    )
    return client


@pytest.fixture
def make_client(app_key: str) -> Callable[[User], APIClient]:
    """Return a factory building an app-key + Bearer client for a given user."""
    return lambda user: _client_for(app_key, user)


@pytest.fixture
def user_a(db: Any) -> User:
    return UserFactory()


@pytest.fixture
def user_b(db: Any) -> User:
    return UserFactory()


@pytest.fixture
def client_a(make_client: Callable[[User], APIClient], user_a: User) -> APIClient:
    return make_client(user_a)


@pytest.fixture
def client_b(make_client: Callable[[User], APIClient], user_b: User) -> APIClient:
    return make_client(user_b)


class JamendoMock:
    """MockTransport-backed httpx client; records calls and scripts replies."""

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

    def respond_tracks(self, tracks: list[dict[str, Any]]) -> None:
        """Reply with a Jamendo-style success payload carrying ``tracks`` as results."""
        self._handler = lambda r: httpx.Response(
            200, json={"headers": {"status": "success"}, "results": tracks}
        )

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


def jamendo_track(track_id: str, **overrides: Any) -> dict[str, Any]:
    """A minimal raw Jamendo track record for mocking hydration."""
    base = {
        "id": track_id,
        "name": f"Track {track_id}",
        "artist_id": "9",
        "artist_name": "Mock Artist",
        "album_id": "5",
        "album_name": "Mock Album",
        "duration": 200,
        "image": f"https://img/{track_id}.jpg",
        "audio": f"https://audio/{track_id}.mp3",
        "license_ccurl": "http://creativecommons.org/licenses/by-nc-sa/3.0/",
    }
    base.update(overrides)
    return base
