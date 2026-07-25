from __future__ import annotations

import pytest
from django.conf import settings
from rest_framework.test import APIClient


@pytest.fixture
def app_key() -> str:
    return settings.X_APP_KEY


@pytest.fixture
def api(app_key: str) -> APIClient:
    """Client that always sends a valid X-App-Key."""
    client = APIClient()
    client.credentials(HTTP_X_APP_KEY=app_key)
    return client


@pytest.fixture
def bearer(app_key):
    """Return a helper that sets app-key + bearer on a client."""

    def _apply(client: APIClient, access_token: str) -> APIClient:
        client.credentials(
            HTTP_X_APP_KEY=app_key,
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        return client

    return _apply


@pytest.fixture
def registered(api):
    """Register a user; return (tokens_payload, response)."""

    def _register(email="a@b.com", password="password8", display_name="Bao"):
        resp = api.post(
            "/auth/register",
            {"email": email, "password": password, "display_name": display_name},
            format="json",
        )
        return resp

    return _register
