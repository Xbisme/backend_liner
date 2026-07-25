# Quickstart & Validation: User Library (BE-003)

How to prove `apps/library` works end-to-end. Implementation bodies live in the code / `tasks.md`; this is the run-and-verify guide.

## Prerequisites

- BE-001 + BE-002 merged (auth, catalog, `core/*`). Same virtualenv / `requirements/dev.txt`.
- No new dependency. No external service at test time — Jamendo is mocked at the `apps.catalog.services.jamendo` boundary (reuse BE-002's `httpx.MockTransport` fixtures in `apps/catalog/tests/conftest.py`).

## Setup

```bash
# after implementing models
python manage.py makemigrations library
python manage.py makemigrations --check --dry-run   # must be clean
python manage.py migrate
```

## Pre-commit gate (Constitution / dev-workflow §4)

```bash
black .
ruff check .
mypy .
pytest
python manage.py makemigrations --check --dry-run
```

## End-to-end validation scenario (happy path + IDOR + tombstone)

Drive with DRF `APIClient`, `X-App-Key` + Bearer set. Two users A and B.

1. **Create + list** — `POST /me/playlists {name:"Chill"}` → `201`, `track_count:0`, `cover_url:null`. `GET /me/playlists` → the playlist appears; owned by A only.
2. **Add tracks** — `POST /me/playlists/{id}/tracks {track_id:"1"}`, then `"2"`, `"3"` → each `204`, appended in order. Re-add `"2"` → `409 TRACK_ALREADY_IN_PLAYLIST`.
3. **Detail hydrates** — `GET /me/playlists/{id}` → `200 PlaylistDetail`, `tracks` in `[1,2,3]` order with full metadata from mocked Jamendo; `is_liked` reflects A's likes.
4. **Reorder** — `PATCH …/tracks/reorder {track_ids:["3","1","2"]}` → `200`, order now `[3,1,2]`. Submit `["3","1"]` (missing one) → `400 REORDER_MISMATCH`; order unchanged.
5. **Remove** — `DELETE …/tracks/2` → `204`; removing `"999"` (absent) → `204` (idempotent).
6. **updated_at ordering** — create a 2nd playlist, then add a track to the 1st; `GET /me/playlists` → 1st now sorts first (recency bump).
7. **Likes** — `POST /me/liked-tracks/5` → `204`; again → `204` (idempotent, no dup). `GET /me/liked-tracks` → item `5`, `is_liked:true`. `DELETE /me/liked-tracks/5` → `204`; list empty. `DELETE` again → `204`.
8. **History distinct + cap** — `POST /me/history {track_id:"7", played_at:<t1>}` then again with `<t2>` → still **one** row for `7`, `played_at=t2`. `GET /me/history` → distinct, newest-first. Log > `HISTORY_MAX_ENTRIES` distinct tracks → oldest trimmed. `POST` with future `played_at` → `400 VALIDATION_ERROR`.
9. **Tombstone** — playlist contains `track_id` the mocked upstream returns no result for → `GET` detail returns that item with `available:false`, metadata null; other tracks intact; **no** 502.
10. **Global upstream failure** — mock Jamendo to raise (timeout/5xx) → hydrated list endpoints return `502 CATALOG_UPSTREAM_ERROR` (whole response), not tombstones.
11. **IDOR** — B calls `GET/PATCH/DELETE /me/playlists/{A's id}` and `…/tracks…` → `403 FORBIDDEN` every time; A's data unchanged, not leaked. Sending `user_id` of A in B's body changes nothing.
12. **Cascade** — `DELETE /me` (user A) → `204`; assert zero `Playlist/PlaylistTrack/LikedTrack/ListeningHistory` rows remain for A.

## Test matrix (pytest — Constitution XI) → requirement mapping

| Test module | Covers | FR / SC |
|---|---|---|
| `test_playlists.py` | CRUD, add/remove/reorder, 409 dup, 400 reorder-mismatch, contract shape, updated_at ordering | FR-006..012, SC-002, SC-006 |
| `test_playlists_idor.py` | A↔B on every playlist + track op → 403; `user_id` spoof ignored | FR-001/002, SC-001, SC-007 |
| `test_liked_tracks.py` | like idempotent, unlike-absent 204, list `is_liked:true`, IDOR, pagination | FR-013..015, SC-003, SC-004 |
| `test_history.py` | upsert-distinct, cap trim, `played_at` desc, future→400, IDOR | FR-016..018, SC-004 |
| `test_hydration.py` | batch fetch one call/page, cache hit/miss, tombstone (missing id), 502 (upstream down), `is_liked` set | FR-004/004a, SC-006 |
| `test_cascade.py` | `DELETE /me` removes all library rows, no orphans | FR-019, SC-005 |

Jamendo is mocked in every test; suite stays deterministic and network-free. IDOR and hydration-error paths are the highest-risk and are covered explicitly.

## Contract sync check

After editing `contracts/openapi.yaml` (`Track.available`) confirm:
- `.claude/api-context.md` Track example + note updated in the same change.
- `changelog.md` entry added; flag Contract Sync with `soundwave-mobile` at freeze #000.
- Response bodies from the new endpoints validate against the updated schemas (shape asserted in the `test_*` modules).
