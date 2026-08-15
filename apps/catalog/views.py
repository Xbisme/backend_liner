"""Thin catalog views — delegate to services + serializers (Principle III).

Auth is Layer-1 only: ``X-App-Key`` is enforced globally by ``AppKeyMiddleware``;
no user token is required (public content). Errors flow through the shared handler.
"""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog import genres as genre_helper
from apps.catalog.serializers import (
    AlbumDetailSerializer,
    ArtistDetailSerializer,
    GenreSerializer,
    TrackCursorPageSerializer,
    TrackSerializer,
)
from apps.catalog.services import catalog
from core.throttling import CatalogRateThrottle


class TrendingView(APIView):
    throttle_classes = [CatalogRateThrottle]

    def get(self, request: Request) -> Response:
        genre = request.query_params.get("genre")
        tracks = catalog.trending(genre_slug=genre)
        return Response(TrackSerializer(tracks, many=True).data)


class GenresView(APIView):
    throttle_classes = [CatalogRateThrottle]

    def get(self, request: Request) -> Response:
        return Response(GenreSerializer(genre_helper.list_genres(), many=True).data)


class TracksView(APIView):
    throttle_classes = [CatalogRateThrottle]

    def get(self, request: Request) -> Response:
        page = catalog.list_tracks(
            search=request.query_params.get("search"),
            genre_slug=request.query_params.get("genre"),
            cursor=request.query_params.get("cursor"),
            limit=request.query_params.get("limit"),
        )
        return Response(TrackCursorPageSerializer(page).data)


class TrackDetailView(APIView):
    throttle_classes = [CatalogRateThrottle]

    def get(self, request: Request, track_id: str) -> Response:
        return Response(TrackSerializer(catalog.get_track(track_id)).data)


class ArtistDetailView(APIView):
    throttle_classes = [CatalogRateThrottle]

    def get(self, request: Request, artist_id: str) -> Response:
        return Response(ArtistDetailSerializer(catalog.get_artist(artist_id)).data)


class AlbumDetailView(APIView):
    throttle_classes = [CatalogRateThrottle]

    def get(self, request: Request, album_id: str) -> Response:
        return Response(AlbumDetailSerializer(catalog.get_album(album_id)).data)
