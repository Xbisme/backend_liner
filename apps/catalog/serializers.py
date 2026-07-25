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
    title = serializers.CharField(allow_blank=True)
    artist = ArtistSerializer()
    album = AlbumSerializer()
    genres = GenreSerializer(many=True)
    duration_seconds = serializers.IntegerField()
    cover_url = serializers.CharField(allow_blank=True)
    stream_url = serializers.CharField(allow_blank=True)
    license_type = serializers.CharField(allow_blank=True)
    is_liked = serializers.BooleanField()


class TrackCursorPageSerializer(serializers.Serializer):
    items = TrackSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)
    has_more = serializers.BooleanField()
