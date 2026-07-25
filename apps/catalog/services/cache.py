"""Cache helper for catalog responses (Constitution IV).

Caches the *mapped* result (contract dicts) — never raw upstream JSON. Keys are
namespaced and include every parameter that affects the result. Upstream failures
are not cached (``get_or_fetch`` only stores what ``fn`` returns successfully).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from django.core.cache import cache

from apps.catalog.constants import CACHE_NAMESPACE


def cache_key(resource: str, params: dict[str, Any]) -> str:
    """``catalog:v1:<resource>:<sha1(sorted params)>`` (Principle IV)."""
    blob = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha1(blob.encode()).hexdigest()
    return f"{CACHE_NAMESPACE}:{resource}:{digest}"


def get_or_fetch[T](key: str, ttl: int, fn: Callable[[], T]) -> T:
    """Return the cached value for ``key`` or compute+store it for ``ttl`` seconds.

    ``fn`` is only invoked on a miss; if it raises (e.g. upstream error) nothing is
    cached, so failures are never persisted.
    """
    cached = cache.get(key)
    if cached is not None:
        return cached  # type: ignore[no-any-return]
    value = fn()
    cache.set(key, value, ttl)
    return value
