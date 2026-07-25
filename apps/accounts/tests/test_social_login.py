import pytest

from apps.accounts.models import SocialIdentity, User
from apps.accounts.services import social
from apps.accounts.tests.factories import UserFactory
from core.errors import ErrorCode
from core.exceptions import AppError

pytestmark = pytest.mark.django_db


def _mock_verify(monkeypatch, result):
    monkeypatch.setattr(social, "verify_social_token", lambda provider, token: result)


def test_google_first_time_creates_account(api, monkeypatch):
    _mock_verify(
        monkeypatch, {"provider": "google", "subject_id": "g-1", "email": "g@x.com"}
    )
    resp = api.post(
        "/auth/social-login", {"provider": "google", "id_token": "tok"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "g@x.com"
    assert User.objects.filter(email="g@x.com").count() == 1
    assert (
        SocialIdentity.objects.filter(provider="google", subject_id="g-1").count() == 1
    )


def test_same_subject_reuses_account(api, monkeypatch):
    _mock_verify(
        monkeypatch, {"provider": "google", "subject_id": "g-1", "email": "g@x.com"}
    )
    api.post(
        "/auth/social-login", {"provider": "google", "id_token": "tok"}, format="json"
    )
    api.post(
        "/auth/social-login", {"provider": "google", "id_token": "tok"}, format="json"
    )
    assert User.objects.filter(email="g@x.com").count() == 1
    assert SocialIdentity.objects.filter(subject_id="g-1").count() == 1


def test_apple_without_email_creates_null_email_account(api, monkeypatch):
    _mock_verify(monkeypatch, {"provider": "apple", "subject_id": "a-1", "email": None})
    resp = api.post(
        "/auth/social-login", {"provider": "apple", "id_token": "tok"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] is None
    user = User.objects.get(social_identities__subject_id="a-1")
    assert user.email is None


def test_email_match_auto_links_existing_account(api, monkeypatch):
    existing = UserFactory(email="dup@x.com")
    _mock_verify(
        monkeypatch, {"provider": "google", "subject_id": "g-9", "email": "dup@x.com"}
    )
    resp = api.post(
        "/auth/social-login", {"provider": "google", "id_token": "tok"}, format="json"
    )
    assert resp.status_code == 200
    assert User.objects.filter(email="dup@x.com").count() == 1  # no duplicate
    assert existing.social_identities.filter(subject_id="g-9").exists()


def test_invalid_token_returns_social_token_invalid(api, monkeypatch):
    def _raise(provider, token):
        raise AppError(ErrorCode.SOCIAL_TOKEN_INVALID)

    monkeypatch.setattr(social, "verify_social_token", _raise)
    resp = api.post(
        "/auth/social-login", {"provider": "google", "id_token": "bad"}, format="json"
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "SOCIAL_TOKEN_INVALID"


def test_unknown_provider_is_validation_error(api):
    resp = api.post(
        "/auth/social-login", {"provider": "facebook", "id_token": "tok"}, format="json"
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
