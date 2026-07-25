from datetime import timedelta

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def _register(api, email="a@b.com"):
    return api.post(
        "/auth/register",
        {"email": email, "password": "password8", "display_name": "Bao"},
        format="json",
    ).json()


def test_refresh_returns_new_tokens(api):
    tokens = _register(api)
    resp = api.post(
        "/auth/refresh", {"refresh_token": tokens["refresh_token"]}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]
    assert resp.json()["refresh_token"] != tokens["refresh_token"]  # rotated


def test_reused_refresh_token_is_rejected(api):
    tokens = _register(api)
    api.post("/auth/refresh", {"refresh_token": tokens["refresh_token"]}, format="json")
    # Reuse the now-blacklisted (rotated) refresh token.
    resp = api.post(
        "/auth/refresh", {"refresh_token": tokens["refresh_token"]}, format="json"
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "TOKEN_INVALID"


def test_expired_access_token_reports_token_expired(api, bearer):
    _register(api)
    user = User.objects.get(email="a@b.com")
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=-timedelta(seconds=1))  # already expired
    client = bearer(APIClient(), str(token))
    resp = client.get("/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_garbage_token_reports_token_invalid(api, bearer):
    _register(api)
    client = bearer(APIClient(), "not-a-real-token")
    resp = client.get("/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "TOKEN_INVALID"


def test_logout_revokes_refresh(api, bearer):
    tokens = _register(api)
    client = bearer(APIClient(), tokens["access_token"])
    resp = client.post(
        "/auth/logout", {"refresh_token": tokens["refresh_token"]}, format="json"
    )
    assert resp.status_code == 204
    after = api.post(
        "/auth/refresh", {"refresh_token": tokens["refresh_token"]}, format="json"
    )
    assert after.status_code == 401
    assert after.json()["error"]["code"] == "TOKEN_INVALID"
