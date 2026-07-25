# Research: User Library (BE-003)

All spec-level ambiguities were resolved in `/speckit-clarify` (see spec.md Clarifications). This document records the **implementation decisions** — the "how" behind those resolutions — grounded in the existing BE-001/002 code.

## §1. Track metadata hydration (the core decision)

**Decision**: Add a public batch entrypoint to the catalog service:
`apps.catalog.services.catalog.get_tracks_by_ids(ids: list[str], *, liked_ids: set[str]) -> list[dict]`.
`apps/library` calls **only** this function — never catalog internals — satisfying Constitution III (one-way public dependency, no cross-app internal import).

**Mechanism**:
- New client method `apps.catalog.services.jamendo.list_tracks_by_ids(ids)` uses Jamendo's multi-value `id` param (`id=<id1>+<id2>+…`, i.e. space/plus-joined) with the same `include`/`audioformat` params as `get_track`. One upstream call per page (≤ `limit` ids).
- Per-id caching reuses `cache.get_or_fetch` with `CACHE_TTL_DETAIL` and the existing `track` cache key (`cache_key("track", {"id": id})`) — so a track already warmed by `/catalog/tracks/{id}` is a cache hit here and vice-versa. Only ids missing from cache are batched upstream; results are back-filled into per-id cache.
- `map_track` gains `available: True`. For any requested id with no upstream result, emit a **tombstone**: `{"id": id, "available": False, "title": None, "artist": None, "album": None, "genres": [], "duration_seconds": None, "cover_url": None, "stream_url": None, "license_type": None, "is_liked": <membership>}`.
- Order is preserved to match the caller's id order (playlist position / recency).

**Global-failure vs per-id-absence**: `JamendoClient` already raises `AppError(CATALOG_UPSTREAM_ERROR)` on timeout/5xx/`status!=success`. That propagates out of `get_tracks_by_ids` → the shared handler renders **502** (spec: global upstream failure). A per-id *absence* (id simply not in the successful batch result) is **not** an error → tombstone. This is the exact distinction the clarify session locked.

**Rationale**: Keeps the "no stored metadata" constraint intact, reuses the Redis cache (no second cache, Constitution XII), and centralizes upstream access in the one client (Constitution IV). Batch-by-page bounds upstream load to one call/page.

**Alternatives considered**:
- *Denormalize a metadata snapshot at like/add time* — rejected: violates the explicit "backend không lưu metadata bài hát" constraint and goes stale.
- *Let mobile hydrate via `/catalog/tracks/{id}`* — rejected: contract returns full `Track`/`TrackCursorPage` in library responses; would break the frozen shape and cause N calls from the client.
- *Per-id sequential fetch* — rejected: N upstream calls per page (N+1), quota/latency blowup.

## §2. Cursor pagination over hydrated lists

**Decision**: Paginate the **model queryset**, then hydrate the page. `GET /me/liked-tracks`, `/me/history`, `/me/playlists` use `core.pagination.CursorPage` (DRF `CursorPagination`, already the DRF default) over `LikedTrack`/`ListeningHistory`/`Playlist` querysets. After DRF slices the page, the view collects that page's `track_id`s and calls `get_tracks_by_ids` once.

**Ordering keys** (stable, unique-tie-broken by pk so pages never skip/dup — Constitution VII):
- Playlists: `("-updated_at", "-id")` — recently-touched first (clarify Q).
- Liked tracks: `("-created_at", "-id")` — most-recently-liked first.
- History: `("-played_at", "-id")` — most-recently-played first.

`core.pagination.CursorPage.ordering` is currently the single value `"-id"`; per-endpoint ordering is set by subclassing (e.g. `PlaylistCursorPage(CursorPage)` with `ordering = ("-updated_at", "-id")`) or by setting `ordering` on the paginator instance in the view. Malformed cursor → DRF raises `NotFound`/`ValidationError`; confirm it maps to `VALIDATION_ERROR` (400) via the shared handler, matching the catalog cursor behavior (spec edge case). If DRF emits 404 for a bad cursor, wrap decoding to raise `AppError(VALIDATION_ERROR)` for parity with `apps/catalog/pagination.py`.

