"""Catalog orchestration used by views (Constitution III/IV).

Ties together validation → JamendoClient → mapper → cache → cursor. Validation and
genre-slug checks run *before* any upstream call, so invalid input never hits Jamendo
and failures are never cached.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.cache import cache as track_cache

from apps.catalog import genres as genre_helper
from apps.catalog.pagination import build_page, decode_cursor
from apps.catalog.services import cache, jamendo
from apps.catalog.services.mapper import (
    map_album_detail,
    map_artist_detail,
    map_track,
    map_tracks,
)
from core.errors import ErrorCode
from core.exceptions import AppError


def _tombstone(track_id: str) -> dict[str, Any]:
    """A saved track that no longer resolves upstream (BE-003, research §1)."""
    return {
        "id": track_id,
        "available": False,
        "title": None,
        "artist": None,
        "album": None,
        "genres": [],
        "duration_seconds": None,
        "cover_url": None,
        "stream_url": None,
        "license_type": None,
        "is_liked": False,
    }


def get_tracks_by_ids(
    ids: list[str], *, liked_ids: set[str] | None = None
) -> list[dict[str, Any]]:
    """Hydrate saved ``track_id``s into contract ``Track`` dicts (Constitution III/IV).

    Public entrypoint for ``apps/library`` — the only way that app reaches the catalog.
    Reuses the per-id ``track`` cache (a track warmed by ``/catalog/tracks/{id}`` is a
    hit here and vice-versa); only cache-misses are batched upstream in ONE call.
    Order matches ``ids``; an id the upstream cannot resolve becomes a tombstone.
    A *global* upstream failure raises ``CATALOG_UPSTREAM_ERROR`` (propagated) — that
    is distinct from a single id simply being absent.
    """
    liked = liked_ids or set()
    unique_ids = list(dict.fromkeys(ids))  # preserve order, drop dupes
    resolved: dict[str, dict[str, Any]] = {}

    misses: list[str] = []
    for track_id in unique_ids:
        cached = track_cache.get(cache.cache_key("track", {"id": track_id}))
        if cached is not None:
            resolved[track_id] = cached
        else:
            misses.append(track_id)

    if misses:
        for raw in jamendo.list_tracks_by_ids(misses):
            mapped = map_track(raw)
            track_id = mapped["id"]
            track_cache.set(
                cache.cache_key("track", {"id": track_id}),
                mapped,
                settings.CACHE_TTL_DETAIL,
            )
            resolved[track_id] = mapped

    out: list[dict[str, Any]] = []
    for track_id in ids:
        base = resolved.get(track_id)
        track = dict(base) if base is not None else _tombstone(track_id)
        track["is_liked"] = track_id in liked
        out.append(track)
    return out


def _normalize_limit(raw: str | int | None) -> int:
    """Default if missing; clamp integers to 1..MAX; non-integer → VALIDATION_ERROR."""
    default: int = settings.CATALOG_TRACKS_PAGE_SIZE_DEFAULT
    maximum: int = settings.CATALOG_TRACKS_PAGE_SIZE_MAX
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise AppError(ErrorCode.VALIDATION_ERROR, "limit must be an integer.")
    return max(1, min(value, maximum))


def trending(genre_slug: str | None = None) -> list[dict[str, Any]]:
    tag = genre_helper.slug_to_tag(genre_slug)
    key = cache.cache_key("trending", {"genre": genre_slug})

    def fetch() -> list[dict[str, Any]]:
        raw = jamendo.trending(tag=tag, size=settings.CATALOG_TRENDING_SIZE)
        return map_tracks(raw)

    return cache.get_or_fetch(key, settings.CACHE_TTL_TRENDING, fetch)


def list_tracks(
    *,
    search: str | None = None,
    genre_slug: str | None = None,
    cursor: str | None = None,
    limit: str | int | None = None,
) -> dict[str, Any]:
    limit_val = _normalize_limit(limit)
    offset = decode_cursor(cursor)
    tag = genre_helper.slug_to_tag(genre_slug)
    key = cache.cache_key(
        "tracks",
        {"search": search, "genre": genre_slug, "offset": offset, "limit": limit_val},
    )

    def fetch() -> dict[str, Any]:
        results, fullcount = jamendo.list_tracks(
            search=search, tag=tag, offset=offset, limit=limit_val
        )
        return build_page(map_tracks(results), offset, limit_val, fullcount)

    return cache.get_or_fetch(key, settings.CACHE_TTL_SEARCH, fetch)


def get_track(track_id: str) -> dict[str, Any]:
    key = cache.cache_key("track", {"id": track_id})
    return cache.get_or_fetch(
        key, settings.CACHE_TTL_DETAIL, lambda: map_track(jamendo.get_track(track_id))
    )


def get_artist(artist_id: str) -> dict[str, Any]:
    """ArtistDetail: artist + its tracks + albums (research: mobile MO catalog)."""
    key = cache.cache_key("artist_detail", {"id": artist_id})

    def fetch() -> dict[str, Any]:
        raw = jamendo.get_artist(artist_id)  # raises NOT_FOUND if the artist is absent
        albums = jamendo.get_artist_albums(artist_id)
        return map_artist_detail(raw, albums)

    return cache.get_or_fetch(key, settings.CACHE_TTL_DETAIL, fetch)


def get_album(album_id: str) -> dict[str, Any]:
    """AlbumDetail: album + its tracks (research: mobile MO catalog)."""
    key = cache.cache_key("album_detail", {"id": album_id})
    return cache.get_or_fetch(
        key,
        settings.CACHE_TTL_DETAIL,
        lambda: map_album_detail(jamendo.get_album(album_id)),
    )
