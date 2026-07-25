---
description: "Task list for BE-002 Catalog Proxy"
---

# Tasks: Catalog Proxy

**Input**: Design documents from `specs/002-catalog-proxy/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/catalog-endpoints.md](contracts/catalog-endpoints.md)

**Tests**: INCLUDED — Constitution Principle XI (Testing Discipline) is mandatory and spec SC-006 requires unit/service/API tests with Jamendo mocked.

**Organization**: Tasks grouped by user story. US1 is the MVP; US2 and US3 are independent increments layered on the shared foundation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish carry no story label)
- Exact file paths are included in every task.

## Path Conventions

Django app under `apps/catalog/` (mirrors `apps/accounts` from BE-001); shared code in
`core/` (reused, unchanged); config in `config/`. Repository root is the working dir.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Register the app, add the one new dependency, and wire all config from env.

- [X] T001 [P] Add `httpx==0.28.1` to `requirements/base.txt` (with a pin comment referencing research.md §1) and install into `.venv`
- [X] T002 Create app skeleton `apps/catalog/__init__.py` + `apps/catalog/apps.py` (`CatalogConfig`, name `apps.catalog`) and register `"apps.catalog"` in `INSTALLED_APPS` in `config/settings/base.py`
- [X] T003 Wire catalog settings in `config/settings/base.py`: `JAMENDO_CLIENT_ID`, `JAMENDO_API_BASE_URL`, `JAMENDO_REQUEST_TIMEOUT_SECONDS`, `JAMENDO_AUDIOFORMAT` (default `mp31`), `CACHE_TTL_TRENDING/_GENRES/_SEARCH/_DETAIL`, `CATALOG_TRENDING_SIZE` (50), `CATALOG_TRACKS_PAGE_SIZE_DEFAULT` (20), `CATALOG_TRACKS_PAGE_SIZE_MAX` (50), and the `CATALOG_GENRES` curated list of `{slug,name,tag}` (all env-driven per data-model.md)
- [X] T004 [P] Add `JAMENDO_AUDIOFORMAT=mp31` to `.env.example` and `.env` (other `JAMENDO_*`/`CACHE_TTL_*` keys already present)
- [X] T005 Create `apps/catalog/urls.py` (empty `urlpatterns`) and include it at prefix `catalog/` in `config/urls.py`
- [X] T006 [P] Create `apps/catalog/constants.py` (cache-key namespace `catalog:v1`, Jamendo param names, `order=popularity_month`, `include=musicinfo+licenses`, and the CC-license URL→label lookup table per data-model.md, e.g. `by-nc-sa` → `"CC BY-NC-SA"`)

**Checkpoint**: `python manage.py check` passes; app is installed and routable (no endpoints yet).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the proxy pipeline primitives every endpoint reuses — upstream client, mapper, serializers, cache, cursor, genre helper, and the test harness.

**⚠️ CRITICAL**: No user story (Phase 3+) can begin until this phase is complete.

- [X] T007 [P] Test harness: `apps/catalog/tests/__init__.py`, `apps/catalog/tests/conftest.py` (httpx `MockTransport` fixture + `X-App-Key` API client), `apps/catalog/tests/factories.py` (builders for raw Jamendo track/artist/album JSON payloads incl. `headers.results_fullcount` and `status:failed`)
- [X] T008 [P] Implement `apps/catalog/serializers.py`: `ArtistSerializer`, `AlbumSerializer`, `GenreSerializer`, `TrackSerializer` (with constant `is_liked=False`), `TrackCursorPageSerializer` — explicit fields only, matching `contracts/openapi.yaml` (no raw passthrough)
- [X] T009 [P] Implement `apps/catalog/services/mapper.py`: functions mapping raw Jamendo JSON → Artist/Album/Genre/Track dicts per data-model.md; derive `license_type` from `license_ccurl` via the T006 lookup (fallback to raw `musicinfo.licenses`, never emit the URL); MUST tolerate missing `album`/`image`/`musicinfo`/`genres`/`license_ccurl` with safe empties
- [X] T010 [P] [Test] `apps/catalog/tests/test_mapper.py`: full track mapping, flat→nested artist/album, genre lookup against curated list (unknown tags dropped), `license_ccurl`→label (known + unknown→fallback), missing-field safety
- [X] T011 [P] Implement `apps/catalog/genres.py`: read `settings.CATALOG_GENRES`; `list_genres()` → `[{slug,name}]`, `slug_to_tag(slug)` with unknown-slug raising `AppError(VALIDATION_ERROR)`
- [X] T012 [P] Implement `apps/catalog/pagination.py`: `encode_cursor(offset)`/`decode_cursor(cursor)` (base64url JSON), `build_page(items, offset, limit, fullcount)` → `{items,next_cursor,has_more}`; malformed cursor → `AppError(VALIDATION_ERROR)`
- [X] T013 [P] Implement `apps/catalog/services/cache.py`: `cache_key(resource, params)` (namespaced `catalog:v1:<resource>:<sha1>`) and `get_or_fetch(key, ttl, fn)` over Django default cache; never caches upstream failures
- [X] T014 Implement `apps/catalog/services/jamendo.py` `JamendoClient`: module-level `httpx.Client` with explicit timeout from settings; inject `client_id`+`format=json`+`audioformat`; methods `list_tracks(...)`, `trending(genre)`, `get_track/get_artist/get_album(id)`; translate `httpx.TimeoutException`/`HTTPError`/non-2xx/`headers.status=="failed"` → `AppError(CATALOG_UPSTREAM_ERROR)` (raw error logged redacted, never returned); empty `results` on a detail call → `AppError(NOT_FOUND)` (depends on T006 constants)
- [X] T015 [Test] `apps/catalog/tests/test_jamendo_client.py`: timeout/5xx/rate-limit/`status:failed` → `502 CATALOG_UPSTREAM_ERROR`; detail empty → `404`; assert `client_id` never appears in any raised message/response
- [X] T016 [P] [Test] `apps/catalog/tests/test_cache.py`: `get_or_fetch` miss→fetch→hit; two identical calls within TTL invoke `fn` once; failures not cached

**Checkpoint**: All primitives implemented and unit/service-tested with Jamendo fully mocked. Endpoints can now be assembled.

---

## Phase 3: User Story 1 — Duyệt và tìm nhạc (Priority: P1) 🎯 MVP

**Goal**: Users browse trending music and search/filter the catalog with cursor paging — the core of a music app and the MO-002 mock→real sync point.

**Independent Test**: Call `GET /catalog/trending` and `GET /catalog/tracks` (with/without `search`, with/without `genre`, following `next_cursor`) using a valid app-key; verify normalized `Track` data, correct paging envelope, and no upstream leakage — with Jamendo mocked.

- [X] T017 [US1] Implement `trending(genre=None)` and `list_tracks(search, genre, cursor, limit)` orchestration in `apps/catalog/services/catalog.py` — **clamp integer `limit` to 1..50** (default 20; non-integer → `VALIDATION_ERROR`), validate `genre` slug (via `genres.py`), call `JamendoClient`, map results, wrap in cache (`CACHE_TTL_TRENDING`/`CACHE_TTL_SEARCH`) and cursor page
- [X] T018 [US1] Implement `TrendingView` (returns `Track[]`, size 50) and `TracksView` (returns `TrackCursorPageSerializer` data) in `apps/catalog/views.py`
- [X] T019 [US1] Wire `catalog/trending` and `catalog/tracks` routes in `apps/catalog/urls.py`
- [X] T020 [P] [US1] [Test] `apps/catalog/tests/test_trending.py`: 200 with ≤50 mapped tracks, `?genre=` maps to `tags`, unknown genre → `400 VALIDATION_ERROR` (before upstream), upstream fail → `502`, missing app-key → `401`
- [X] T021 [P] [US1] [Test] `apps/catalog/tests/test_tracks.py`: search+genre paths, out-of-range integer `limit` **clamped to 1..50** (200, no error), non-integer `limit` → `400`, malformed cursor → `400`, page1→`next_cursor`→page2 no overlap, empty results → `200 {items:[],has_more:false}`, identical calls → one upstream call, **valid app-key with no `Authorization: Bearer` → `200`** (FR-016 positive case)

**Checkpoint**: MVP delivered — browse + search fully functional and independently testable.

---

## Phase 4: User Story 2 — Chi tiết track/artist/album (Priority: P2)

**Goal**: Users open a track, artist, or album to see details and start playback (stream_url in track detail).

**Independent Test**: With a valid id, call each detail endpoint and assert the normalized object; with a nonexistent id, assert `404 NOT_FOUND` — Jamendo mocked.

- [X] T022 [US2] Implement `get_track(id)`, `get_artist(id)`, `get_album(id)` orchestration in `apps/catalog/services/catalog.py` — call `JamendoClient`, map, cache with `CACHE_TTL_DETAIL`; empty upstream → `NOT_FOUND`
- [X] T023 [US2] Implement `TrackDetailView`, `ArtistDetailView`, `AlbumDetailView` in `apps/catalog/views.py`
- [X] T024 [US2] Wire `catalog/tracks/<id>`, `catalog/artists/<id>`, `catalog/albums/<id>` routes in `apps/catalog/urls.py`
- [X] T025 [P] [US2] [Test] `apps/catalog/tests/test_detail.py`: track/artist/album detail shape (track has working `stream_url`, `is_liked=false`), nonexistent id → `404 NOT_FOUND`, upstream fail → `502`

**Checkpoint**: Detail screens + player source functional; independent of US1.

---

## Phase 5: User Story 3 — Danh sách thể loại (Priority: P3)

**Goal**: Provide the genre list for the filter UI, served from the curated config with no upstream call.

**Independent Test**: Call `GET /catalog/genres` with a valid app-key; assert `[{slug,name}]` from the curated list and that no Jamendo request is made.

- [X] T026 [US3] Implement `GenresView` in `apps/catalog/views.py` returning `genres.list_genres()` via `GenreSerializer` (served in-process from settings — no upstream call, no Redis layer; optionally set `Cache-Control: max-age=CACHE_TTL_GENRES`)
- [X] T027 [US3] Wire `catalog/genres` route in `apps/catalog/urls.py`
- [X] T028 [P] [US3] [Test] `apps/catalog/tests/test_genres.py`: `200` `[{slug,name}]`, internal `tag` never emitted, zero upstream calls (assert mock transport unused), missing app-key → `401`

**Checkpoint**: Filter data available; all six endpoints complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Contract sync, docs, and the full quality gate.

- [X] T029 [P] Verify `contracts/openapi.yaml` + `.claude/api-context.md` still match the implemented shapes (no drift). If drift found, update all 3 files + bump Contract version per Contract Sync (`.claude/dev-workflow.md`)
- [X] T030 [P] Update `.claude/changelog.md`: BE-002 Catalog Proxy done; flag the **MO-002 sync point** (mobile switches mock→real API)
- [X] T031 [P] Update `.claude/project-context.md` (Current Focus) and `.claude/sdd-roadmap.md` (BE-002 status → done, BE-003 next)
- [X] T032 Run the full pre-commit gate: `black . && ruff check . && mypy . && pytest && python manage.py makemigrations --check --dry-run` (expect "No changes"), then walk [quickstart.md](quickstart.md) validation table

---

## Dependencies & Execution Order

- **Setup (P1)** → **Foundational (P2)** → **User Stories (P3–P5)** → **Polish (P6)**.
- Within Foundational: T014 (`JamendoClient`) depends on T006 (constants); T015 depends on T014; everything else (T007–T013, T016) is parallel-safe (distinct files).
- **US1** depends on Foundational (uses client, mapper, cache, cursor, genres). **US2** depends on Foundational (client, mapper, cache). **US3** depends only on `serializers.py` + `genres.py` (T008, T011) — the lightest story, deliverable independently despite its P3 priority.
- US1, US2, US3 are mutually independent once Foundational is done — they touch overlapping files (`views.py`, `urls.py`, `services/catalog.py`) so run **sequentially by priority** to avoid merge churn, or split those files if parallelizing.
- Polish runs after the stories being shipped are complete.

## Parallel Execution Examples

- **Setup**: T001, T004, T006 in parallel (distinct files).
- **Foundational**: T007, T008, T009, T011, T012, T013 in parallel; then T010, T016 (tests) in parallel; then T014 → T015.
- **Per story**: implementation tasks are sequential (shared `views.py`/`urls.py`/`catalog.py`), but the test task ([P]) can be written in parallel with route wiring.

## Implementation Strategy

- **MVP = US1 only** (T001–T021): browse + search shipped and independently testable — this is the MO-002 sync deliverable. Ship, then add US2 (detail) and US3 (genres) as increments.
- Each story ends at a green checkpoint (its tests + the running suite pass) before the next begins.

## Task Summary

- **Total tasks**: 32
- **Setup**: 6 (T001–T006) · **Foundational**: 10 (T007–T016)
- **US1 (P1, MVP)**: 5 (T017–T021) · **US2 (P2)**: 4 (T022–T025) · **US3 (P3)**: 3 (T026–T028)
- **Polish**: 4 (T029–T032)
- **Test tasks**: 8 (T010, T015, T016, T020, T021, T025, T028 + gate T032)
