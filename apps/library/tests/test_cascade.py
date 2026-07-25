"""Polish — DELETE /me cascades to all library rows, no orphans (FR-019, SC-005)."""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.library.models import (
    LikedTrack,
    ListeningHistory,
    Playlist,
    PlaylistTrack,
)
from apps.library.tests.factories import (
    LikedTrackFactory,
    ListeningHistoryFactory,
    PlaylistTrackFactory,
)

pytestmark = pytest.mark.django_db


def test_delete_me_removes_all_library_rows(client_a: APIClient, user_a: Any) -> None:
    pt = PlaylistTrackFactory(playlist__owner=user_a)
    LikedTrackFactory(user=user_a)
    ListeningHistoryFactory(user=user_a)
    playlist_id = pt.playlist_id

    assert client_a.delete("/me").status_code == 204

    assert not Playlist.objects.filter(owner=user_a).exists()
    assert not PlaylistTrack.objects.filter(playlist_id=playlist_id).exists()
    assert not LikedTrack.objects.filter(user=user_a).exists()
    assert not ListeningHistory.objects.filter(user=user_a).exists()
