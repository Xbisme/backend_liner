"""Canonical error-code catalog (Constitution Principle V).

Clients branch on ``code``; ``message`` is human/debug text only. Every code
maps to exactly one HTTP status here.
"""

from __future__ import annotations

from rest_framework import status


class ErrorCode:
    INVALID_APP_KEY = "INVALID_APP_KEY"
    UNAUTHORIZED_USER = "UNAUTHORIZED_USER"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    FORBIDDEN = "FORBIDDEN"
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    SOCIAL_TOKEN_INVALID = "SOCIAL_TOKEN_INVALID"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    TRACK_ALREADY_IN_PLAYLIST = "TRACK_ALREADY_IN_PLAYLIST"
    REORDER_MISMATCH = "REORDER_MISMATCH"
    CATALOG_UPSTREAM_ERROR = "CATALOG_UPSTREAM_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# code -> (http_status, default human message)
ERROR_MAP: dict[str, tuple[int, str]] = {
    ErrorCode.INVALID_APP_KEY: (
        status.HTTP_401_UNAUTHORIZED,
        "Missing or invalid app key.",
    ),
    ErrorCode.UNAUTHORIZED_USER: (
        status.HTTP_401_UNAUTHORIZED,
        "Authentication required.",
    ),
    ErrorCode.TOKEN_EXPIRED: (
        status.HTTP_401_UNAUTHORIZED,
        "Access token has expired.",
    ),
    ErrorCode.TOKEN_INVALID: (
        status.HTTP_401_UNAUTHORIZED,
        "Token is invalid or revoked.",
    ),
    ErrorCode.FORBIDDEN: (
        status.HTTP_403_FORBIDDEN,
        "You do not have access to this resource.",
    ),
    ErrorCode.EMAIL_ALREADY_EXISTS: (
        status.HTTP_409_CONFLICT,
        "Email is already registered.",
    ),
    ErrorCode.INVALID_CREDENTIALS: (
        status.HTTP_401_UNAUTHORIZED,
        "Invalid email or password.",
    ),
    ErrorCode.SOCIAL_TOKEN_INVALID: (
        status.HTTP_400_BAD_REQUEST,
        "Social identity token could not be verified.",
    ),
    ErrorCode.VALIDATION_ERROR: (
        status.HTTP_400_BAD_REQUEST,
        "Request validation failed.",
    ),
    ErrorCode.NOT_FOUND: (status.HTTP_404_NOT_FOUND, "Resource not found."),
    ErrorCode.TRACK_ALREADY_IN_PLAYLIST: (
        status.HTTP_409_CONFLICT,
        "Track already in playlist.",
    ),
    ErrorCode.REORDER_MISMATCH: (
        status.HTTP_400_BAD_REQUEST,
        "Reorder track_ids do not match playlist.",
    ),
    ErrorCode.CATALOG_UPSTREAM_ERROR: (
        status.HTTP_502_BAD_GATEWAY,
        "Upstream catalog error, retry shortly.",
    ),
    ErrorCode.INTERNAL_ERROR: (
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Internal server error.",
    ),
}


def status_for(code: str) -> int:
    return ERROR_MAP.get(code, ERROR_MAP[ErrorCode.INTERNAL_ERROR])[0]


def default_message_for(code: str) -> str:
    return ERROR_MAP.get(code, ERROR_MAP[ErrorCode.INTERNAL_ERROR])[1]
