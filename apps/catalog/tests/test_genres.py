"""API tests for GET /catalog/genres (curated list, no upstream)."""

from __future__ import annotations

from rest_framework.test import APIClient


def test_genres_returns_curated_slug_name_pairs(api, jamendo):
    resp = api.get("/catalog/genres")
    assert resp.status_code == 200
    body = resp.json()
    assert {"slug": "electronic", "name": "Electronic"} in body
    # Only slug + name are exposed — the internal Jamendo ``tag`` never leaks.
    for entry in body:
        assert set(entry) == {"slug", "name"}


def test_genres_makes_no_upstream_call(api, jamendo):
    api.get("/catalog/genres")
    assert jamendo.calls == 0


def test_genres_requires_app_key(jamendo):
    resp = APIClient().get("/catalog/genres")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_APP_KEY"
