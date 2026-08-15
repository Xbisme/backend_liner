"""Rate-limit throttles (Constitution VIII, BE-004).

Scope → identity mapping (see specs/004-security-hardening/data-model.md):

- ``auth``       → per-IP, **fail-closed** (never open brute-force protection).
- ``catalog``    → per-IP (X-App-Key is a shared secret, unusable as a per-caller
                   bucket — research R1), fail-open.
- ``user_write`` → per-user, fail-open. Applied to write ``/me/*`` methods only.
- ``history``    → per-user, fail-open, higher rate (rapid skips log many plays).

Rates come from ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`` (env-driven,
Constitution VI). When the counter store (Redis) is unavailable, functional
throttles fail open (don't block legitimate users) while auth fails closed.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from django.core.exceptions import ImproperlyConfigured
from redis.exceptions import RedisError
from rest_framework.request import Request
from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# Errors that mean "the throttle counter store is unreachable" (FR-006a).
_CACHE_ERRORS: tuple[type[BaseException], ...] = (RedisError, ConnectionError, OSError)

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class _ResilientThrottle(SimpleRateThrottle):
    """Base throttle with fail-open / fail-closed handling on store outage."""

    fail_open: bool = True

    def get_rate(self) -> str | None:
        # Resolve the rate from live settings rather than the import-time snapshot
        # baked into ``SimpleRateThrottle.THROTTLE_RATES`` (keeps rates correct
        # after a settings reload in tests; harmless in production where static).
        if not getattr(self, "scope", None):
            return None
        rates: dict[str, Any] = api_settings.DEFAULT_THROTTLE_RATES
        if self.scope not in rates:
            raise ImproperlyConfigured(
                f"No throttle rate configured for scope '{self.scope}'."
            )
        return cast("str | None", rates[self.scope])

    def allow_request(self, request: Request, view: APIView) -> bool:
        try:
            return super().allow_request(request, view)
        except _CACHE_ERRORS as exc:
            logger.warning(
                "Throttle store unavailable (%s); scope=%s fail_open=%s",
                exc.__class__.__name__,
                self.scope,
                self.fail_open,
            )
            if self.fail_open:
                return True
            # Fail closed: block, but seed ``history`` so ``wait()`` is safe.
            self.history = []
            return False


class _IpScopedThrottle(_ResilientThrottle):
    """Keyed on the client IP (proxy-aware via DRF ``NUM_PROXIES``)."""

    def get_cache_key(self, request: Request, view: APIView) -> str | None:
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class _UserScopedThrottle(_ResilientThrottle):
    """Keyed on the authenticated user; anonymous requests are not throttled here."""

    def get_cache_key(self, request: Request, view: APIView) -> str | None:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": user.pk}


class AuthRateThrottle(_IpScopedThrottle):
    """Per-IP throttle for unauthenticated auth endpoints (brute-force guard)."""

    scope = "auth"
    fail_open = False


class CatalogRateThrottle(_IpScopedThrottle):
    """Per-IP throttle for catalog reads (protects Jamendo quota beyond cache)."""

    scope = "catalog"
    fail_open = True


class UserWriteRateThrottle(_UserScopedThrottle):
    """Per-user throttle for write ``/me/*`` operations."""

    scope = "user_write"
    fail_open = True


class HistoryRateThrottle(_UserScopedThrottle):
    """Per-user throttle for ``POST /me/history`` (higher rate)."""

    scope = "history"
    fail_open = True


class WriteThrottleMixin:
    """Apply ``write_throttle`` to mutating methods only; reads stay unthrottled."""

    write_throttle: type[SimpleRateThrottle] = UserWriteRateThrottle

    def get_throttles(self) -> list[Any]:
        request = getattr(self, "request", None)
        if request is not None and request.method in _WRITE_METHODS:
            return [self.write_throttle()]
        return []
