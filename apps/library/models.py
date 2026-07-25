"""User-library models (Constitution VII).

Every row is owned by ``accounts.User`` (FK ``CASCADE``) so ``DELETE /me`` removes
all library data with no orphans. Only the Jamendo ``track_id`` string is stored —
never song metadata (FR-004); full ``Track`` objects are hydrated at read time.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

TRACK_ID_MAX_LENGTH = 64


class Playlist(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="playlists",
    )
    name = models.CharField(max_length=settings.PLAYLIST_NAME_MAX_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "library_playlist"
        ordering = ["-updated_at", "-id"]
        indexes = [models.Index(fields=["owner", "-updated_at", "-id"])]

    def __str__(self) -> str:
        return f"{self.name} (user#{self.owner_id})"


class PlaylistTrack(models.Model):
    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name="tracks",
    )
    track_id = models.CharField(max_length=TRACK_ID_MAX_LENGTH)
    position = models.PositiveIntegerField()
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "library_playlist_track"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["playlist", "track_id"], name="uniq_playlist_track"
            ),
            models.UniqueConstraint(
                fields=["playlist", "position"], name="uniq_playlist_position"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.track_id}@{self.position} (pl#{self.playlist_id})"


class LikedTrack(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="liked_tracks",
    )
    track_id = models.CharField(max_length=TRACK_ID_MAX_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "library_liked_track"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "track_id"], name="uniq_user_liked_track"
            )
        ]
        indexes = [models.Index(fields=["user", "-created_at", "-id"])]

    def __str__(self) -> str:
        return f"{self.track_id} liked by user#{self.user_id}"


class ListeningHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="history",
    )
    track_id = models.CharField(max_length=TRACK_ID_MAX_LENGTH)
    played_at = models.DateTimeField()
    completed = models.BooleanField(default=False)

    class Meta:
        db_table = "library_listening_history"
        ordering = ["-played_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "track_id"], name="uniq_user_history_track"
            )
        ]
        indexes = [models.Index(fields=["user", "-played_at", "-id"])]

    def __str__(self) -> str:
        return f"{self.track_id} played by user#{self.user_id}"
