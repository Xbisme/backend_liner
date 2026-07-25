"""Auth endpoints are throttled per-IP to blunt brute-force (BE-004 US1)."""

from __future__ import annotations

from typing import Any

import pytest
from django.core.cache import cache
from rest_framework.settings import api_settings
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _isolate_cache(settings: Any) -> Any:
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    cache.clear()
    yield
    cache.clear()


def _set_auth_rate(settings: Any, rate: str) -> None:
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
            "auth": rate,
        },
    }
    api_settings.reload()


def _login(api: APIClient) -> int:
    return api.post(
        "/auth/login",
        {"email": "x@y.z", "password": "wrongpass1"},
        format="json",
    ).status_code


@pytest.mark.django_db
def test_login_throttled_after_limit(api: APIClient, settings: Any) -> None:
    _set_auth_rate(settings, "3/min")
    codes = [_login(api) for _ in range(5)]
    # First 3 reach business logic (not throttled); the rest are rate-limited.
    assert 429 not in codes[:3]
    assert codes[3] == 429 and codes[4] == 429


@pytest.mark.django_db
def test_throttled_response_uses_rate_limited_envelope(
    api: APIClient, settings: Any
) -> None:
    _set_auth_rate(settings, "1/min")
    _login(api)
    resp = api.post(
        "/auth/login", {"email": "x@y.z", "password": "wrongpass1"}, format="json"
    )
    assert resp.status_code == 429
    assert resp.data["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in resp
