from django.urls import path

from apps.library.views import (
    HistoryView,
    LikedTrackDetailView,
    LikedTracksView,
    PlaylistDetailView,
    PlaylistListCreateView,
    PlaylistReorderView,
    PlaylistTrackDeleteView,
    PlaylistTracksView,
)

urlpatterns = [
    path("me/history", HistoryView.as_view(), name="history"),
    path("me/liked-tracks", LikedTracksView.as_view(), name="liked-tracks"),
    path(
        "me/liked-tracks/<track_id>",
        LikedTrackDetailView.as_view(),
        name="liked-track-detail",
    ),
    path("me/playlists", PlaylistListCreateView.as_view(), name="playlists"),
    path(
        "me/playlists/<int:playlist_id>",
        PlaylistDetailView.as_view(),
        name="playlist-detail",
    ),
    path(
        "me/playlists/<int:playlist_id>/tracks",
        PlaylistTracksView.as_view(),
        name="playlist-tracks",
    ),
    # 'reorder' must precede the <track_id> route so it isn't captured as a track id.
    path(
        "me/playlists/<int:playlist_id>/tracks/reorder",
        PlaylistReorderView.as_view(),
        name="playlist-reorder",
    ),
    path(
        "me/playlists/<int:playlist_id>/tracks/<track_id>",
        PlaylistTrackDeleteView.as_view(),
        name="playlist-track-delete",
    ),
]
