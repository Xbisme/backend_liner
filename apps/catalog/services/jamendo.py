"""JamendoClient — the ONLY module that talks to Jamendo (Constitution IV).

Centralizes upstream access: injects the ``client_id`` (never exposed), uses an
explicit timeout, and translates every failure mode (timeout / transport error /
non-2xx / Jamendo ``status != success``) into ``AppError(CATALOG_UPSTREAM_ERROR)``.
Raw upstream errors/URLs are logged redacted, never returned to clients.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from django.conf import settings

from apps.catalog.constants import JAMENDO_TRACK_INCLUDE, JAMENDO_TRENDING_ORDER
from core.errors import ErrorCode
from core.exceptions import AppError

logger = logging.getLogger(__name__)

# Module-level httpx client (connection pooling). Tests inject a MockTransport-backed
# client by setting this attribute directly.
_HTTP: httpx.Client | None = None


def _http() -> httpx.Client:
    global _HTTP
    if _HTTP is None:
        _HTTP = httpx.Client(
            base_url=settings.JAMENDO_API_BASE_URL,
            timeout=settings.JAMENDO_REQUEST_TIMEOUT_SECONDS,
        )
    return _HTTP


def _base_params() -> dict[str, Any]:
    return {"client_id": settings.JAMENDO_CLIENT_ID, "format": "json"}


def _request(entity: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET ``/{entity}`` and return parsed JSON, or raise CATALOG_UPSTREAM_ERROR."""
    merged = {**_base_params(), **params}
    started = time.monotonic()
    try:
        response = _http().get(f"/{entity}", params=merged)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
    except httpx.HTTPStatusError as exc:
        # Context for diagnosis (FR-014): endpoint, status, latency — never the
        # URL (carries client_id) or raw body.
        logger.warning(
            "Jamendo upstream error on %s: status=%s latency=%.0fms",
            entity,
            exc.response.status_code,
            (time.monotonic() - started) * 1000,
        )
        raise AppError(ErrorCode.CATALOG_UPSTREAM_ERROR) from exc
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(
            "Jamendo upstream error on %s: %s latency=%.0fms",
            entity,
            type(exc).__name__,
            (time.monotonic() - started) * 1000,
        )
        raise AppError(ErrorCode.CATALOG_UPSTREAM_ERROR) from exc

    headers = payload.get("headers") or {}
    if headers.get("status") != "success":
        logger.warning(
            "Jamendo non-success on %s: upstream_status=%s latency=%.0fms",
            entity,
            headers.get("status"),
            (time.monotonic() - started) * 1000,
        )
        raise AppError(ErrorCode.CATALOG_UPSTREAM_ERROR)
    return payload


def _results(entity: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return _request(entity, params).get("results") or []


def list_tracks(
    *,
    search: str | None = None,
    tag: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """Return ``(results, fullcount)`` for a track browse/search query."""
    params: dict[str, Any] = {
        "limit": limit,
        "offset": offset,
        "fullcount": "true",
        "audioformat": settings.JAMENDO_AUDIOFORMAT,
        "include": JAMENDO_TRACK_INCLUDE,
    }
    if search:
        params["search"] = search
    if tag:
        params["tags"] = tag
    payload = _request("tracks", params)
    results = payload.get("results") or []
    fullcount = int(
        (payload.get("headers") or {}).get("results_fullcount", len(results))
    )
    return results, fullcount


def trending(*, tag: str | None = None, size: int = 50) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "limit": size,
        "order": JAMENDO_TRENDING_ORDER,
        "audioformat": settings.JAMENDO_AUDIOFORMAT,
        "include": JAMENDO_TRACK_INCLUDE,
    }
    if tag:
        params["tags"] = tag
    return _results("tracks", params)


def get_track(track_id: str) -> dict[str, Any]:
    return _get_one(
        "tracks",
        {
            "id": track_id,
            "audioformat": settings.JAMENDO_AUDIOFORMAT,
            "include": JAMENDO_TRACK_INCLUDE,
        },
    )


def list_tracks_by_ids(ids: list[str]) -> list[dict[str, Any]]:
    """Batch-fetch tracks by id in a single call (Jamendo multi-value ``id=1+2+3``).

    httpx encodes a space-joined value to ``id=1+2+3`` — the format Jamendo expects.
    Returns the raw results (order/completeness not guaranteed); the caller maps and
    fills tombstones for any requested id missing from the response. Empty input
    short-circuits with no upstream call.
    """
    if not ids:
        return []
    return _results(
        "tracks",
        {
            "id": " ".join(ids),
            "limit": len(ids),
            "audioformat": settings.JAMENDO_AUDIOFORMAT,
            "include": JAMENDO_TRACK_INCLUDE,
        },
    )


def get_artist(artist_id: str) -> dict[str, Any]:
    """Artist + its tracks (``/artists/tracks``: parent fields + nested tracks)."""
    return _get_one(
        "artists/tracks",
        {
            "id": artist_id,
            "audioformat": settings.JAMENDO_AUDIOFORMAT,
            "include": JAMENDO_TRACK_INCLUDE,
        },
    )


def get_artist_albums(artist_id: str) -> list[dict[str, Any]]:
    """The artist's albums (``/albums?artist_id=`` — each result is an album)."""
    return _results("albums", {"artist_id": artist_id})


def get_album(album_id: str) -> dict[str, Any]:
    """Album + its tracks (``/albums/tracks`` — parent album fields + nested tracks)."""
    return _get_one(
        "albums/tracks",
        {
            "id": album_id,
            "audioformat": settings.JAMENDO_AUDIOFORMAT,
            "include": JAMENDO_TRACK_INCLUDE,
        },
    )


def _get_one(entity: str, params: dict[str, Any]) -> dict[str, Any]:
    """Fetch a single resource by id; empty upstream result → NOT_FOUND."""
    results = _results(entity, params)
    if not results:
        raise AppError(ErrorCode.NOT_FOUND)
    return results[0]
