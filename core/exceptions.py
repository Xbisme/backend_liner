"""AppError + the single DRF exception handler that renders the error envelope.

Every error response is ``{"error": {"code", "message"}}`` (Principle V).
"""

from __future__ import annotations

from typing import Any

from django.http import Http404
from rest_framework import exceptions as drf_exc
from rest_framework.response import Response

from core.errors import ErrorCode, default_message_for, status_for


class AppError(Exception):
    """Raise anywhere to produce a catalog error response."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or default_message_for(code)
        super().__init__(self.message)


def _envelope(code: str, message: str, http_status: int) -> Response:
    return Response({"error": {"code": code, "message": message}}, status=http_status)


def _validation_message(detail: Any) -> str:
    """Flatten a DRF ValidationError detail into one human string."""
    if isinstance(detail, dict):
        parts = []
        for field, msgs in detail.items():
            text = msgs[0] if isinstance(msgs, list) and msgs else msgs
            parts.append(f"{field}: {text}")
        return (
            "; ".join(parts)
            if parts
            else default_message_for(ErrorCode.VALIDATION_ERROR)
        )
    if isinstance(detail, list) and detail:
        return str(detail[0])
    return str(detail)


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    # 1. Our own typed errors.
    if isinstance(exc, AppError):
        return _envelope(exc.code, exc.message, status_for(exc.code))

    # 2. Map well-known DRF/Django exceptions to catalog codes.
    if isinstance(exc, drf_exc.ValidationError):
        return _envelope(
            ErrorCode.VALIDATION_ERROR,
            _validation_message(exc.detail),
            status_for(ErrorCode.VALIDATION_ERROR),
        )
    if isinstance(exc, drf_exc.NotAuthenticated):
        return _envelope(
            ErrorCode.UNAUTHORIZED_USER,
            default_message_for(ErrorCode.UNAUTHORIZED_USER),
            status_for(ErrorCode.UNAUTHORIZED_USER),
        )
    if isinstance(exc, drf_exc.AuthenticationFailed):
        return _envelope(
            ErrorCode.TOKEN_INVALID,
            default_message_for(ErrorCode.TOKEN_INVALID),
            status_for(ErrorCode.TOKEN_INVALID),
        )
    if isinstance(exc, drf_exc.PermissionDenied):
        return _envelope(
            ErrorCode.FORBIDDEN,
            default_message_for(ErrorCode.FORBIDDEN),
            status_for(ErrorCode.FORBIDDEN),
        )
    if isinstance(exc, (drf_exc.NotFound, Http404)):
        return _envelope(
            ErrorCode.NOT_FOUND,
            default_message_for(ErrorCode.NOT_FOUND),
            status_for(ErrorCode.NOT_FOUND),
        )

    # 3. Let DRF build a response for anything else it knows (405, throttled…).
    #    Imported lazily to avoid a circular import at DRF settings-init time.
    from rest_framework.views import exception_handler as drf_exception_handler

    response = drf_exception_handler(exc, context)
    if response is not None:
        detail = getattr(exc, "detail", str(exc))
        code = getattr(exc, "default_code", ErrorCode.INTERNAL_ERROR)
        message = detail if isinstance(detail, str) else _validation_message(detail)
        return _envelope(str(code).upper(), message, response.status_code)

    # 4. Unhandled → generic 500 (never leak internals).
    return _envelope(
        ErrorCode.INTERNAL_ERROR,
        default_message_for(ErrorCode.INTERNAL_ERROR),
        status_for(ErrorCode.INTERNAL_ERROR),
    )
