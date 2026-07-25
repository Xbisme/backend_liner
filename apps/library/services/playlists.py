"""Playlist business logic (Constitution III/VII).

Pure data operations over owner-scoped models; views orchestrate hydration/response.
Ordering is kept stable and unique; reorder validates an exact permutation and
rewrites positions in two non-overlapping phases so it is safe under an immediate
``(playlist, position)`` unique constraint on both SQLite and PostgreSQL.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.library.models import Playlist, PlaylistTrack
from core.errors import ErrorCode
from core.exceptions import AppError

COVER_TRACK_LIMIT = 4


def create_playlist(user: Any, name: str) -> Playlist:
    return Playlist.objects.create(owner=user, name=name)


def rename_playlist(playlist: Playlist, name: str) -> Playlist:
    playlist.name = name
    playlist.save(update_fields=["name", "updated_at"])
    return playlist


def delete_playlist(playlist: Playlist) -> None:
    playlist.delete()  # cascades to PlaylistTrack


def _touch(playlist: Playlist) -> None:
    """Bump ``updated_at`` so content changes surface in recency ordering (FR-007)."""
    now = timezone.now()
    Playlist.objects.filter(pk=playlist.pk).update(updated_at=now)
    playlist.updated_at = now


def ordered_track_ids(playlist: Playlist) -> list[str]:
    return list(
        PlaylistTrack.objects.filter(playlist=playlist)
        .order_by("position")
        .values_list("track_id", flat=True)
    )


def add_track(playlist: Playlist, track_id: str) -> None:
    if PlaylistTrack.objects.filter(playlist=playlist, track_id=track_id).exists():
        raise AppError(ErrorCode.TRACK_ALREADY_IN_PLAYLIST)
    max_pos = PlaylistTrack.objects.filter(playlist=playlist).aggregate(
        m=Max("position")
    )["m"]
    next_pos = 0 if max_pos is None else max_pos + 1
    PlaylistTrack.objects.create(
        playlist=playlist, track_id=track_id, position=next_pos
    )
    _touch(playlist)


def remove_track(playlist: Playlist, track_id: str) -> None:
    deleted, _ = PlaylistTrack.objects.filter(
        playlist=playlist, track_id=track_id
    ).delete()
    if deleted:
        _touch(playlist)
    # Absent track → no-op, still idempotent 204 (FR-010).


def reorder(playlist: Playlist, track_ids: list[str]) -> None:
    rows = list(PlaylistTrack.objects.filter(playlist=playlist))
    if sorted(track_ids) != sorted(pt.track_id for pt in rows):
        # Missing/extra/duplicate ids relative to the current set.
        raise AppError(ErrorCode.REORDER_MISMATCH)
    by_id = {pt.track_id: pt for pt in rows}
    ordered = [by_id[tid] for tid in track_ids]
    offset = (max((pt.position for pt in rows), default=-1)) + 1
    with transaction.atomic():
        for idx, pt in enumerate(ordered):
            pt.position = offset + idx
        PlaylistTrack.objects.bulk_update(ordered, ["position"])
        for idx, pt in enumerate(ordered):
            pt.position = idx
        PlaylistTrack.objects.bulk_update(ordered, ["position"])
    _touch(playlist)


def cover_url_from_tracks(tracks: list[dict[str, Any]]) -> str | None:
    """First usable cover among the first ≤4 tracks (contract: null if empty)."""
    for track in tracks[:COVER_TRACK_LIMIT]:
        cover = track.get("cover_url")
        if cover:
            return str(cover)
    return None


def summary_dict(
    playlist: Playlist, *, track_count: int, cover_url: str | None
) -> dict[str, Any]:
    return {
        "id": playlist.id,
        "name": playlist.name,
        "track_count": track_count,
        "cover_url": cover_url,
        "created_at": playlist.created_at,
        "updated_at": playlist.updated_at,
    }


def detail_dict(playlist: Playlist, *, tracks: list[dict[str, Any]]) -> dict[str, Any]:
    data = summary_dict(
        playlist,
        track_count=len(tracks),
        cover_url=cover_url_from_tracks(tracks),
    )
    data["tracks"] = tracks
    return data
