"""Production settings — HTTPS, secure cookies, Sentry (all env-driven)."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import JWT_MIN_SECRET_BYTES, SECRET_KEY, env

DEBUG = False

# Fail fast: never boot production with a weak HS256 JWT signing key (FR-010).
if len(SECRET_KEY.encode()) < JWT_MIN_SECRET_BYTES:
    raise ImproperlyConfigured(
        f"DJANGO_SECRET_KEY must be at least {JWT_MIN_SECRET_BYTES} bytes "
        "for HS256 JWT signing in production."
    )

# HTTPS / security hardening
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# CORS allowlist (never "*" in production).
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# Error tracking (env-driven DSN; scrubs secrets/PII — core.observability).
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:  # pragma: no cover
    from core.observability import init_sentry

    init_sentry(SENTRY_DSN)
