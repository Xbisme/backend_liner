"""US3 — listening history: distinct upsert, cap, ordering, validation, isolation."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.library.models import ListeningHistory
from apps.library.tests.conftest import jamendo_track
from apps.library.tests.factories import ListeningHistoryFactory

pytestmark = pytest.mark.django_db


def test_post_records_and_is_distinct_upsert(client_a: APIClient, user_a: Any) -> None:
    t1 = (timezone.now() - timedelta(hours=1)).isoformat()
    assert (
        client_a.post(
            "/me/history", {"track_id": "1", "played_at": t1}, format="json"
        ).status_code
        == 201
    )
    t2 = timezone.now().isoformat()
    client_a.post(
        "/me/history",
        {"track_id": "1", "played_at": t2, "completed": True},
        format="json",
    )
    rows = ListeningHistory.objects.filter(user=user_a, track_id="1")
    assert rows.count() == 1  # upsert, not a new row
    assert rows.first().completed is True


def test_played_at_defaults_to_now_when_missing(
    client_a: APIClient, user_a: Any
) -> None:
    resp = client_a.post("/me/history", {"track_id": "5"}, format="json")
    assert resp.status_code == 201
    assert ListeningHistory.objects.filter(user=user_a, track_id="5").exists()


def test_future_played_at_rejected(client_a: APIClient) -> None:
    future = (timezone.now() + timedelta(days=1)).isoformat()
    resp = client_a.post(
        "/me/history", {"track_id": "1", "played_at": future}, format="json"
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_cap_trims_oldest(client_a: APIClient, user_a: Any, settings: Any) -> None:
    settings.HISTORY_MAX_ENTRIES = 3
    base = timezone.now()
    for i in range(5):
        client_a.post(
            "/me/history",
            {
                "track_id": str(i),
                "played_at": (base - timedelta(minutes=i)).isoformat(),
            },
            format="json",
        )
    remaining = set(
        ListeningHistory.objects.filter(user=user_a).values_list("track_id", flat=True)
    )
    # Newest 3 by played_at are tracks 0,1,2 (i=0 most recent).
    assert remaining == {"0", "1", "2"}


def test_list_orders_by_played_at_desc(
    client_a: APIClient, user_a: Any, jamendo: Any
) -> None:
    now = timezone.now()
    ListeningHistoryFactory(
        user=user_a, track_id="1", played_at=now - timedelta(hours=2)
    )
    ListeningHistoryFactory(
        user=user_a, track_id="2", played_at=now - timedelta(hours=1)
    )
    ListeningHistoryFactory(user=user_a, track_id="3", played_at=now)
    jamendo.respond_tracks([jamendo_track(t) for t in ["1", "2", "3"]])
    items = client_a.get("/me/history").json()["items"]
    assert [t["id"] for t in items] == ["3", "2", "1"]


def test_history_is_isolated_per_user(client_a: APIClient, user_b: Any) -> None:
    ListeningHistoryFactory(user=user_b, track_id="9")
    assert client_a.get("/me/history").json()["items"] == []
