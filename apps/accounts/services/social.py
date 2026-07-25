"""Social sign-in: verify provider token, then resolve-or-create the account.

Verification is isolated in ``verify_google`` / ``verify_apple`` so tests mock
``verify_social_token`` at this boundary (no live network — Principle XI).
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import transaction

from apps.accounts.models import SocialIdentity, User
from core.errors import ErrorCode
from core.exceptions import AppError


def verify_google(id_token_str: str) -> dict[str, Any]:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    try:
        info = google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID
        )
    except Exception as exc:  # noqa: BLE001 - any failure = invalid token
        raise AppError(ErrorCode.SOCIAL_TOKEN_INVALID) from exc
    if not info.get("sub"):
        raise AppError(ErrorCode.SOCIAL_TOKEN_INVALID)
    return {"provider": "google", "subject_id": info["sub"], "email": info.get("email")}


def verify_apple(id_token_str: str) -> dict[str, Any]:
    import jwt

    try:
        jwks_client = jwt.PyJWKClient(settings.APPLE_KEYS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token_str)
        info = jwt.decode(
            id_token_str,
            signing_key.key,
            algorithms=["ES256"],
            audience=settings.APPLE_CLIENT_ID,
            issuer=settings.APPLE_ISSUER,
        )
    except Exception as exc:  # noqa: BLE001 - any failure = invalid token
        raise AppError(ErrorCode.SOCIAL_TOKEN_INVALID) from exc
    if not info.get("sub"):
        raise AppError(ErrorCode.SOCIAL_TOKEN_INVALID)
    return {"provider": "apple", "subject_id": info["sub"], "email": info.get("email")}


_VERIFIERS = {"google": verify_google, "apple": verify_apple}


def verify_social_token(provider: str, id_token_str: str) -> dict[str, Any]:
    verifier = _VERIFIERS.get(provider)
    if verifier is None:  # pragma: no cover - provider validated by serializer
        raise AppError(ErrorCode.SOCIAL_TOKEN_INVALID)
    return verifier(id_token_str)


@transaction.atomic
def resolve_or_create_account(verified: dict[str, Any]) -> User:
    provider = verified["provider"]
    subject_id = verified["subject_id"]
    email = verified.get("email")
    normalized = email.lower() if email else None

    # 1. Known provider identity → reuse its account.
    identity = (
        SocialIdentity.objects.select_related("user")
        .filter(provider=provider, subject_id=subject_id)
        .first()
    )
    if identity is not None:
        return identity.user

    # 2. Verified email matches an existing account → auto-link.
    user: User | None = None
    if normalized:
        user = User.objects.filter(email=normalized).first()

    # 3. Otherwise create a new account (email may be None).
    if user is None:
        display_name = (
            normalized.split("@")[0] if normalized else f"{provider.title()} User"
        )
        user = User.objects.create_user(
            email=normalized, password=None, display_name=display_name
        )

    SocialIdentity.objects.create(
        user=user, provider=provider, subject_id=subject_id, email_at_provider=email
    )
    return user


def social_login(provider: str, id_token_str: str) -> User:
    verified = verify_social_token(provider, id_token_str)
    return resolve_or_create_account(verified)
