"""Egress serializers — the contract-enforcement layer (Constitution II/IV).

Fields are explicit and match ``contracts/openapi.yaml``. Serializing through these
guarantees no raw upstream key ever leaks: only the declared fields are emitted.
Input is the mapped dicts produced by ``services/mapper.py``.
"""

from __future__ import annotations

from rest_framework import serializers


class ArtistSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField(allow_blank=True)
    image_url = serializers.CharField(allow_blank=True)


class AlbumSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    artist = ArtistSerializer()
    cover_url = serializers.CharField(allow_blank=True)


class GenreSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()


class TrackSerializer(serializers.Serializer):
    id = serializers.CharField()
    # available=false → "tombstone": metadata below is null (BE-003). Catalog
    # endpoints always emit available=true with full metadata.
    available = serializers.BooleanField(default=True)
    title = serializers.CharField(allow_blank=True, allow_null=True)
    artist = ArtistSerializer(allow_null=True)
    album = AlbumSerializer(allow_null=True)
    genres = GenreSerializer(many=True)
    duration_seconds = serializers.IntegerField(allow_null=True)
    cover_url = serializers.CharField(allow_blank=True, allow_null=True)
    stream_url = serializers.CharField(allow_blank=True, allow_null=True)
    license_type = serializers.CharField(allow_blank=True, allow_null=True)
    is_liked = serializers.BooleanField()


class TrackCursorPageSerializer(serializers.Serializer):
    items = TrackSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)
    has_more = serializers.BooleanField()


class AlbumDetailSerializer(AlbumSerializer):
    """Album + its tracks (GET /catalog/albums/{id}, contract v0.2.0)."""

    tracks = TrackSerializer(many=True)


class ArtistDetailSerializer(ArtistSerializer):
    """Artist + its tracks and albums (GET /catalog/artists/{id}, contract v0.2.0)."""

    tracks = TrackSerializer(many=True)
    albums = AlbumSerializer(many=True)
