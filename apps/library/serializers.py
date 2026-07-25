"""Library serializers — the contract-enforcement layer (Constitution II).

Egress serializers shape view-assembled dicts (playlist + hydrated tracks) to match
``contracts/openapi.yaml``. Ingress serializers validate request bodies.
"""

from __future__ import annotations

import datetime

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from apps.catalog.serializers import TrackSerializer


# --- Egress ------------------------------------------------------------------
class PlaylistSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    track_count = serializers.IntegerField()
    cover_url = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class PlaylistDetailSerializer(PlaylistSerializer):
    tracks = TrackSerializer(many=True)


class PlaylistCursorPageSerializer(serializers.Serializer):
    items = PlaylistSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)
    has_more = serializers.BooleanField()


# --- Ingress -----------------------------------------------------------------
class CreatePlaylistSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=settings.PLAYLIST_NAME_MAX_LENGTH)


class UpdatePlaylistSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=settings.PLAYLIST_NAME_MAX_LENGTH)


class AddTrackSerializer(serializers.Serializer):
    track_id = serializers.CharField(max_length=64)


class ReorderSerializer(serializers.Serializer):
    track_ids = serializers.ListField(
        child=serializers.CharField(max_length=64), allow_empty=True
    )


class LogHistorySerializer(serializers.Serializer):
    track_id = serializers.CharField(max_length=64)
    played_at = serializers.DateTimeField(required=False)
    completed = serializers.BooleanField(required=False, default=False)

    def validate_played_at(self, value: datetime.datetime) -> datetime.datetime:
        if value > timezone.now():
            raise serializers.ValidationError("played_at cannot be in the future.")
        return value
