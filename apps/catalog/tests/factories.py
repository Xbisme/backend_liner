"""Builders for raw Jamendo JSON payloads used in catalog tests."""

from __future__ import annotations

from typing import Any


def track_result(track_id: str = "123", **overrides: Any) -> dict[str, Any]:
    """A raw Jamendo ``/tracks`` result with the flat fields the mapper reads."""
    base: dict[str, Any] = {
        "id": track_id,
        "name": "Night Drive",
        "duration": 214,
        "artist_id": "998",
        "artist_name": "Aeon Waves",
        "artist_image": "https://usercontent.jamendo.com/artist/998.jpg",
        "album_id": "555",
        "album_name": "Synth Horizons",
        "album_image": "https://usercontent.jamendo.com/album/555.jpg",
        "image": "https://usercontent.jamendo.com/track/123.jpg",
        "audio": "https://prod-1.storage.jamendo.com/track/123/stream.mp3",
        "license_ccurl": "http://creativecommons.org/licenses/by-nc-sa/3.0/",
        "musicinfo": {"tags": {"genres": ["synthwave", "electronic"]}},
    }
    base.update(overrides)
    return base


def artist_result(artist_id: str = "998", **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": artist_id,
        "name": "Aeon Waves",
        "image": "https://usercontent.jamendo.com/artist/998.jpg",
    }
    base.update(overrides)
    return base


def album_result(album_id: str = "555", **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": album_id,
        "name": "Synth Horizons",
        "artist_id": "998",
        "artist_name": "Aeon Waves",
        "image": "https://usercontent.jamendo.com/album/555.jpg",
    }
    base.update(overrides)
    return base


def envelope(
    results: list[dict[str, Any]],
    *,
    status: str = "success",
    fullcount: int | None = None,
) -> dict[str, Any]:
    """Wrap results in Jamendo's ``{headers, results}`` envelope."""
    headers: dict[str, Any] = {
        "status": status,
        "code": 0,
        "results_count": len(results),
    }
    if fullcount is not None:
        headers["results_fullcount"] = fullcount
    return {"headers": headers, "results": results}
