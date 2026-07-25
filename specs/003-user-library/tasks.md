---
description: "Task list for BE-003 User Library implementation"
---

# Tasks: User Library

**Input**: Design documents from `specs/003-user-library/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/library-endpoints.md](contracts/library-endpoints.md), [quickstart.md](quickstart.md)

**Tests**: INCLUDED — Constitution XI mandates auth/IDOR + contract + data-rule tests; quickstart.md defines the matrix. Jamendo is mocked at the `apps.catalog.services.jamendo` boundary (reuse BE-002 fixtures).

**Organization**: Grouped by user story (P1 Playlists → P2 Liked → P3 History). Setup + Foundational block all stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 = Playlists, US2 = Liked Tracks, US3 = Listening History
- Exact file paths included per task

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the `apps/library` app and wire it into the project.

- [X] T001 Create `apps/library/` package skeleton (`__init__.py`, `apps.py` with `LibraryConfig`, `services/__init__.py`, `migrations/__init__.py`, `tests/__init__.py`) mirroring `apps/catalog` layout
- [X] T002 Register `"apps.library"` in `INSTALLED_APPS` and add `path("", include("apps.library.urls"))` in `config/urls.py` (create an empty `apps/library/urls.py` with `urlpatterns = []` so the include resolves)
- [X] T003 [P] Add library settings constants in `config/settings/base.py` (`HISTORY_MAX_ENTRIES=100`, `LIBRARY_PAGE_SIZE_DEFAULT=20`, `LIBRARY_PAGE_SIZE_MAX=50`, `PLAYLIST_NAME_MAX_LENGTH=200`), all `env`-driven per data-model.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contract change, data layer, IDOR boundary, and the shared catalog hydration path used by every story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Contract-first (must precede code — Constitution II)

- [X] T004 [P] In `contracts/openapi.yaml`: (a) add `available` (boolean, default true) + make `Track` metadata fields `nullable` per contracts/library-endpoints.md; (b) **fix I1** — make `LogHistoryRequest.played_at` optional (`required: [track_id]` only), reconciling the contract with FR-016 (server defaults `played_at` to now when absent)
- [X] T005 [P] Mirror both changes in `.claude/api-context.md` (Track `available`/tombstone note + updated Track JSON example; note `played_at` optional on `POST /me/history`) and add a changelog entry in `.claude/changelog.md` (flag Contract Sync with mobile at freeze #000)

### Data layer

- [X] T006 Define the four models (`Playlist`, `PlaylistTrack`, `LikedTrack`, `ListeningHistory`) with fields, `Meta` (db_table, ordering, unique constraints, indexes) in `apps/library/models.py` per data-model.md
- [X] T007 Generate `apps/library/migrations/0001_initial.py` via `makemigrations library`; verify `makemigrations --check --dry-run` is clean (depends on T006)
- [X] T008 [P] Implement owner-scoped selectors in `apps/library/selectors.py` — `get_owned_playlist_or_error(user, id)` returns playlist if owner, raises `AppError(FORBIDDEN)` if another user's, `AppError(NOT_FOUND)` if absent (Constitution I; research §6)
- [X] T009 [P] Add per-endpoint cursor paginators in `apps/library/pagination.py` subclassing `core.pagination.CursorPage` — `PlaylistCursorPage` (`ordering=("-updated_at","-id")`), `LikedTrackCursorPage` (`("-created_at","-id")`), `HistoryCursorPage` (`("-played_at","-id")`); **fix U2** — set `page_size = settings.LIBRARY_PAGE_SIZE_DEFAULT` and `max_page_size = settings.LIBRARY_PAGE_SIZE_MAX` on each so `?limit=` is clamped to 50 (FR-003); ensure a malformed cursor surfaces `VALIDATION_ERROR` (400) parity with catalog

### Shared hydration path (catalog extension — used by US1/US2/US3)

- [X] T010 [P] `map_track` sets `"available": True` in `apps/catalog/services/mapper.py`
- [X] T011 [P] `TrackSerializer` gains `available = BooleanField(default=True)` and metadata fields become `allow_null=True` in `apps/catalog/serializers.py`
- [X] T012 [P] Add `list_tracks_by_ids(ids: list[str])` batch method (Jamendo multi-value `id=` param, same include/audioformat) in `apps/catalog/services/jamendo.py`
- [X] T013 Add public `get_tracks_by_ids(ids, *, liked_ids)` in `apps/catalog/services/catalog.py` — per-id cache reuse (`CACHE_TTL_DETAIL`, existing `track` key), batch only cache-misses via T012, preserve order, emit tombstones for unresolved ids, set `is_liked` from `liked_ids`; global upstream failure propagates `CATALOG_UPSTREAM_ERROR` (depends T010, T012)

### Test infrastructure + hydration tests

- [X] T014 [P] Create `apps/library/tests/conftest.py` (authenticated `APIClient` with `X-App-Key`+Bearer, users A and B) and `apps/library/tests/factories.py` (`PlaylistFactory`, `PlaylistTrackFactory`, `LikedTrackFactory`, `ListeningHistoryFactory`)
- [X] T015 [P] Hydration unit tests in `apps/catalog/tests/test_hydration.py` — one upstream call per page, cache hit/miss, tombstone for missing id, `502` on global upstream failure, `is_liked` set from `liked_ids` (mocks Jamendo)

**Checkpoint**: Contract updated, tables migrated, IDOR selector + hydration ready — user stories can begin.

---

## Phase 3: User Story 1 — Quản lý playlist cá nhân (Priority: P1) 🎯 MVP

**Goal**: Full playlist lifecycle — create, list, detail (hydrated, ordered), rename, delete, add/remove/reorder tracks — all owner-scoped.

**Independent Test**: Two users each create playlists, add/remove/reorder tracks; each only accesses their own (cross-user → 403); track order preserved across reads; duplicate add → 409; bad reorder → 400.

### Tests for User Story 1 ⚠️ (write first, ensure they fail)

- [X] T016 [P] [US1] `apps/library/tests/test_playlists.py` — create (201, empty), list (recency order), detail (hydrated in order + is_liked), rename, delete, add (204/append), duplicate add → `TRACK_ALREADY_IN_PLAYLIST` (409), remove (204, and 204 when absent), reorder (200), reorder mismatch → `REORDER_MISMATCH` (400), response shape vs `openapi.yaml`
- [X] T017 [P] [US1] `apps/library/tests/test_playlists_idor.py` — user B on A's playlist + track ops → `403 FORBIDDEN` on every verb; `user_id` in body ignored

### Implementation for User Story 1

- [X] T018 [P] [US1] Playlist serializers in `apps/library/serializers.py` — `PlaylistSerializer` (id, name, `track_count`, `cover_url` from first ≤4 hydrated covers/null, timestamps), `PlaylistDetailSerializer` (+`tracks`), and request serializers `CreatePlaylistSerializer`/`UpdatePlaylistSerializer` (name non-blank, max `PLAYLIST_NAME_MAX_LENGTH`), `AddTrackSerializer`, `ReorderSerializer`. **U1** — `cover_url` is populated by the view (from the page's batched hydration), not by a per-object upstream call inside the serializer
- [X] T019 [US1] Playlist service in `apps/library/services/playlists.py` — create/rename/delete; add_track (append at `max(position)+1`, dup pre-check → `TRACK_ALREADY_IN_PLAYLIST`); remove_track (idempotent 204); reorder (validate exact permutation → `REORDER_MISMATCH`, rewrite positions in `transaction.atomic()`); bump `Playlist.updated_at` on every track mutation; detail hydration via `catalog.get_tracks_by_ids`. **fix L2** — avoid transient `(playlist, position)` unique collisions on reorder via a deferrable constraint (Postgres `DEFERRABLE INITIALLY DEFERRED`) or a two-phase position write; a reorder test must assert no IntegrityError (depends T006, T008, T013)
- [X] T020 [US1] Playlist views (`IsAuthenticated`, thin) in `apps/library/views.py` — list/create, detail/patch/delete, tracks add/remove/reorder. **fix U1** — for `GET /me/playlists`, collect the first ≤4 `track_id`s across every playlist in the page into ONE `catalog.get_tracks_by_ids` call, then compose each `cover_url` from its hydrated covers (keeps ≤1 upstream call/page); for detail/hydrated lists compute `liked_ids` for the page before hydration (depends T018, T019)
- [X] T021 [US1] Wire `/me/playlists`, `/me/playlists/<int:id>`, `/me/playlists/<int:id>/tracks`, `/me/playlists/<int:id>/tracks/reorder`, `/me/playlists/<int:id>/tracks/<track_id>` in `apps/library/urls.py`

**Checkpoint**: US1 fully functional and independently testable — this is the MVP.

---

## Phase 4: User Story 2 — Bài hát yêu thích (Priority: P2)

**Goal**: Like (idempotent), unlike (idempotent), and list liked tracks (hydrated, all `is_liked:true`).

**Independent Test**: Like a track → appears in liked list; like again → 204 no dup; unlike → gone; unlike absent → 204; A's likes never visible to B.

### Tests for User Story 2 ⚠️

- [X] T022 [P] [US2] `apps/library/tests/test_liked_tracks.py` — like 204 + idempotent, unlike 204 (incl. not-liked), list `TrackCursorPage` (`is_liked:true`, recency order, cursor pagination), IDOR isolation

### Implementation for User Story 2

- [X] T023 [US2] Likes service in `apps/library/services/likes.py` — `like` = `get_or_create` (204 either way), `unlike` = filtered delete (204 either way), `list_liked` returns owner-scoped queryset for pagination
- [X] T024 [US2] Liked-tracks views in `apps/library/views.py` — `GET` (paginate via `LikedTrackCursorPage`, hydrate page with `is_liked=True`), `POST`/`DELETE` `/me/liked-tracks/<track_id>` (depends T023, T013)
- [X] T025 [US2] Add `/me/liked-tracks` and `/me/liked-tracks/<track_id>` routes in `apps/library/urls.py`

**Checkpoint**: US1 + US2 both independently functional.

---

## Phase 5: User Story 3 — Lịch sử nghe (Priority: P3)

**Goal**: Record listens (distinct per track via upsert, capped) and list recently played (hydrated, `played_at` desc).

**Independent Test**: Log a track twice → one row, latest `played_at`; list is distinct newest-first; exceeding cap trims oldest; future `played_at` → 400; A's history isolated from B.

### Tests for User Story 3 ⚠️

- [X] T026 [P] [US3] `apps/library/tests/test_history.py` — POST upsert-distinct (201), cap trim to `HISTORY_MAX_ENTRIES`, GET `played_at` desc + cursor pagination, future/invalid `played_at` → `VALIDATION_ERROR` (400), IDOR isolation

### Implementation for User Story 3

- [X] T027 [US3] History service in `apps/library/services/history.py` — `record` = `update_or_create` on `(user, track_id)` setting `played_at` (default `timezone.now()`)/`completed`, then trim to newest `settings.HISTORY_MAX_ENTRIES`; `list_history` owner-scoped queryset
- [X] T028 [US3] `LogHistorySerializer` (reject future/invalid `played_at`) in `apps/library/serializers.py` + history views in `apps/library/views.py` — `POST` (201), `GET` (paginate via `HistoryCursorPage`, hydrate page) (depends T027, T013)
- [X] T029 [US3] Add `/me/history` route in `apps/library/urls.py`

**Checkpoint**: All three stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T030 [P] `apps/library/tests/test_cascade.py` — `DELETE /me` removes all `Playlist`/`PlaylistTrack`/`LikedTrack`/`ListeningHistory` rows for the user; assert zero orphans (SC-005)
- [X] T031 Run pre-commit gate: `black .`, `ruff check .`, `mypy .`, `pytest`, `makemigrations --check --dry-run` — all green (dev-workflow §4)
- [X] T032 Execute quickstart.md validation scenarios 1–12 end-to-end against the running app
- [X] T033 [P] Update `.claude/changelog.md` (BE-003 done entry), `.claude/sdd-roadmap.md` + `.claude/project-context.md` (BE-003 status), and confirm the `Track.available` contract note is consistent across `openapi.yaml` + `api-context.md`

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)** → no deps.
- **Foundational (P2)** → after Setup; **blocks all stories**. Within P2: T006→T007; T010/T012→T013; contract (T004/T005), selectors (T008), pagination (T009), serializer (T011), test infra (T014), hydration tests (T015) are otherwise parallel.
- **US1 (P3)** → after Foundational. **MVP.**
- **US2 (P4)**, **US3 (P5)** → after Foundational; independent of US1 in logic, but share `views.py`/`urls.py`/`serializers.py` files created in US1 (sequential edits, not parallel across stories).
- **Polish (P6)** → after the desired stories.

### Story independence

- US1/US2/US3 are logically independent (different models, different endpoints) and each independently testable. File-level: US2/US3 append to the same `apps/library/views.py`, `urls.py`, `serializers.py` as US1 — do these sequentially (no `[P]` across stories on those files).

### Parallel opportunities

- Setup: T003 ∥ others.
- Foundational: T004 ∥ T005 ∥ T008 ∥ T009 ∥ T010 ∥ T011 ∥ T012 ∥ T014 ∥ T015 (then T013 after T010+T012; T007 after T006).
- Within a story: the two test files / test file vs. serializer are `[P]`.

---

## Parallel Example: Foundational hydration slice

```bash
# After T006/T007 (models+migration), run these together:
Task: "T008 owner-scoped selectors in apps/library/selectors.py"
Task: "T010 map_track available:True in apps/catalog/services/mapper.py"
Task: "T012 list_tracks_by_ids in apps/catalog/services/jamendo.py"
Task: "T011 TrackSerializer.available + allow_null in apps/catalog/serializers.py"
# then:
Task: "T013 get_tracks_by_ids in apps/catalog/services/catalog.py"  # needs T010+T012
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational (contract + data + hydration) → 3. Phase 3 US1 → **STOP & validate** playlists end-to-end (incl. IDOR + tombstone). Deliverable MVP: working personal playlists on real catalog data.

### Incremental delivery

Foundation → US1 (MVP, demo) → US2 liked (demo) → US3 history (demo) → Polish. Each story adds value without breaking the previous.

---

## Notes

- `[P]` = different files, no incomplete-task dependency.
- Every `/me/*` test must include an IDOR/isolation case (Constitution I/XI).
- Jamendo mocked in all tests; suite stays network-free and deterministic.
- Commit after each task or logical group; keep black/ruff/mypy green throughout.
- Total: 33 tasks — Setup 3, Foundational 12, US1 6, US2 4, US3 4, Polish 4.
