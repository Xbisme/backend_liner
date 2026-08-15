"""Catalog reads are throttled per-IP (BE-004 US1, research R1)."""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.settings import api_settings
from rest_framework.test import APIClient


def _set_catalog_rate(settings: Any, rate: str) -> None:
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
            "catalog": rate,
        },
    }
    api_settings.reload()


@pytest.mark.django_db
def test_catalog_throttled_after_limit(
    api: APIClient, settings: Any, jamendo: Any
) -> None:
    _set_catalog_rate(settings, "3/min")
    codes = [api.get("/catalog/trending").status_code for _ in range(5)]
    assert codes.count(200) == 3
    assert codes[-1] == 429
    # Last call carries the canonical rate-limit envelope.
    resp = api.get("/catalog/trending")
    assert resp.status_code == 429
    assert resp.data["error"]["code"] == "RATE_LIMITED"
