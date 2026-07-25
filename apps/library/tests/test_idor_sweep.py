"""Cross-user isolation sweep for /me/* (BE-004 FR-016/SC-006).

Playlist IDOR (403 on another user's playlist + nested resources) is covered by
``test_playlists_idor.py``. This sweep adds the remaining ``/me/*`` surfaces —
liked-tracks and history — proving one user never sees or mutates another's rows.
"""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.library.tests.conftest import jamendo_track


@pytest.mark.django_db
def test_liked_tracks_are_user_scoped(
    client_a: APIClient, client_b: APIClient, jamendo: Any
) -> None:
    jamendo.respond_tracks([jamendo_track("t1")])
    assert client_b.post("/me/liked-tracks/t1").status_code == 204

    a_items = client_a.get("/me/liked-tracks").json()["items"]
    assert a_items == []  # A never sees B's likes

    b_ids = [t["id"] for t in client_b.get("/me/liked-tracks").json()["items"]]
    assert b_ids == ["t1"]


@pytest.mark.django_db
def test_unlike_only_affects_own_likes(
    client_a: APIClient, client_b: APIClient, jamendo: Any
) -> None:
    jamendo.respond_tracks([jamendo_track("t1")])
    client_b.post("/me/liked-tracks/t1")
    # A unliking "t1" is a no-op on B's like (idempotent, per-user).
    assert client_a.delete("/me/liked-tracks/t1").status_code == 204

    b_ids = [t["id"] for t in client_b.get("/me/liked-tracks").json()["items"]]
    assert b_ids == ["t1"]  # B's like is intact


@pytest.mark.django_db
def test_history_is_user_scoped(
    client_a: APIClient, client_b: APIClient, jamendo: Any
) -> None:
    jamendo.respond_tracks([jamendo_track("t1")])
    assert (
        client_b.post("/me/history", {"track_id": "t1"}, format="json").status_code
        == 201
    )

    assert client_a.get("/me/history").json()["items"] == []  # A sees none of B's

    b_ids = [t["id"] for t in client_b.get("/me/history").json()["items"]]
    assert b_ids == ["t1"]
