"""Liked-tracks business logic (Constitution III). Like/unlike are idempotent."""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from apps.library.models import LikedTrack


def like(user: Any, track_id: str) -> None:
    """Idempotent — re-liking an existing track is a no-op (FR-013)."""
    LikedTrack.objects.get_or_create(user=user, track_id=track_id)


def unlike(user: Any, track_id: str) -> None:
    """Idempotent — unliking a track that isn't liked is a no-op (FR-014)."""
    LikedTrack.objects.filter(user=user, track_id=track_id).delete()


def liked_queryset(user: Any) -> QuerySet[LikedTrack]:
    return LikedTrack.objects.filter(user=user)