**Rationale**: DB rows carry the orderable/paginable state; Track metadata is display-only and fetched last. Avoids trying to paginate over hydrated dicts (no stable DB cursor there).

**Alternatives considered**: reuse the catalog offset-cursor (`apps/catalog/pagination.py`) — rejected: that is an *offset into an upstream list*, wrong tool for owned DB rows where keyset pagination is correct and concurrency-safe.

## §3. Playlist reorder

**Decision**: `PATCH /me/playlists/{id}/tracks/reorder` accepts the full `track_ids` list. Validate `set(track_ids) == set(existing track_ids)` **and** equal length (rejects dupes/missing/extras) → else `AppError(REORDER_MISMATCH)` (400). On success, rewrite `position` for each row in a single `transaction.atomic()` bulk update following the submitted order. Return `PlaylistDetail` (200) with tracks hydrated in the new order.

**Rationale**: Full-list replacement is unambiguous and matches contract (`ReorderPlaylistRequest.track_ids` = "toàn bộ danh sách theo thứ tự mới") and Constitution VII (reorder must exactly match current tracks; stable unique ordering).

## §4. Listening history — distinct + cap

**Decision**:
- `(user, track_id)` **unique constraint**. `POST /me/history` → `update_or_create` on `(user, track_id)` setting `played_at` (body value, default `timezone.now()` if absent) and `completed`. Re-logging the same track updates recency, never duplicates (clarify Q). Returns **201** per contract.
- After each write, trim: keep the newest `HISTORY_MAX_ENTRIES` (default 100, `settings.HISTORY_MAX_ENTRIES`) rows for that user; delete older. Done in the same service call.
- `played_at` in the future (or non-datetime) → serializer validation → `VALIDATION_ERROR` (400).

**Rationale**: "Recently played" UX wants distinct tracks; cap bounds table growth without a background job (Constitution XII). Rate-limiting the endpoint is BE-004 (documented out of scope).

**Alternatives considered**: append-only event log — rejected in clarify (unbounded growth, duplicate rows in "recently played" list).

## §5. is_liked in library responses

**Decision**: Compute per response. The view builds `liked_ids = set(LikedTrack.objects.filter(user=request.user, track_id__in=<page ids>).values_list("track_id", flat=True))` and passes it to `get_tracks_by_ids(..., liked_ids=liked_ids)`, which sets each Track's `is_liked`. For `GET /me/liked-tracks` every item is liked by definition (`is_liked=True`). Catalog Layer-1 endpoints keep `is_liked=False` (no user context) — unchanged from BE-002.

**Rationale**: `is_liked` is user-relative and cheap to compute with one indexed `IN` query per page; storing it on Track would duplicate state and break the stateless catalog.

## §6. Delete-semantics & idempotency (locked in clarify)

- Remove track not in playlist → **204** (idempotent), mirrors unlike-not-liked → 204.
- Cross-user access on any `/me/*` resource → **403 FORBIDDEN** consistently; `404 NOT_FOUND` only for a resource that truly does not exist. Implemented by an owner-scoped selector: `get_owned_playlist_or_error(user, id)` returns the playlist if `owner==user`, raises `AppError(FORBIDDEN)` if it exists but belongs to someone else, `AppError(NOT_FOUND)` if no such id. (Constitution I — decision, not existence-hiding, per contract which documents 403 for "playlist thuộc user khác".)

## §7. Dependencies

**Decision**: **No new dependency.** All needs (DRF views/serializers, SimpleJWT auth, django-redis cache, factory_boy tests) are already pinned in `requirements/`. Constitution XIV latest-version/PyPI check therefore N/A for this feature. If a future need arises it must follow the PyPI-lookup rule.

## §8. Contract delta

**Decision**: The only contract change is additive on `Track`:
- `available: { type: boolean, default: true }` — false for tombstones.
- Metadata fields (`title`, `artist`, `album`, `cover_url`, `stream_url`, `license_type`, `duration_seconds`, `genres`) become `nullable: true` to represent tombstones.

Update `contracts/openapi.yaml` + `.claude/api-context.md` in the same change (Constitution II authoring order), note it in `changelog.md`, and flag Contract Sync with mobile at freeze #000. Because it is additive/optional it is **not** a breaking change for existing catalog responses (which always send `available:true` with full metadata).
