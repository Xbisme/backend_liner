"""US1 — playlist CRUD, track add/remove/reorder, hydration, contract shape."""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.library.models import Playlist
from apps.library.tests.conftest import jamendo_track
from apps.library.tests.factories import LikedTrackFactory

pytestmark = pytest.mark.django_db

PLAYLIST_FIELDS = {
    "id",
    "name",
    "track_count",
    "cover_url",
    "created_at",
    "updated_at",
}


def _mock_tracks(jamendo: Any, ids: list[str]) -> None:
    jamendo.respond_tracks([jamendo_track(tid) for tid in ids])


def _create(client: APIClient, name: str = "Chill") -> dict[str, Any]:
    resp = client.post("/me/playlists", {"name": name}, format="json")
    assert resp.status_code == 201, resp.content
    return resp.json()


def test_create_returns_empty_playlist(client_a: APIClient) -> None:
    body = _create(client_a)
    assert set(body) == PLAYLIST_FIELDS
    assert body["track_count"] == 0
    assert body["cover_url"] is None


def test_create_rejects_blank_name(client_a: APIClient) -> None:
    resp = client_a.post("/me/playlists", {"name": "   "}, format="json")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_add_track_appends_and_detail_orders(client_a: APIClient, jamendo: Any) -> None:
    pid = _create(client_a)["id"]
    for tid in ["1", "2", "3"]:
        assert (
            client_a.post(
                f"/me/playlists/{pid}/tracks", {"track_id": tid}, format="json"
            ).status_code
            == 204
        )
    _mock_tracks(jamendo, ["1", "2", "3"])
    detail = client_a.get(f"/me/playlists/{pid}").json()
    assert [t["id"] for t in detail["tracks"]] == ["1", "2", "3"]
    assert all(t["available"] for t in detail["tracks"])
    assert detail["track_count"] == 3


def test_duplicate_add_conflicts(client_a: APIClient) -> None:
    pid = _create(client_a)["id"]
    client_a.post(f"/me/playlists/{pid}/tracks", {"track_id": "1"}, format="json")
    resp = client_a.post(
        f"/me/playlists/{pid}/tracks", {"track_id": "1"}, format="json"
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "TRACK_ALREADY_IN_PLAYLIST"


def test_remove_track_is_idempotent(client_a: APIClient) -> None:
    pid = _create(client_a)["id"]
    client_a.post(f"/me/playlists/{pid}/tracks", {"track_id": "1"}, format="json")
    assert client_a.delete(f"/me/playlists/{pid}/tracks/1").status_code == 204
    # Removing an absent track still succeeds (idempotent).
    assert client_a.delete(f"/me/playlists/{pid}/tracks/1").status_code == 204
    assert client_a.delete(f"/me/playlists/{pid}/tracks/999").status_code == 204


def test_reorder_updates_order(client_a: APIClient, jamendo: Any) -> None:
    pid = _create(client_a)["id"]
    for tid in ["1", "2", "3"]:
        client_a.post(f"/me/playlists/{pid}/tracks", {"track_id": tid}, format="json")
    _mock_tracks(jamendo, ["1", "2", "3"])
    resp = client_a.patch(
        f"/me/playlists/{pid}/tracks/reorder",
        {"track_ids": ["3", "1", "2"]},
        format="json",
    )
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()["tracks"]] == ["3", "1", "2"]


def test_reorder_mismatch_rejected(client_a: APIClient) -> None:
    pid = _create(client_a)["id"]
    for tid in ["1", "2", "3"]:
        client_a.post(f"/me/playlists/{pid}/tracks", {"track_id": tid}, format="json")
    resp = client_a.patch(
        f"/me/playlists/{pid}/tracks/reorder",
        {"track_ids": ["3", "1"]},  # missing "2"
        format="json",
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "REORDER_MISMATCH"


def test_rename_and_delete(client_a: APIClient) -> None:
    pid = _create(client_a)["id"]
    renamed = client_a.patch(
        f"/me/playlists/{pid}", {"name": "New Name"}, format="json"
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "New Name"
    assert client_a.delete(f"/me/playlists/{pid}").status_code == 204
    assert not Playlist.objects.filter(pk=pid).exists()


def test_list_orders_by_recency(client_a: APIClient, jamendo: Any) -> None:
    first = _create(client_a, "First")["id"]
    _create(client_a, "Second")
    _mock_tracks(jamendo, ["1"])
    # Touch the first playlist so it bubbles to the top.
    client_a.post(f"/me/playlists/{first}/tracks", {"track_id": "1"}, format="json")
    items = client_a.get("/me/playlists").json()["items"]
    assert items[0]["id"] == first
    assert items[0]["track_count"] == 1


def test_detail_is_liked_reflects_user(
    client_a: APIClient, user_a: Any, jamendo: Any
) -> None:
    pid = _create(client_a)["id"]
    client_a.post(f"/me/playlists/{pid}/tracks", {"track_id": "1"}, format="json")
    client_a.post(f"/me/playlists/{pid}/tracks", {"track_id": "2"}, format="json")
    LikedTrackFactory(user=user_a, track_id="1")
    _mock_tracks(jamendo, ["1", "2"])
    tracks = {t["id"]: t for t in client_a.get(f"/me/playlists/{pid}").json()["tracks"]}
    assert tracks["1"]["is_liked"] is True
    assert tracks["2"]["is_liked"] is False


def test_list_pagination_shape(client_a: APIClient) -> None:
    body = client_a.get("/me/playlists").json()
    assert set(body) == {"items", "next_cursor", "has_more"}
