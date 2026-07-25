from __future__ import annotations

import factory
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.library.models import (
    LikedTrack,
    ListeningHistory,
    Playlist,
    PlaylistTrack,
)


class PlaylistFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Playlist

    owner = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Playlist {n}")


class PlaylistTrackFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PlaylistTrack

    playlist = factory.SubFactory(PlaylistFactory)
    track_id = factory.Sequence(lambda n: str(1000 + n))
    position = factory.Sequence(lambda n: n)


class LikedTrackFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LikedTrack

    user = factory.SubFactory(UserFactory)
    track_id = factory.Sequence(lambda n: str(2000 + n))


class ListeningHistoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ListeningHistory

    user = factory.SubFactory(UserFactory)
    track_id = factory.Sequence(lambda n: str(3000 + n))
    played_at = factory.LazyFunction(timezone.now)
    completed = True
