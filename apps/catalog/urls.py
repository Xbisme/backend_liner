from django.urls import path

from apps.catalog.views import (
    AlbumDetailView,
    ArtistDetailView,
    GenresView,
    TrackDetailView,
    TracksView,
    TrendingView,
)

urlpatterns = [
    path("catalog/trending", TrendingView.as_view(), name="catalog-trending"),
    path("catalog/genres", GenresView.as_view(), name="catalog-genres"),
    path("catalog/tracks", TracksView.as_view(), name="catalog-tracks"),
    path(
        "catalog/tracks/<str:track_id>",
        TrackDetailView.as_view(),
        name="catalog-track-detail",
    ),
    path(
        "catalog/artists/<str:artist_id>",
        ArtistDetailView.as_view(),
        name="catalog-artist-detail",
    ),
    path(
        "catalog/albums/<str:album_id>",
        AlbumDetailView.as_view(),
        name="catalog-album-detail",
    ),
]
