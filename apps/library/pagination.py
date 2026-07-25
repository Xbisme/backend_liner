"""Keyset cursor paginators for the owned library lists (Constitution VII).

Unlike the catalog's offset cursor (an index into an upstream list), these paginate
DB querysets by a stable ordered key so pages never skip/duplicate under concurrent
writes. ``limit`` is clamped to ``LIBRARY_PAGE_SIZE_MAX`` (FR-003) and a malformed
cursor surfaces ``VALIDATION_ERROR`` (400) — parity with ``apps/catalog/pagination``.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from rest_framework.exceptions import NotFound
from rest_framework.request import Request

from core.errors import ErrorCode
from core.exceptions import AppError
from core.pagination import CursorPage


class LibraryCursorPage(CursorPage):
    # DRF CursorPagination accepts a tuple ordering at runtime; the stub types it
    # as ``str`` only, so widen it here to keep the subclass orderings type-clean.
    ordering: Any = "-id"
    page_size = settings.LIBRARY_PAGE_SIZE_DEFAULT
    max_page_size = settings.LIBRARY_PAGE_SIZE_MAX

    def paginate_queryset(
        self, queryset: Any, request: Request, view: Any = None
    ) -> list[Any] | None:
        try:
            return super().paginate_queryset(queryset, request, view)
        except NotFound as exc:
            # DRF raises NotFound (404) for an undecodable cursor; the contract
            # wants a 400 VALIDATION_ERROR (spec edge case).
            raise AppError(ErrorCode.VALIDATION_ERROR, "Malformed cursor.") from exc


class PlaylistCursorPage(LibraryCursorPage):
    ordering = ("-updated_at", "-id")


class LikedTrackCursorPage(LibraryCursorPage):
    ordering = ("-created_at", "-id")


class HistoryCursorPage(LibraryCursorPage):
    ordering = ("-played_at", "-id")
