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
        "available": True,  # real upstream result; tombstones set False (BE-003).
        "title": _s(raw.get("name")),
        "artist": _artist_from_track(raw),
        "album": _album_from_track(raw),
        "genres": _track_genres(raw),
        "duration_seconds": _int(raw.get("duration")),
        "cover_url": _s(raw.get("image")) or _s(raw.get("album_image")),
        "stream_url": _s(raw.get("audio")),
        "license_type": license_label(raw.get("license_ccurl")),
        "is_liked": False,  # per-request; BE-003 library responses set from liked set.
    }


def map_tracks(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [map_track(r) for r in results]


def _nested_tracks(raw: dict[str, Any], parent: dict[str, Any]) -> list[dict[str, Any]]:
    """Map tracks nested under an album/artist, injecting the parent's flat fields.

    ``/albums/tracks`` and ``/artists/tracks`` return each track WITHOUT the parent's
    artist_*/album_* fields (they belong to the enclosing object), so merge them in
    before mapping so each Track carries full artist/album/cover data.
    """
    return [map_track({**parent, **t}) for t in raw.get("tracks") or []]


def map_album_detail(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a Jamendo ``/albums/tracks`` result to the contract ``AlbumDetail``."""
    parent = {
        "album_id": _s(raw.get("id")),
        "album_name": _s(raw.get("name")),
        "album_image": _s(raw.get("image")),
        "artist_id": _s(raw.get("artist_id")),
        "artist_name": _s(raw.get("artist_name")),
    }
    return {**map_album(raw), "tracks": _nested_tracks(raw, parent)}


def map_artist_detail(
    raw: dict[str, Any], albums: list[dict[str, Any]]
) -> dict[str, Any]:
    """Map a Jamendo ``/artists/tracks`` result (+ albums) to ``ArtistDetail``."""
    parent = {
        "artist_id": _s(raw.get("id")),
        "artist_name": _s(raw.get("name")),
        "artist_image": _s(raw.get("image")),
    }
    return {
        **map_artist(raw),
        "tracks": _nested_tracks(raw, parent),
        "albums": [map_album(a) for a in albums],
    }
