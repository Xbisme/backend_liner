"""API tests for GET /catalog/tracks (search, genre, limit, cursor paging)."""

from __future__ import annotations

import httpx
from rest_framework.test import APIClient

from apps.catalog.pagination import decode_cursor
from apps.catalog.tests.factories import envelope, track_result


def test_tracks_page_shape_and_search(api, jamendo):
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["search"] = request.url.params.get("search")
        return httpx.Response(200, json=envelope([track_result("1")], fullcount=1))

    jamendo.respond(handler)
    resp = api.get("/catalog/tracks?search=night")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"items", "next_cursor", "has_more"}
    assert seen["search"] == "night"
    assert body["has_more"] is False
    assert body["next_cursor"] is None


def test_tracks_genre_maps_to_tags(api, jamendo):
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["tags"] = request.url.params.get("tags")
        return httpx.Response(200, json=envelope([track_result("1")], fullcount=1))

    jamendo.respond(handler)
    resp = api.get("/catalog/tracks?genre=jazz")
    assert resp.status_code == 200
    assert seen["tags"] == "jazz"


def test_tracks_unknown_genre_validation_error(api, jamendo):
    resp = api.get("/catalog/tracks?genre=nope")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert jamendo.calls == 0


def test_limit_out_of_range_integer_is_clamped(api, jamendo):
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["limit"] = request.url.params.get("limit")
        return httpx.Response(200, json=envelope([track_result("1")], fullcount=1))

    jamendo.respond(handler)
    resp = api.get("/catalog/tracks?limit=999")
    assert resp.status_code == 200
    assert seen["limit"] == "50"  # clamped to max, not an error


def test_limit_non_integer_is_validation_error(api, jamendo):
    resp = api.get("/catalog/tracks?limit=abc")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert jamendo.calls == 0


def test_malformed_cursor_is_validation_error(api, jamendo):
    resp = api.get("/catalog/tracks?cursor=%%%notbase64%%%")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_cursor_paging_no_overlap(api, jamendo):
    # 3 total rows, page size 2 → page 1 has_more, page 2 is the tail.
    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params.get("offset", "0"))
        rows = [track_result("1"), track_result("2"), track_result("3")]
        window = rows[offset : offset + 2]
        return httpx.Response(200, json=envelope(window, fullcount=3))

    jamendo.respond(handler)
    p1 = api.get("/catalog/tracks?limit=2").json()
    assert [t["id"] for t in p1["items"]] == ["1", "2"]
    assert p1["has_more"] is True
    assert decode_cursor(p1["next_cursor"]) == 2

    p2 = api.get(f"/catalog/tracks?limit=2&cursor={p1['next_cursor']}").json()
    assert [t["id"] for t in p2["items"]] == ["3"]
    assert p2["has_more"] is False


def test_empty_results_is_ok_not_error(api, jamendo):
    jamendo.respond_json(envelope([], fullcount=0))
    resp = api.get("/catalog/tracks?search=zzzznothing")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["has_more"] is False


def test_identical_calls_hit_cache_once(api, jamendo):
    jamendo.respond_json(envelope([track_result("1")], fullcount=1))
    api.get("/catalog/tracks?search=cacheme")
    api.get("/catalog/tracks?search=cacheme")
    assert jamendo.calls == 1  # second served from cache


def test_no_bearer_token_still_succeeds(jamendo):
    # FR-016 positive case: valid app-key, NO Authorization header → 200.
    from django.conf import settings

    jamendo.respond_json(envelope([track_result("1")], fullcount=1))
    client = APIClient()
    client.credentials(HTTP_X_APP_KEY=settings.X_APP_KEY)  # app-key only
    resp = client.get("/catalog/tracks")
    assert resp.status_code == 200
