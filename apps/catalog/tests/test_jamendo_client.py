"""Service tests for JamendoClient — failure translation + no credential leak.

The ``jamendo`` fixture is the mocked upstream; ``jclient`` is the module under test.
"""

from __future__ import annotations

import httpx
import pytest
from django.conf import settings

from apps.catalog.services import jamendo as jclient
from apps.catalog.tests.factories import envelope, track_result
from core.errors import ErrorCode
from core.exceptions import AppError


def test_timeout_becomes_upstream_error(jamendo):
    jamendo.raise_timeout()
    with pytest.raises(AppError) as exc:
        jclient.trending()
    assert exc.value.code == ErrorCode.CATALOG_UPSTREAM_ERROR


def test_5xx_becomes_upstream_error(jamendo):
    jamendo.respond_json({"headers": {"status": "failed"}}, status_code=503)
    with pytest.raises(AppError) as exc:
        jclient.trending()
    assert exc.value.code == ErrorCode.CATALOG_UPSTREAM_ERROR


def test_rate_limit_429_becomes_upstream_error(jamendo):
    jamendo.respond_json({"headers": {"status": "failed"}}, status_code=429)
    with pytest.raises(AppError) as exc:
        jclient.list_tracks()
    assert exc.value.code == ErrorCode.CATALOG_UPSTREAM_ERROR


def test_status_failed_envelope_becomes_upstream_error(jamendo):
    # HTTP 200 but Jamendo signals failure in the body.
    jamendo.respond_json(envelope([], status="failed"))
    with pytest.raises(AppError) as exc:
        jclient.list_tracks()
    assert exc.value.code == ErrorCode.CATALOG_UPSTREAM_ERROR


def test_detail_empty_results_is_not_found(jamendo):
    jamendo.respond_json(envelope([]))
    with pytest.raises(AppError) as exc:
        jclient.get_track("nope")
    assert exc.value.code == ErrorCode.NOT_FOUND


def test_client_id_never_leaks_in_error(jamendo):
    jamendo.raise_timeout()
    with pytest.raises(AppError) as exc:
        jclient.trending()
    assert settings.JAMENDO_CLIENT_ID not in str(exc.value)


def test_client_id_sent_upstream_but_not_in_results(jamendo):
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["client_id"] = request.url.params.get("client_id")
        return httpx.Response(200, json=envelope([track_result()], fullcount=1))

    jamendo.respond(handler)
    results, fullcount = jclient.list_tracks()
    assert seen["client_id"] == settings.JAMENDO_CLIENT_ID  # injected upstream
    assert fullcount == 1
    assert "client_id" not in results[0]  # never in the payload we forward
