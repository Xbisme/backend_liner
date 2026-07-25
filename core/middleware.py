"""X-App-Key gate (Constitution Principle I, Layer 1).

Runs ahead of DRF so a bad/absent key is rejected before body/auth processing.
Uses a constant-time compare to avoid timing side-channels.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

from core.errors import ErrorCode, default_message_for


class AppKeyMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not self._is_exempt(request.path):
            provided = request.headers.get("X-App-Key", "")
            expected = settings.X_APP_KEY
            if not expected or not hmac.compare_digest(provided, expected):
                return JsonResponse(
                    {
                        "error": {
                            "code": ErrorCode.INVALID_APP_KEY,
                            "message": default_message_for(ErrorCode.INVALID_APP_KEY),
                        }
                    },
                    status=401,
                )
        return self.get_response(request)

    @staticmethod
    def _is_exempt(path: str) -> bool:
        return any(
            path == prefix or path.startswith(prefix)
            for prefix in settings.APP_KEY_EXEMPT_PREFIXES
        )
