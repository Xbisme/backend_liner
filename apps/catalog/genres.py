"""Curated genre vocabulary helpers (research §6).

Genres are served from ``settings.CATALOG_GENRES`` — Jamendo has no genre-list
endpoint. The internal ``tag`` (Jamendo filter value) is never exposed to clients.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

from core.errors import ErrorCode
from core.exceptions import AppError


def _genres() -> list[dict[str, str]]:
    return settings.CATALOG_GENRES


def list_genres() -> list[dict[str, str]]:
    """Public genre list: ``[{slug, name}]`` (no internal ``tag``)."""
    return [{"slug": g["slug"], "name": g["name"]} for g in _genres()]


def slug_to_tag(slug: str | None) -> str | None:
    """Map a public genre ``slug`` to its Jamendo ``tag``.

    ``None``/empty → ``None`` (no filter). An unknown slug → ``VALIDATION_ERROR``
    (never silently ignored — spec Edge Case).
    """
    if not slug:
        return None
    for g in _genres():
        if g["slug"] == slug:
            return g["tag"]
    raise AppError(ErrorCode.VALIDATION_ERROR, f"Unknown genre: {slug}")


def tag_lookup() -> dict[str, dict[str, str]]:
    """``{tag: {slug, name}}`` for mapping per-track Jamendo tags to curated genres."""
    return {g["tag"]: {"slug": g["slug"], "name": g["name"]} for g in _genres()}


def genres_from_tags(tags: Any) -> list[dict[str, str]]:
    """Map a track's raw Jamendo genre tags to curated ``[{slug,name}]``.

    Unknown tags are dropped; non-list input yields ``[]`` (missing-field safety).
    """
    if not isinstance(tags, (list, tuple)):
        return []
    lookup = tag_lookup()
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for tag in tags:
        entry = lookup.get(tag)
        if entry and entry["slug"] not in seen:
            seen.add(entry["slug"])
            out.append(entry)
    return out
