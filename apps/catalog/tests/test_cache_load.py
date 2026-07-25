"""Cache-hit shields the upstream from load (BE-004 FR-017/SC-005).

Deterministic stand-in for a load test: many identical reads must NOT scale
upstream calls linearly — the cache serves repeats. No live Jamendo (Constitution
XI); the mock counts calls.
"""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_repeated_reads_hit_cache_not_upstream(api: APIClient, jamendo: Any) -> None:
    n_requests = 30
    codes = [api.get("/catalog/trending").status_code for _ in range(n_requests)]

    assert codes == [200] * n_requests
    # The first request misses (1 upstream call); the rest are served from cache.
    assert jamendo.calls == 1


@pytest.mark.django_db
def test_upstream_errors_are_not_cached(api: APIClient, jamendo: Any) -> None:
    jamendo.raise_timeout()
    assert api.get("/catalog/trending").status_code == 502

    # Recovery: a later success is fetched fresh (the error was never cached).
    jamendo.respond_json({"headers": {"status": "success"}, "results": []})
    assert api.get("/catalog/trending").status_code == 200
    assert jamendo.calls == 2
