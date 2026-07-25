"""Unit tests for the Jamendo → contract mapper (no DB, no network)."""

from __future__ import annotations

from apps.catalog.services import mapper
from apps.catalog.tests.factories import album_result, artist_result, track_result


def test_map_track_full():
    out = mapper.map_track(track_result())
    assert out["id"] == "123"
    assert out["title"] == "Night Drive"
    assert out["duration_seconds"] == 214
    assert out["stream_url"].startswith("https://prod-1.storage.jamendo.com/")
    assert out["is_liked"] is False


def test_map_track_flat_to_nested_artist_and_album():
    out = mapper.map_track(track_result())
    assert out["artist"] == {
        "id": "998",
        "name": "Aeon Waves",
        "image_url": "https://usercontent.jamendo.com/artist/998.jpg",
    }
    assert out["album"]["id"] == "555"
    assert out["album"]["title"] == "Synth Horizons"
    assert out["album"]["artist"]["id"] == "998"


def test_map_track_genre_lookup_drops_unknown_tags():
    # "synthwave" is not curated; "electronic" is → only the curated one survives.
    out = mapper.map_track(track_result())
    assert out["genres"] == [{"slug": "electronic", "name": "Electronic"}]


def test_license_label_known_and_unknown():
    assert mapper.map_track(track_result())["license_type"] == "CC BY-NC-SA"
    unknown = mapper.map_track(track_result(license_ccurl="https://example.com/weird"))
    assert unknown["license_type"] == ""


def test_map_track_missing_fields_safe():
    out = mapper.map_track({"id": 77})  # numeric id, everything else absent
    assert out["id"] == "77"
    assert out["title"] == ""
    assert out["duration_seconds"] == 0
    assert out["genres"] == []
    assert out["album"]["id"] == ""
    assert out["license_type"] == ""


def test_map_artist_and_album():
    a = mapper.map_artist(artist_result())
    assert a == {
        "id": "998",
        "name": "Aeon Waves",
        "image_url": "https://usercontent.jamendo.com/artist/998.jpg",
    }
    al = mapper.map_album(album_result())
    assert al["id"] == "555"
    assert al["title"] == "Synth Horizons"
    assert al["artist"]["name"] == "Aeon Waves"
