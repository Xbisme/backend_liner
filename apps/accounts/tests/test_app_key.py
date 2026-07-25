import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_missing_app_key_rejected():
    client = APIClient()
    resp = client.post(
        "/auth/login", {"email": "a@b.com", "password": "x"}, format="json"
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_APP_KEY"


def test_wrong_app_key_rejected():
    client = APIClient()
    client.credentials(HTTP_X_APP_KEY="totally-wrong")
    resp = client.post(
        "/auth/login", {"email": "a@b.com", "password": "x"}, format="json"
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_APP_KEY"


def test_valid_app_key_passes_gate(api):
    # Gate passes → we reach the view and get a *credentials* error, not app-key.
    resp = api.post(
        "/auth/login", {"email": "none@none.com", "password": "nope"}, format="json"
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"
