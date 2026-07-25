"""API tests for GET /catalog/{tracks,artists,albums}/{id}."""

from __future__ import annotations

from typing import Any

import httpx

from apps.catalog.tests.factories import (
    album_result,
    artist_result,
    envelope,
    track_result,
)


def _nested_track(track_id: str) -> dict[str, Any]:
    """A track as nested under /albums/tracks or /artists/tracks (no parent fields)."""
    return {
        "id": track_id,
        "name": f"Track {track_id}",
        "duration": 120,
        "audio": f"https://prod-1.storage.jamendo.com/track/{track_id}/stream.mp3",
        "license_ccurl": "http://creativecommons.org/licenses/by-nc-sa/3.0/",
    }


def test_track_detail(api, jamendo):
    jamendo.respond_json(envelope([track_result("123")]))
    resp = api.get("/catalog/tracks/123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "123"
    assert body["stream_url"].startswith("https://")
    assert body["is_liked"] is False


def test_artist_detail(api, jamendo):
    artist = artist_result("998")
    artist["tracks"] = [_nested_track("1"), _nested_track("2")]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/artists/tracks"):
            return httpx.Response(200, json=envelope([artist]))
        if path.endswith("/albums"):  # /albums?artist_id=998
            return httpx.Response(200, json=envelope([album_result("555")]))
        return httpx.Response(200, json=envelope([]))

    jamendo.respond(handler)
    resp = api.get("/catalog/artists/998")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "998"
    assert body["name"] == "Aeon Waves"
    assert body["image_url"] == "https://usercontent.jamendo.com/artist/998.jpg"
    # Nested tracks are hydrated with the parent artist's identity.
    assert [t["id"] for t in body["tracks"]] == ["1", "2"]
    assert body["tracks"][0]["artist"]["id"] == "998"
    assert [a["id"] for a in body["albums"]] == ["555"]


def test_album_detail(api, jamendo):
    album = album_result("555")
    album["tracks"] = [_nested_track("1"), _nested_track("2")]
    jamendo.respond_json(envelope([album]))
    resp = api.get("/catalog/albums/555")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "555"
    assert body["title"] == "Synth Horizons"
    assert body["artist"]["name"] == "Aeon Waves"
    # Nested tracks carry the parent album/artist context.
    assert [t["id"] for t in body["tracks"]] == ["1", "2"]
    assert body["tracks"][0]["album"]["id"] == "555"
    assert body["tracks"][0]["artist"]["id"] == "998"


def test_detail_not_found(api, jamendo):
    jamendo.respond_json(envelope([]))
    resp = api.get("/catalog/tracks/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_detail_upstream_failure_is_502(api, jamendo):
    jamendo.raise_timeout()
    resp = api.get("/catalog/artists/998")
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "CATALOG_UPSTREAM_ERROR"
