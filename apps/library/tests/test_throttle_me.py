"""``/me/*`` write throttles are per-user and isolate one user from another."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from rest_framework.settings import api_settings
from rest_framework.test import APIClient

from apps.accounts.models import User


def _set_history_rate(settings: Any, rate: str) -> None:
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
            "history": rate,
        },
    }
    api_settings.reload()


@pytest.mark.django_db
def test_history_throttled_after_limit(client_a: APIClient, settings: Any) -> None:
    _set_history_rate(settings, "3/min")
    codes = [
        client_a.post("/me/history", {"track_id": f"t{i}"}, format="json").status_code
        for i in range(5)
    ]
    assert codes.count(201) == 3
    assert codes[-1] == 429


@pytest.mark.django_db
def test_history_throttle_is_per_user(
    client_a: APIClient,
    make_client: Callable[[User], APIClient],
    user_b: User,
    settings: Any,
) -> None:
    _set_history_rate(settings, "2/min")
    # User A exhausts their bucket.
    for i in range(3):
        client_a.post("/me/history", {"track_id": f"a{i}"}, format="json")
    # User B is unaffected (separate bucket).
    client_b = make_client(user_b)
    resp = client_b.post("/me/history", {"track_id": "b0"}, format="json")
    assert resp.status_code == 201


@pytest.mark.django_db
def test_history_get_is_not_throttled(
    client_a: APIClient, settings: Any, jamendo: Any
) -> None:
    """Reads use no write budget — many GETs stay allowed even at a tiny rate."""
    _set_history_rate(settings, "1/min")
    codes = [client_a.get("/me/history").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 200]
