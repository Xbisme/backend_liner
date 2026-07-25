"""Listening-history business logic (Constitution III/VII).

History is a distinct "recently played" list: one row per (user, track_id), upserted
on each play, capped to ``HISTORY_MAX_ENTRIES`` newest entries per user (FR-016/017a).
"""

from __future__ import annotations

import datetime
from typing import Any

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from apps.library.models import ListeningHistory


def record(
    user: Any,
    track_id: str,
    *,
    played_at: datetime.datetime | None = None,
    completed: bool = False,
) -> None:
    ListeningHistory.objects.update_or_create(
        user=user,
        track_id=track_id,
        defaults={"played_at": played_at or timezone.now(), "completed": completed},
    )
    _trim(user)


def _trim(user: Any) -> None:
    """Keep only the newest ``HISTORY_MAX_ENTRIES`` rows for the user."""
    keep_ids = list(
        ListeningHistory.objects.filter(user=user)
        .order_by("-played_at", "-id")
        .values_list("id", flat=True)[: settings.HISTORY_MAX_ENTRIES]
    )
    ListeningHistory.objects.filter(user=user).exclude(id__in=keep_ids).delete()


def history_queryset(user: Any) -> QuerySet[ListeningHistory]:
    return ListeningHistory.objects.filter(user=user)
