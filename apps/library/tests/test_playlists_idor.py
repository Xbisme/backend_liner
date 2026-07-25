"""US1 — IDOR: user B must never read/mutate user A's playlists (Constitution I)."""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.library.models import Playlist, PlaylistTrack
from apps.library.tests.factories import PlaylistFactory, PlaylistTrackFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def a_playlist(user_a: Any) -> Playlist:
    playlist = PlaylistFactory(owner=user_a)
    PlaylistTrackFactory(playlist=playlist, track_id="1", position=0)
    return playlist


def test_b_cannot_read_a_playlist(client_b: APIClient, a_playlist: Playlist) -> None:
    resp = client_b.get(f"/me/playlists/{a_playlist.id}")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_b_cannot_rename_a_playlist(client_b: APIClient, a_playlist: Playlist) -> None:
    resp = client_b.patch(
        f"/me/playlists/{a_playlist.id}", {"name": "hacked"}, format="json"
    )
    assert resp.status_code == 403
    a_playlist.refresh_from_db()
    assert a_playlist.name != "hacked"


def test_b_cannot_delete_a_playlist(client_b: APIClient, a_playlist: Playlist) -> None:
    assert client_b.delete(f"/me/playlists/{a_playlist.id}").status_code == 403
    assert Playlist.objects.filter(pk=a_playlist.id).exists()


def test_b_cannot_add_track_to_a_playlist(
    client_b: APIClient, a_playlist: Playlist
) -> None:
    resp = client_b.post(
        f"/me/playlists/{a_playlist.id}/tracks", {"track_id": "9"}, format="json"
    )
    assert resp.status_code == 403
    assert not PlaylistTrack.objects.filter(playlist=a_playlist, track_id="9").exists()


def test_b_cannot_remove_track_from_a_playlist(
    client_b: APIClient, a_playlist: Playlist
) -> None:
    assert client_b.delete(f"/me/playlists/{a_playlist.id}/tracks/1").status_code == 403
    assert PlaylistTrack.objects.filter(playlist=a_playlist, track_id="1").exists()


def test_b_cannot_reorder_a_playlist(client_b: APIClient, a_playlist: Playlist) -> None:
    resp = client_b.patch(
        f"/me/playlists/{a_playlist.id}/tracks/reorder",
        {"track_ids": ["1"]},
        format="json",
    )
    assert resp.status_code == 403


def test_nonexistent_playlist_is_404(client_a: APIClient) -> None:
    resp = client_a.get("/me/playlists/999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_spoofed_user_id_in_body_is_ignored(
    client_b: APIClient, user_a: Any, a_playlist: Playlist
) -> None:
    # B tries to claim ownership via body — must be ignored; still 403.
    resp = client_b.patch(
        f"/me/playlists/{a_playlist.id}",
        {"name": "x", "user_id": user_a.id, "owner": user_a.id},
        format="json",
    )
    assert resp.status_code == 403


def test_a_only_sees_own_playlists(client_a: APIClient, user_b: Any) -> None:
    PlaylistFactory(owner=user_b)  # B's playlist
    items = client_a.get("/me/playlists").json()["items"]
    assert items == []
