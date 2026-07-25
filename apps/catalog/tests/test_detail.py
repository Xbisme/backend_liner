"""API tests for GET /catalog/{tracks,artists,albums}/{id}."""

from __future__ import annotations

from apps.catalog.tests.factories import (
    album_result,
    artist_result,
    envelope,
    track_result,
)


def test_track_detail(api, jamendo):
    jamendo.respond_json(envelope([track_result("123")]))
    resp = api.get("/catalog/tracks/123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "123"
    assert body["stream_url"].startswith("https://")
    assert body["is_liked"] is False


def test_artist_detail(api, jamendo):
    jamendo.respond_json(envelope([artist_result("998")]))
    resp = api.get("/catalog/artists/998")
    assert resp.status_code == 200
    assert resp.json() == {
        "id": "998",
        "name": "Aeon Waves",
        "image_url": "https://usercontent.jamendo.com/artist/998.jpg",
    }


def test_album_detail(api, jamendo):
    jamendo.respond_json(envelope([album_result("555")]))
    resp = api.get("/catalog/albums/555")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "555"
    assert body["title"] == "Synth Horizons"
    assert body["artist"]["name"] == "Aeon Waves"


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
