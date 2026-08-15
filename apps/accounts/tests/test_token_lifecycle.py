"""Token lifecycle hardening — per-session logout + idempotency (BE-004 US2)."""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def _register(api: APIClient, email: str = "a@b.com") -> dict[str, Any]:
    return api.post(
        "/auth/register",
        {"email": email, "password": "password8", "display_name": "Bao"},
        format="json",
    ).json()


def _login(api: APIClient, email: str = "a@b.com") -> dict[str, Any]:
    return api.post(
        "/auth/login",
        {"email": email, "password": "password8"},
        format="json",
    ).json()


def test_logout_is_per_session(api: APIClient, bearer: Any) -> None:
    device1 = _register(api)
    device2 = _login(api)  # second session for the same user

    client = bearer(APIClient(), device1["access_token"])
    resp = client.post(
        "/auth/logout", {"refresh_token": device1["refresh_token"]}, format="json"
    )
    assert resp.status_code == 204

    # Device 1's refresh is revoked...
    r1 = api.post(
        "/auth/refresh", {"refresh_token": device1["refresh_token"]}, format="json"
    )
    assert r1.status_code == 401
    assert r1.json()["error"]["code"] == "TOKEN_INVALID"

    # ...but device 2 stays logged in.
    r2 = api.post(
        "/auth/refresh", {"refresh_token": device2["refresh_token"]}, format="json"
    )
    assert r2.status_code == 200


def test_logout_without_token_is_idempotent(api: APIClient, bearer: Any) -> None:
    tokens = _register(api)
    client = bearer(APIClient(), tokens["access_token"])

    resp = client.post("/auth/logout", {}, format="json")
    assert resp.status_code == 204

    # Nothing was revoked — the refresh token still works.
    after = api.post(
        "/auth/refresh", {"refresh_token": tokens["refresh_token"]}, format="json"
    )
    assert after.status_code == 200


def test_logout_with_invalid_token_is_idempotent(api: APIClient, bearer: Any) -> None:
    tokens = _register(api)
    client = bearer(APIClient(), tokens["access_token"])

    resp = client.post("/auth/logout", {"refresh_token": "garbage"}, format="json")
    assert resp.status_code == 204  # never 500 / 401 (FR-011)
