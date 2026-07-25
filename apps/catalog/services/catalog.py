"""Catalog orchestration used by views (Constitution III/IV).

Ties together validation → JamendoClient → mapper → cache → cursor. Validation and
genre-slug checks run *before* any upstream call, so invalid input never hits Jamendo
and failures are never cached.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.catalog import genres as genre_helper
from apps.catalog.pagination import build_page, decode_cursor
from apps.catalog.services import cache, jamendo
from apps.catalog.services.mapper import map_album, map_artist, map_track, map_tracks
from core.errors import ErrorCode
from core.exceptions import AppError


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
    key = cache.cache_key("artist", {"id": artist_id})
    return cache.get_or_fetch(
        key,
        settings.CACHE_TTL_DETAIL,
        lambda: map_artist(jamendo.get_artist(artist_id)),
    )


def get_album(album_id: str) -> dict[str, Any]:
    key = cache.cache_key("album", {"id": album_id})
    return cache.get_or_fetch(
        key, settings.CACHE_TTL_DETAIL, lambda: map_album(jamendo.get_album(album_id))
    )
