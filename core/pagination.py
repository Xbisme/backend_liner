"""Cursor pagination base returning {items, next_cursor, has_more}.

Foundation for BE-002/003 list endpoints; not used by BE-001 auth endpoints.
"""

from __future__ import annotations

from typing import Any

from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.utils.urls import remove_query_param, replace_query_param


class CursorPage(CursorPagination):
    page_size_query_param = "limit"
    ordering = "-id"
    cursor_query_param = "cursor"

    def _cursor_token(self, url: str | None) -> str | None:
        if url is None:
            return None
        # Extract the opaque cursor value from a DRF-built pagination URL.
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(url).query)
        values = qs.get(self.cursor_query_param)
        return values[0] if values else None

    def get_paginated_response(self, data: list[Any]) -> Response:
        next_cursor = self._cursor_token(self.get_next_link())
        return Response(
            {
                "items": data,
                "next_cursor": next_cursor,
                "has_more": next_cursor is not None,
            }
        )

    # Keep imports referenced for future link customization.
    _url_helpers = (replace_query_param, remove_query_param)
