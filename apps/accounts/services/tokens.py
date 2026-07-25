"""JWT issue / refresh (rotating) / revoke via SimpleJWT."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.errors import ErrorCode
from core.exceptions import AppError

User = get_user_model()


def _expires_in() -> int:
    lifetime = cast(timedelta, settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"])
    return int(lifetime.total_seconds())


def issue_tokens(user: Any) -> dict[str, Any]:
    refresh = RefreshToken.for_user(user)
    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "expires_in": _expires_in(),
    }


def refresh_tokens(raw_refresh: str) -> tuple[Any, dict[str, Any]]:
    """Rotate a refresh token; returns (user, token dict). Invalid → TOKEN_INVALID."""
    try:
        # simplejwt accepts a str token here (stub types it narrowly).
        refresh = RefreshToken(raw_refresh)  # type: ignore[arg-type]
    except TokenError as exc:
        raise AppError(ErrorCode.TOKEN_INVALID) from exc

    access = str(refresh.access_token)

    # Rotation: blacklist the presented token, then re-issue.
    if settings.SIMPLE_JWT.get("BLACKLIST_AFTER_ROTATION"):
        try:
            refresh.blacklist()
        except AttributeError:  # pragma: no cover - blacklist app always on
            pass
    refresh.set_jti()
    refresh.set_exp()
    refresh.set_iat()

    try:
        user = User.objects.get(pk=refresh["user_id"])
    except User.DoesNotExist as exc:
        raise AppError(ErrorCode.TOKEN_INVALID) from exc

    return user, {
        "access_token": access,
        "refresh_token": str(refresh),
        "expires_in": _expires_in(),
    }


def revoke(raw_refresh: str) -> None:
    try:
        RefreshToken(raw_refresh).blacklist()  # type: ignore[arg-type]
    except TokenError as exc:
        raise AppError(ErrorCode.TOKEN_INVALID) from exc


def revoke_all(user: Any) -> None:
    """Blacklist every outstanding refresh token for a user (logout-everywhere)."""
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
