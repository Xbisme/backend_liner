import pytest
from rest_framework.test import APIClient

from apps.accounts.models import SocialIdentity, User
from apps.accounts.tests.factories import SocialIdentityFactory

pytestmark = pytest.mark.django_db


def _register(api, email="a@b.com"):
    return api.post(
        "/auth/register",
        {"email": email, "password": "password8", "display_name": "Bao"},
        format="json",
    ).json()


def test_get_me_returns_own_profile(api, bearer):
    tokens = _register(api)
    client = bearer(APIClient(), tokens["access_token"])
    resp = client.get("/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "a@b.com"
    assert "password" not in resp.json()
    assert "is_staff" not in resp.json()


def test_get_me_missing_token_unauthorized(api):
    resp = api.get("/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED_USER"


def test_me_is_scoped_to_token_user(api, bearer):
    # Two users; each token only ever yields its own profile (no IDOR surface).
    t1 = _register(api, "a@b.com")
    t2 = _register(api, "c@d.com")
    c1 = bearer(APIClient(), t1["access_token"])
    c2 = bearer(APIClient(), t2["access_token"])
    assert c1.get("/me").json()["email"] == "a@b.com"
    assert c2.get("/me").json()["email"] == "c@d.com"


def test_delete_me_cascades_and_invalidates(api, bearer):
    tokens = _register(api)
    user = User.objects.get(email="a@b.com")
    SocialIdentityFactory(user=user, subject_id="s-1")
    client = bearer(APIClient(), tokens["access_token"])

    resp = client.delete("/me")
    assert resp.status_code == 204
    assert not User.objects.filter(email="a@b.com").exists()
    assert not SocialIdentity.objects.filter(subject_id="s-1").exists()

    # Old access token no longer works.
    assert client.get("/me").status_code == 401
    # Old credentials cannot log in.
    login = api.post(
        "/auth/login", {"email": "a@b.com", "password": "password8"}, format="json"
    )
    assert login.status_code == 401
