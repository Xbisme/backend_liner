"""US2 — liked tracks: idempotent like/unlike, listing, isolation."""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.library.models import LikedTrack
from apps.library.tests.conftest import jamendo_track
from apps.library.tests.factories import LikedTrackFactory

pytestmark = pytest.mark.django_db


def test_like_is_idempotent(client_a: APIClient, user_a: Any) -> None:
    assert client_a.post("/me/liked-tracks/1").status_code == 204
    assert client_a.post("/me/liked-tracks/1").status_code == 204  # again → still 204
    assert LikedTrack.objects.filter(user=user_a, track_id="1").count() == 1


def test_unlike_removes_and_is_idempotent(client_a: APIClient, user_a: Any) -> None:
    client_a.post("/me/liked-tracks/1")
    assert client_a.delete("/me/liked-tracks/1").status_code == 204
    assert not LikedTrack.objects.filter(user=user_a, track_id="1").exists()
    # Unliking a not-liked track still succeeds.
    assert client_a.delete("/me/liked-tracks/1").status_code == 204


def test_list_returns_liked_tracks(
    client_a: APIClient, user_a: Any, jamendo: Any
) -> None:
    LikedTrackFactory(user=user_a, track_id="1")
    LikedTrackFactory(user=user_a, track_id="2")
    jamendo.respond_tracks([jamendo_track("1"), jamendo_track("2")])
    body = client_a.get("/me/liked-tracks").json()
    assert set(body) == {"items", "next_cursor", "has_more"}
    assert {t["id"] for t in body["items"]} == {"1", "2"}
    assert all(t["is_liked"] is True for t in body["items"])


def test_liked_list_is_isolated_per_user(
    client_a: APIClient, user_b: Any, jamendo: Any
) -> None:
    LikedTrackFactory(user=user_b, track_id="9")  # B's like
    body = client_a.get("/me/liked-tracks").json()
    assert body["items"] == []


def test_like_requires_auth(app_key: str) -> None:
    client = APIClient()
    client.credentials(HTTP_X_APP_KEY=app_key)  # no bearer
    resp = client.post("/me/liked-tracks/1")
    assert resp.status_code == 401
