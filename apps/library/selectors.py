"""Owner-scoped selectors — the IDOR boundary (Constitution I; research §6).

Authorization is derived from ``request.user`` only, never a client-supplied id.
A resource owned by another user raises ``FORBIDDEN`` (it exists but is not yours);
a truly non-existent id raises ``NOT_FOUND``.
"""

from __future__ import annotations

from apps.accounts.models import User
from apps.library.models import LikedTrack, Playlist
from core.errors import ErrorCode
from core.exceptions import AppError


def get_owned_playlist_or_error(user: User, playlist_id: int) -> Playlist:
    """Return the playlist iff it belongs to ``user``.

    Raises ``AppError(FORBIDDEN)`` if it exists but is owned by someone else,
    ``AppError(NOT_FOUND)`` if no playlist with that id exists at all.
    """
    playlist = Playlist.objects.filter(pk=playlist_id).first()
    if playlist is None:
        raise AppError(ErrorCode.NOT_FOUND)
    if playlist.owner_id != user.id:
        raise AppError(ErrorCode.FORBIDDEN)
    return playlist


def liked_track_ids(user: User, track_ids: list[str]) -> set[str]:
    """Subset of ``track_ids`` the user has liked — for per-response ``is_liked``."""
    if not track_ids:
        return set()
    return set(
        LikedTrack.objects.filter(user=user, track_id__in=track_ids).values_list(
            "track_id", flat=True
        )
    )
