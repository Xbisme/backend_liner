"""JWT authentication that emits precise catalog codes.

SimpleJWT collapses all token problems into ``InvalidToken``; we split them into
TOKEN_EXPIRED vs TOKEN_INVALID (missing token → handled as UNAUTHORIZED_USER by
the permission layer). See spec FR-010.
"""

from __future__ import annotations

from typing import Any

from rest_framework_simplejwt.authentication import (
    JWTAuthentication as BaseJWTAuthentication,
)
from rest_framework_simplejwt.exceptions import InvalidToken

from core.errors import ErrorCode
from core.exceptions import AppError


class JWTAuthentication(BaseJWTAuthentication):
    def get_validated_token(self, raw_token: bytes) -> Any:
        try:
            return super().get_validated_token(raw_token)
        except InvalidToken as exc:
            if _looks_expired(exc):
                raise AppError(ErrorCode.TOKEN_EXPIRED) from exc
            raise AppError(ErrorCode.TOKEN_INVALID) from exc


def _looks_expired(exc: InvalidToken) -> bool:
    detail = getattr(exc, "detail", "")
    messages = ""
    if isinstance(detail, dict):
        messages = str(detail.get("messages", "")) + str(detail.get("detail", ""))
    else:
        messages = str(detail)
    return "expired" in messages.lower()
