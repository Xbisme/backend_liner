"""Hydration path tests for get_tracks_by_ids (BE-003, Constitution IV/XI).

Covers: one upstream call per page, cache reuse, tombstone for unresolved ids,
502 on global upstream failure, and per-user is_liked. Jamendo is mocked.
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.catalog.services import cache
from apps.catalog.services.catalog import get_tracks_by_ids
from core.errors import ErrorCode
from core.exceptions import AppError

pytestmark = pytest.mark.django_db


def _raw(track_id: str) -> dict[str, Any]:
    return {
        "id": track_id,
        "name": f"Track {track_id}",
        "artist_id": "9",
        "artist_name": "Artist",
        "album_id": "5",
        "album_name": "Album",
        "duration": 100,
        "image": f"https://img/{track_id}.jpg",
        "audio": f"https://audio/{track_id}.mp3",
        "license_ccurl": "http://creativecommons.org/licenses/by-nc-sa/3.0/",
    }


def _success(tracks: list[dict[str, Any]]) -> dict[str, Any]:
    return {"headers": {"status": "success"}, "results": tracks}


def test_hydrates_in_order_one_call(jamendo: Any) -> None:
    jamendo.respond_json(_success([_raw("3"), _raw("1"), _raw("2")]))

    out = get_tracks_by_ids(["1", "2", "3"])

    assert [t["id"] for t in out] == [
        "1",
        "2",
        "3",
    ]  # order follows request, not upstream
    assert all(t["available"] for t in out)
    assert jamendo.calls == 1  # single batched call for the page


def test_cache_reuse_skips_second_call(jamendo: Any) -> None:
    jamendo.respond_json(_success([_raw("1"), _raw("2")]))

    get_tracks_by_ids(["1", "2"])
    get_tracks_by_ids(["1", "2"])  # fully cached now

    assert jamendo.calls == 1


def test_partial_cache_only_fetches_misses(jamendo: Any) -> None:
    # Warm id "1" via the shared per-id track cache key.
    cache.cache.set(
        cache.cache_key("track", {"id": "1"}), {"id": "1", "available": True}
    )
    jamendo.respond_json(_success([_raw("2")]))

    out = get_tracks_by_ids(["1", "2"])

    assert jamendo.calls == 1
    assert {t["id"] for t in out} == {"1", "2"}


def test_missing_id_becomes_tombstone(jamendo: Any) -> None:
    jamendo.respond_json(_success([_raw("1")]))  # id "2" absent from upstream

    out = {t["id"]: t for t in get_tracks_by_ids(["1", "2"])}

    assert out["1"]["available"] is True
    assert out["2"]["available"] is False
    assert out["2"]["title"] is None and out["2"]["stream_url"] is None


def test_global_upstream_failure_raises_502(jamendo: Any) -> None:
    jamendo.raise_timeout()

    with pytest.raises(AppError) as exc:
        get_tracks_by_ids(["1", "2"])
    assert exc.value.code == ErrorCode.CATALOG_UPSTREAM_ERROR


def test_is_liked_set_from_liked_ids(jamendo: Any) -> None:
    jamendo.respond_json(_success([_raw("1"), _raw("2")]))

    out = {t["id"]: t for t in get_tracks_by_ids(["1", "2"], liked_ids={"1"})}

    assert out["1"]["is_liked"] is True
    assert out["2"]["is_liked"] is False


def test_empty_ids_no_call(jamendo: Any) -> None:
    assert get_tracks_by_ids([]) == []
    assert jamendo.calls == 0
