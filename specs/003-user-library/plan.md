# Implementation Plan: User Library

**Branch**: `BE-003-user-library` | **Date**: 2026-07-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-user-library/spec.md`

## Summary

Build `apps/library` — the user-owned side of SoundWave: playlists (CRUD + track add/remove/reorder), liked tracks (idempotent like/unlike), and listening history (distinct "recently played", capped). Every endpoint lives under `/me/*`, requires the two-tier auth already built in BE-001 (`X-App-Key` middleware + user JWT), and derives ownership **only** from `request.user` (IDOR-proof). The library stores **only `track_id` strings** — no song metadata — so list responses that must return full `Track` objects (liked, history, playlist detail) hydrate through a new public batch service in `apps/catalog` at read time, reusing the existing Redis cache. Tracks that no longer resolve upstream render as **tombstones** (`available: false`, null metadata); a global upstream failure surfaces `502 CATALOG_UPSTREAM_ERROR`.

The HTTP contract for `/me/*` already exists in `contracts/openapi.yaml` (paths + `Playlist`/`PlaylistDetail` + all request bodies). The **only contract change** is adding an `available` flag to `Track` and allowing its metadata fields to be null when `available=false` (FR-021) — a Contract-Sync item for mobile at freeze #000.

## Technical Context

**Language/Version**: Python 3.12+ · Django 5.2 + DRF 3.17 (existing stack, no version change)

**Primary Dependencies**: Existing only — DRF (`APIView`, serializers), `djangorestframework-simplejwt` (auth), `django-redis` (hydration cache). **No new dependency** (Constitution XIV satisfied by reuse).

**Storage**: PostgreSQL (prod) / sqlite (dev+test) for the four new library tables; Redis for catalog hydration cache (reused).

**Testing**: pytest + pytest-django + `factory_boy` + DRF `APIClient`; Jamendo mocked at the `apps.catalog.services.jamendo` boundary via the existing `httpx.MockTransport` fixtures.

**Target Platform**: Linux server (containerized), same as BE-001/002.

**Project Type**: Web service (backend API) — single Django project, domain apps.

**Performance Goals**: Personal-scale data (hundreds–few-thousand items/user). List reads do at most **one** batched upstream hydration call per page (≤ `limit` ids), served from cache on repeat. No N+1 upstream calls.

**Constraints**: No stored song metadata (hydrate at read); ownership from token only; uniform error envelope; all tunables env/settings-driven (no hardcoded page sizes, history cap, TTLs).

**Scale/Scope**: 4 models, ~13 `/me/*` endpoints (all already in contract), 1 new catalog hydration service + client method, 1 contract field addition.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| **I. Two-Tier Auth & IDOR** | All `/me/*` require `IsAuthenticated`; every queryset filtered by `request.user`; no client `user_id` trusted; cross-user → `403 FORBIDDEN`. | ✅ PASS — enforced via a shared owner-scoped selector + `get_object_or_404(owner=request.user)` pattern; dedicated IDOR tests (SC-001, SC-007). |
| **II. Contract-First** | Shapes match `openapi.yaml`; only additive `Track.available` change, updated in contract **before** code. | ✅ PASS — Phase 1 updates `openapi.yaml` + `api-context.md` + version note first. |
| **III. Layered Apps** | Thin views → serializers (validation) → `services/` (business logic) → models/selectors. `apps/library` calls `apps/catalog` only through a public service function, never internal imports. | ✅ PASS — hydration via `apps.catalog.services.catalog.get_tracks_by_ids(...)` public entrypoint. |
| **V. Consistent Errors** | Reuse `core.errors.ErrorCode` catalog + single handler; no new codes needed (`FORBIDDEN`, `NOT_FOUND`, `TRACK_ALREADY_IN_PLAYLIST`, `REORDER_MISMATCH`, `VALIDATION_ERROR`, `CATALOG_UPSTREAM_ERROR` all exist). | ✅ PASS — zero new error codes. |
| **VI. Config & Secrets** | `HISTORY_MAX_ENTRIES`, library page-size default/max as named settings; no magic numbers. | ✅ PASS — new settings constants in `config/settings/base.py`. |
| **VII. Data Integrity & Migrations** | Committed migrations; non-destructive; unique constraints (playlist/track, user/liked-track, user/history-track); explicit stable ordering (`position`; `updated_at,id`; `played_at,id`); cascade on `DELETE /me`. | ✅ PASS — see data-model.md. |
| **VIII. Security Hardening** | IDOR is the headline threat, covered by I. Rate-limiting `POST /me/history` deferred to BE-004 (noted). | ✅ PASS (rate-limit explicitly out of scope, documented). |
| **X. Code Quality & Typing** | black/ruff/mypy zero-warning; typed service/selector signatures; role-suffixed classes (`PlaylistSerializer`, `PlaylistViewSet`). | ✅ PASS — matches BE-002 conventions. |
| **XI. Testing Discipline** | Unit (services/selectors, hydration cache hit/miss, tombstone), auth/IDOR, contract shape, data rules (reorder mismatch, like idempotency, duplicate-in-playlist, cursor correctness, cascade). Jamendo mocked. | ✅ PASS — test matrix in quickstart.md. |
| **XII. Simplicity & YAGNI** | Reuse `core.pagination.CursorPage`, existing cache, existing error handler. No new abstractions beyond the batch hydration function a second consumer (library) now genuinely needs. | ✅ PASS. |
| **XIV. Dependency Hygiene** | No new packages. | ✅ PASS. |

**Result**: All gates pass. No entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/003-user-library/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions (hydration, ordering, tombstone, is_liked)
├── data-model.md        # Phase 1 — 4 models, constraints, migrations
├── quickstart.md        # Phase 1 — validation scenarios + test matrix
├── contracts/
│   └── library-endpoints.md   # Phase 1 — /me/* endpoint contract + Track.available delta
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
apps/library/                     # NEW app
├── __init__.py
├── apps.py
├── models.py                     # Playlist, PlaylistTrack, LikedTrack, ListeningHistory
├── selectors.py                  # owner-scoped querysets (IDOR boundary)
├── serializers.py                # Playlist(Detail), request bodies, Liked/History pages
├── services/
│   ├── __init__.py
│   ├── playlists.py              # create/rename/delete, add/remove/reorder track
│   ├── likes.py                  # like (idempotent), unlike, list
│   └── history.py                # record (upsert + cap), list
├── views.py                      # thin /me/* APIViews (IsAuthenticated)
├── urls.py                       # /me/playlists…, /me/liked-tracks…, /me/history
├── migrations/
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── conftest.py               # auth client, user factories
    ├── factories.py              # Playlist/PlaylistTrack/Liked/History factories
    ├── test_playlists.py         # CRUD + track add/remove/reorder + contract shape
    ├── test_playlists_idor.py    # user A vs user B — 403 across all playlist ops
    ├── test_liked_tracks.py      # like idempotency, unlike, list, IDOR
    ├── test_history.py           # upsert-distinct, cap, ordering, played_at validation, IDOR
    ├── test_hydration.py         # tombstone (missing id) + 502 (upstream down) + is_liked
    └── test_cascade.py           # DELETE /me removes all library rows

apps/catalog/                     # EXTEND (public hydration entrypoint)
├── services/jamendo.py           # + list_tracks_by_ids(ids) — batch id= fetch
├── services/catalog.py           # + get_tracks_by_ids(ids, liked_ids) — cache + tombstone + is_liked
├── services/mapper.py            # map_track adds available: True
└── serializers.py                # TrackSerializer: available field; metadata allow_null when unavailable

core/                             # (no change — reuse errors, exceptions, pagination, auth)
config/
├── settings/base.py              # + HISTORY_MAX_ENTRIES, LIBRARY_PAGE_SIZE_DEFAULT/MAX
└── urls.py                       # + include("apps.library.urls")
contracts/openapi.yaml            # + Track.available; metadata nullable when unavailable
.claude/api-context.md            # + Track.available note; contract version bump note
```

**Structure Decision**: New domain app `apps/library` mirroring the layout of `apps/accounts`/`apps/catalog` (models → selectors → serializers → services → thin views). Cross-app hydration goes through a **new public function on the existing catalog service** (`get_tracks_by_ids`), keeping `library`→`catalog` a one-way public-interface dependency (Constitution III) and reusing the catalog Redis cache rather than adding a parallel one.

## Phase 0 — Research

See [research.md](research.md). Key decisions (all spec clarifications already resolved; research records the *how*):

1. **Metadata hydration** — `apps/catalog` exposes `get_tracks_by_ids(ids, *, liked_ids)` that batch-fetches via Jamendo `id=` multi-value param (one call per page), caches per-id (reusing `CACHE_TTL_DETAIL`), returns Track dicts in requested order with `available` + `is_liked` set. Missing ids → tombstones. Any `CATALOG_UPSTREAM_ERROR` from the client propagates as 502 (global failure), distinct from per-id absence.
2. **DB cursor pagination for hydrated lists** — paginate the *model* queryset (`LikedTrack`/`ListeningHistory`/`Playlist`) with `core.pagination.CursorPage`, then hydrate only the page's `track_id`s. Stable ordering keys: playlists `(-updated_at, -id)`, liked `(-created_at, -id)`, history `(-played_at, -id)`.
3. **Reorder validation** — submitted `track_ids` must be a permutation of the playlist's exact current set → else `REORDER_MISMATCH`; applied as a bulk `position` rewrite in a transaction.
4. **History distinct + cap** — `(user, track_id)` unique; `POST` upserts `played_at`/`completed`; after write, trim to newest `HISTORY_MAX_ENTRIES`.
5. **is_liked** — computed per response from the user's liked-track set (batch membership), not stored on Track.

## Phase 1 — Design & Contracts

- **[data-model.md](data-model.md)** — the four models, fields, unique constraints, ordering, indexes, and the `0001_initial` migration shape; cascade wiring to `accounts.User`.
- **[contracts/library-endpoints.md](contracts/library-endpoints.md)** — every `/me/*` endpoint (method, auth, request/response, status + error codes) reconciled with `openapi.yaml`, plus the `Track.available` additive change and the exact `openapi.yaml`/`api-context.md` edits.
- **[quickstart.md](quickstart.md)** — end-to-end validation scenarios (create playlist → add/reorder → hydrate → tombstone → IDOR → cascade) and the full pytest matrix mapping to FRs/SCs.

**Post-Design Constitution re-check**: still all-pass — no new error codes, no new dependency, contract change is additive and documented, IDOR boundary centralized in `selectors.py`, all tunables in settings.

## Complexity Tracking

No constitution violations — table intentionally empty.
