"""Unit tests for rate-limit envelope + fail-open/closed behavior (BE-004)."""

from __future__ import annotations

from typing import Any

from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.exceptions import Throttled
from rest_framework.test import APIRequestFactory

from core.errors import ErrorCode
from core.exceptions import api_exception_handler
from core.throttling import (
    AuthRateThrottle,
    CatalogRateThrottle,
    HistoryRateThrottle,
    UserWriteRateThrottle,
)

factory = APIRequestFactory()


class _BoomCache:
    """A cache whose reads/writes always fail (simulates Redis outage)."""

    def get(self, *args: Any, **kwargs: Any) -> Any:
        raise RedisConnectionError("store down")

    def set(self, *args: Any, **kwargs: Any) -> Any:
        raise RedisConnectionError("store down")


class _AuthedUser:
    is_authenticated = True
    pk = 1


# --- Envelope mapping (FR-004) ----------------------------------------------


def test_throttled_maps_to_rate_limited_with_retry_after() -> None:
    resp = api_exception_handler(Throttled(wait=42), {})
    assert resp.status_code == 429
    assert resp.data["error"]["code"] == ErrorCode.RATE_LIMITED
    assert resp["Retry-After"] == "42"


def test_throttled_without_wait_has_no_retry_after() -> None:
    exc = Throttled()
    exc.wait = None
    resp = api_exception_handler(exc, {})
    assert resp.status_code == 429
    assert resp.data["error"]["code"] == ErrorCode.RATE_LIMITED
    assert "Retry-After" not in resp


# --- Fail-open (functional) / fail-closed (auth) on store outage (FR-006a) ---


def test_auth_throttle_fails_closed_on_cache_error() -> None:
    throttle = AuthRateThrottle()
    throttle.cache = _BoomCache()
    request = factory.post("/auth/login")
    assert throttle.allow_request(request, None) is False


def test_catalog_throttle_fails_open_on_cache_error() -> None:
    throttle = CatalogRateThrottle()
    throttle.cache = _BoomCache()
    request = factory.get("/catalog/trending")
    assert throttle.allow_request(request, None) is True


def test_user_write_throttle_fails_open_on_cache_error() -> None:
    throttle = UserWriteRateThrottle()
    throttle.cache = _BoomCache()
    request = factory.post("/me/playlists")
    request.user = _AuthedUser()
    assert throttle.allow_request(request, None) is True


def test_history_throttle_fails_open_on_cache_error() -> None:
    throttle = HistoryRateThrottle()
    throttle.cache = _BoomCache()
    request = factory.post("/me/history")
    request.user = _AuthedUser()
    assert throttle.allow_request(request, None) is True
