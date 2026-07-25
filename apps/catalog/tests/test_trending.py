"""API tests for GET /catalog/trending."""

from __future__ import annotations

import httpx
from rest_framework.test import APIClient

from apps.catalog.tests.factories import envelope, track_result


def test_trending_returns_mapped_tracks(api, jamendo):
    jamendo.respond_json(envelope([track_result("1"), track_result("2")]))
    resp = api.get("/catalog/trending")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["id"] == "1"
    assert "client_id" not in resp.content.decode()
    assert set(body[0]) == {
        "id",
        "title",
        "artist",
        "album",
        "genres",
        "duration_seconds",
        "cover_url",
        "stream_url",
        "license_type",
        "is_liked",
    }


def test_trending_genre_filter_maps_to_tags(api, jamendo):
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["tags"] = request.url.params.get("tags")
        seen["order"] = request.url.params.get("order")
        return httpx.Response(200, json=envelope([track_result("1")]))

    jamendo.respond(handler)
    resp = api.get("/catalog/trending?genre=electronic")
    assert resp.status_code == 200
    assert seen["tags"] == "electronic"
    assert seen["order"] == "popularity_month"


def test_trending_unknown_genre_is_validation_error_before_upstream(api, jamendo):
    resp = api.get("/catalog/trending?genre=nope")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert jamendo.calls == 0  # rejected before any upstream call


def test_trending_upstream_failure_is_502(api, jamendo):
    jamendo.raise_timeout()
    resp = api.get("/catalog/trending")
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "CATALOG_UPSTREAM_ERROR"


def test_trending_requires_app_key(jamendo):
    resp = APIClient().get("/catalog/trending")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_APP_KEY"
    assert jamendo.calls == 0
