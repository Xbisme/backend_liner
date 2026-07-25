"""Thin ``/me/*`` library views (Constitution I/III).

Every view requires a user JWT and scopes data to ``request.user`` — ownership is
never taken from the request body. Business logic lives in ``services/``; catalog
metadata is hydrated through the public ``catalog.get_tracks_by_ids`` entrypoint.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, cast

from django.db.models import Count
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.catalog.serializers import TrackSerializer
from apps.catalog.services import catalog
from apps.library import selectors
from apps.library.models import Playlist, PlaylistTrack
from apps.library.pagination import (
    HistoryCursorPage,
    LikedTrackCursorPage,
    PlaylistCursorPage,
)
from apps.library.serializers import (
    AddTrackSerializer,
    CreatePlaylistSerializer,
    LogHistorySerializer,
    PlaylistDetailSerializer,
    PlaylistSerializer,
    ReorderSerializer,
    UpdatePlaylistSerializer,
)
from apps.library.services import history as history_service
from apps.library.services import likes as like_service
from apps.library.services import playlists as playlist_service

COVER_TRACK_LIMIT = playlist_service.COVER_TRACK_LIMIT


def _user(request: Request) -> User:
    """Narrow ``request.user`` to the concrete model (IsAuthenticated guarantees it)."""
    return cast(User, request.user)


class PlaylistListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qs = Playlist.objects.filter(owner=_user(request)).annotate(
            track_count_ann=Count("tracks")
        )
        paginator = PlaylistCursorPage()
        page = paginator.paginate_queryset(qs, request, view=self)
        assert page is not None

        # One query for the page's first-≤4 track_ids (cover art), grouped in Python.
        first_ids = _first_track_ids([pl.id for pl in page])
        hydrated = {
            t["id"]: t
            for t in catalog.get_tracks_by_ids(
                [tid for ids in first_ids.values() for tid in ids]
            )
        }
        summaries = [
            playlist_service.summary_dict(
                pl,
                track_count=pl.track_count_ann,
                cover_url=playlist_service.cover_url_from_tracks(
                    [hydrated[tid] for tid in first_ids.get(pl.id, [])]
                ),
            )
            for pl in page
        ]
        return paginator.get_paginated_response(
            list(PlaylistSerializer(summaries, many=True).data)
        )

    def post(self, request: Request) -> Response:
        serializer = CreatePlaylistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        playlist = playlist_service.create_playlist(
            _user(request), serializer.validated_data["name"]
        )
        return Response(
            PlaylistSerializer(
                playlist_service.summary_dict(playlist, track_count=0, cover_url=None)
            ).data,
            status=status.HTTP_201_CREATED,
        )


class PlaylistDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, playlist_id: int) -> Response:
        playlist = selectors.get_owned_playlist_or_error(_user(request), playlist_id)
        return Response(_detail_payload(request, playlist))

    def patch(self, request: Request, playlist_id: int) -> Response:
        playlist = selectors.get_owned_playlist_or_error(_user(request), playlist_id)
        serializer = UpdatePlaylistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        playlist = playlist_service.rename_playlist(
            playlist, serializer.validated_data["name"]
        )
        track_count = PlaylistTrack.objects.filter(playlist=playlist).count()
        return Response(
            PlaylistSerializer(
                playlist_service.summary_dict(
                    playlist, track_count=track_count, cover_url=None
                )
            ).data
        )

    def delete(self, request: Request, playlist_id: int) -> Response:
        playlist = selectors.get_owned_playlist_or_error(_user(request), playlist_id)
        playlist_service.delete_playlist(playlist)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlaylistTracksView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, playlist_id: int) -> Response:
        playlist = selectors.get_owned_playlist_or_error(_user(request), playlist_id)
        serializer = AddTrackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        playlist_service.add_track(playlist, serializer.validated_data["track_id"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlaylistTrackDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, playlist_id: int, track_id: str) -> Response:
        playlist = selectors.get_owned_playlist_or_error(_user(request), playlist_id)
        playlist_service.remove_track(playlist, track_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlaylistReorderView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, playlist_id: int) -> Response:
        playlist = selectors.get_owned_playlist_or_error(_user(request), playlist_id)
        serializer = ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        playlist_service.reorder(playlist, serializer.validated_data["track_ids"])
        return Response(_detail_payload(request, playlist))


class LikedTracksView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        paginator = LikedTrackCursorPage()
        page = paginator.paginate_queryset(
            like_service.liked_queryset(_user(request)), request, view=self
        )
        assert page is not None
        track_ids = [row.track_id for row in page]
        tracks = catalog.get_tracks_by_ids(track_ids, liked_ids=set(track_ids))
        return paginator.get_paginated_response(
            list(TrackSerializer(tracks, many=True).data)
        )


class LikedTrackDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, track_id: str) -> Response:
        like_service.like(_user(request), track_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request: Request, track_id: str) -> Response:
        like_service.unlike(_user(request), track_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class HistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        paginator = HistoryCursorPage()
        page = paginator.paginate_queryset(
            history_service.history_queryset(_user(request)), request, view=self
        )
        assert page is not None
        track_ids = [row.track_id for row in page]
        liked = selectors.liked_track_ids(_user(request), track_ids)
        tracks = catalog.get_tracks_by_ids(track_ids, liked_ids=liked)
        return paginator.get_paginated_response(
            list(TrackSerializer(tracks, many=True).data)
        )

    def post(self, request: Request) -> Response:
        serializer = LogHistorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        history_service.record(
            _user(request),
            data["track_id"],
            played_at=data.get("played_at"),
            completed=data["completed"],
        )
        return Response(status=status.HTTP_201_CREATED)


def _detail_payload(request: Request, playlist: Playlist) -> dict[str, Any]:
    track_ids = playlist_service.ordered_track_ids(playlist)
    liked = selectors.liked_track_ids(_user(request), track_ids)
    tracks = catalog.get_tracks_by_ids(track_ids, liked_ids=liked)
    return PlaylistDetailSerializer(
        playlist_service.detail_dict(playlist, tracks=tracks)
    ).data


def _first_track_ids(playlist_ids: list[int]) -> dict[int, list[str]]:
    """Map playlist id → its first ≤COVER_TRACK_LIMIT track_ids, in one query."""
    grouped: dict[int, list[str]] = defaultdict(list)
    rows = (
        PlaylistTrack.objects.filter(playlist_id__in=playlist_ids)
        .order_by("playlist_id", "position")
        .values_list("playlist_id", "track_id")
    )
    for pid, tid in rows:
        if len(grouped[pid]) < COVER_TRACK_LIMIT:
            grouped[pid].append(tid)
    return grouped
