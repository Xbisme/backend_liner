"""Tests for the catalog cache helper (get_or_fetch, key namespacing)."""

from __future__ import annotations

import pytest

from apps.catalog.services import cache
from core.exceptions import AppError


def test_cache_key_namespaced_and_param_sensitive():
    k1 = cache.cache_key("tracks", {"search": "a", "offset": 0})
    k2 = cache.cache_key("tracks", {"search": "b", "offset": 0})
    assert k1.startswith("catalog:v1:tracks:")
    assert k1 != k2  # different params → different key


def test_get_or_fetch_miss_then_hit_calls_fn_once():
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        return "value"

    key = cache.cache_key("tracks", {"q": "once"})
    assert cache.get_or_fetch(key, 60, fn) == "value"
    assert cache.get_or_fetch(key, 60, fn) == "value"
    assert calls["n"] == 1  # second call served from cache


def test_failure_is_not_cached():
    def boom() -> str:
        raise AppError("CATALOG_UPSTREAM_ERROR")

    key = cache.cache_key("tracks", {"q": "boom"})
    with pytest.raises(AppError):
        cache.get_or_fetch(key, 60, boom)
    # A subsequent successful fetch under the same key works (nothing was cached).
    assert cache.get_or_fetch(key, 60, lambda: "ok") == "ok"
