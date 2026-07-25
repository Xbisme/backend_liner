import pytest

pytestmark = pytest.mark.django_db


def test_register_returns_201_with_token_payload(api):
    resp = api.post(
        "/auth/register",
        {"email": "a@b.com", "password": "password8", "display_name": "Bao"},
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == {"access_token", "refresh_token", "expires_in", "user"}
    assert body["user"]["email"] == "a@b.com"
    assert body["user"]["auth_provider"] == "email"
    assert body["user"]["avatar_url"] is None
    assert "password" not in body["user"]


def test_register_duplicate_email_conflict(api):
    payload = {"email": "a@b.com", "password": "password8", "display_name": "Bao"}
    api.post("/auth/register", payload, format="json")
    resp = api.post("/auth/register", {**payload, "email": "A@B.com"}, format="json")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


def test_register_short_password_validation_error(api):
    resp = api.post(
        "/auth/register",
        {"email": "a@b.com", "password": "short", "display_name": "Bao"},
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_success(api):
    api.post(
        "/auth/register",
        {"email": "a@b.com", "password": "password8", "display_name": "Bao"},
        format="json",
    )
    resp = api.post(
        "/auth/login", {"email": "a@b.com", "password": "password8"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


@pytest.mark.parametrize(
    "email,password",
    [("a@b.com", "wrongpass1"), ("unknown@b.com", "password8")],
)
def test_login_bad_credentials_same_code(api, email, password):
    api.post(
        "/auth/register",
        {"email": "a@b.com", "password": "password8", "display_name": "Bao"},
        format="json",
    )
    resp = api.post(
        "/auth/login", {"email": email, "password": password}, format="json"
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"
