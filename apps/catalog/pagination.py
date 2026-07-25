"""Opaque offset cursor for the proxied ``/catalog/tracks`` list (research §5).

Jamendo paginates by ``offset``/``limit``; the client sees only an opaque cursor.
Emits the same ``{items, next_cursor, has_more}`` envelope as
``core.pagination.CursorPage`` (which is DRF's DB-queryset cursor, unusable here).
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from core.errors import ErrorCode
from core.exceptions import AppError


def encode_cursor(offset: int) -> str:
    raw = json.dumps({"offset": offset}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(cursor: str | None) -> int:
    """Decode an opaque cursor to an offset. ``None``/empty → 0.

    Malformed cursor → ``VALIDATION_ERROR`` (never a 500 — spec Edge Case).
    """
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        offset = json.loads(raw)["offset"]
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Malformed cursor.") from exc
    if not isinstance(offset, int) or offset < 0:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Malformed cursor.")
    return offset


def build_page(
    items: list[Any], offset: int, limit: int, fullcount: int
) -> dict[str, Any]:
    """Assemble the cursor page. ``has_more`` when more rows remain upstream."""
    has_more = offset + len(items) < fullcount
    next_cursor = encode_cursor(offset + limit) if has_more else None
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}
