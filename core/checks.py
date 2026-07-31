"""Deploy-time system checks (Constitution VIII, BE-004 FR-010).

The JWT is signed with ``SECRET_KEY`` (SimpleJWT default, HS256), so a short key
weakens every token. ``check_jwt_signing_key`` surfaces this via
``manage.py check --deploy``; ``config.settings.production`` additionally fails
fast at boot using :func:`signing_key_too_short`.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import Error, Tags, register

DEFAULT_MIN_SECRET_BYTES = 32


def signing_key_too_short(secret_key: str, min_bytes: int) -> bool:
    """True when the HS256 signing key is below the recommended byte length."""
    return len(secret_key.encode()) < min_bytes


@register(Tags.security, deploy=True)
def check_jwt_signing_key(app_configs: Any, **kwargs: Any) -> list[Error]:
    if settings.DEBUG:
        return []
    min_bytes = getattr(settings, "JWT_MIN_SECRET_BYTES", DEFAULT_MIN_SECRET_BYTES)
    if signing_key_too_short(settings.SECRET_KEY, min_bytes):
        return [
            Error(
                f"SECRET_KEY (the HS256 JWT signing key) is shorter than "
                f"{min_bytes} bytes.",
                hint="Set a longer DJANGO_SECRET_KEY in the environment.",
                id="core.E001",
            )
        ]
    return []
