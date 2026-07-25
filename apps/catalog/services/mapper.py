"""Map raw Jamendo JSON → contract dicts (Constitution IV, data-model.md).

Every mapper tolerates missing upstream fields with safe empties and never raises.
Ids are coerced to strings; ``license_type`` is derived from ``license_ccurl`` and
the raw URL is never emitted; per-track genres map to the curated vocabulary.
"""

from __future__ import annotations

from typing import Any

from apps.catalog import genres as genre_helper
from apps.catalog.constants import license_label


def _s(value: Any) -> str:
    """Coerce to string; ``None``/missing → ``""``."""
    return "" if value is None else str(value)


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def map_artist(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a Jamendo ``/artists`` result (or nested artist fields)."""
    return {
        "id": _s(raw.get("id")),
        "name": _s(raw.get("name")),
        "image_url": _s(raw.get("image")),
    }


def _artist_from_track(raw: dict[str, Any]) -> dict[str, Any]:
    """Build the nested artist from a track's flat ``artist_*`` fields."""
    return {
        "id": _s(raw.get("artist_id")),
        "name": _s(raw.get("artist_name")),
        "image_url": _s(raw.get("artist_image")),
    }


def map_album(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a Jamendo ``/albums`` result."""
    return {
        "id": _s(raw.get("id")),
        "title": _s(raw.get("name")),
        "artist": {
            "id": _s(raw.get("artist_id")),
            "name": _s(raw.get("artist_name")),
            "image_url": _s(raw.get("artist_image")),
        },
        "cover_url": _s(raw.get("image")),
    }


def _album_from_track(raw: dict[str, Any]) -> dict[str, Any]:
    """Build the nested album from a track's flat ``album_*`` fields."""
    return {
        "id": _s(raw.get("album_id")),
        "title": _s(raw.get("album_name")),
        "artist": _artist_from_track(raw),
        "cover_url": _s(raw.get("album_image")),
    }


def _track_genres(raw: dict[str, Any]) -> list[dict[str, str]]:
    musicinfo = raw.get("musicinfo") or {}
    tags = musicinfo.get("tags") or {}
    return genre_helper.genres_from_tags(tags.get("genres"))


def map_track(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a Jamendo ``/tracks`` result to the contract ``Track``."""
    return {
        "id": _s(raw.get("id")),
        "title": _s(raw.get("name")),
        "artist": _artist_from_track(raw),
        "album": _album_from_track(raw),
        "genres": _track_genres(raw),
        "duration_seconds": _int(raw.get("duration")),
        "cover_url": _s(raw.get("image")) or _s(raw.get("album_image")),
        "stream_url": _s(raw.get("audio")),
        "license_type": license_label(raw.get("license_ccurl")),
        "is_liked": False,  # BE-002: always false; BE-003 wires per-user.
    }


def map_tracks(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [map_track(r) for r in results]
