# Phase 0 Research: Catalog Proxy

All decisions below are grounded in the Jamendo API v3.0 docs
(https://developer.jamendo.com/v3.0) reviewed 2026-07-25, the existing BE-001
`core/` primitives, and Constitution Principle IV (Catalog Proxy & Cache Discipline).

## 1. HTTP client — httpx 0.28.1

- **Decision**: Add `httpx==0.28.1` to `requirements/base.txt`; use a module-level
  `httpx.Client` inside `JamendoClient` with an explicit `timeout=` from settings.
- **Rationale**: No HTTP client is currently installed (`requests` absent). httpx has
  first-class, mandatory-friendly timeout configuration and a `MockTransport` that
  lets every test run offline. Version verified on PyPI 2026-07-25 (latest stable,
  Python 3.8+). Satisfies Principle XIV (justified + version-pinned).
- **Alternatives**: `requests` (no native async path, timeout easy to forget);
  stdlib `urllib` (verbose, no connection pooling / clean timeout ergonomics).

## 2. JamendoClient — single upstream boundary

- **Decision**: One class in `apps/catalog/services/jamendo.py` is the *only* code
  that constructs Jamendo URLs or reads its raw JSON. It exposes typed methods:
  `list_tracks(...)`, `get_track(id)`, `get_artist(id)`, `get_album(id)`,
  `trending(genre=None)`. `client_id`, base URL, timeout, and `audioformat` come
  from settings. Every method injects `client_id` + `format=json`.
- **Rationale**: Principle IV requires centralization so the source is swappable and
  the credential is contained. Views/serializers never see raw upstream fields.
- **Upstream failure handling**: catch `httpx.TimeoutException`, `httpx.HTTPError`,
  non-2xx status, and Jamendo's own failure envelope (`headers.status == "failed"`
  or a non-zero `headers.code`) → raise `AppError(ErrorCode.CATALOG_UPSTREAM_ERROR)`.
  The raw exception/text is logged (redacted) but never returned. Detail lookups that
  return an empty `results` array → raise `AppError(ErrorCode.NOT_FOUND)`.

## 3. Jamendo parameter mapping

| Our API | Jamendo `/tracks` (etc.) params |
|---|---|
| `GET /catalog/trending` (+`genre`) | `order=popularity_month`, `limit=<CATALOG_TRENDING_SIZE=50>`, optional `tags=<mapped>` |
| `GET /catalog/tracks?search=` | `search=<q>` (free text over track+artist+album+tags — covers "track + artist name") |
| `GET /catalog/tracks?genre=` | `tags=<slug→tag>` |
| `GET /catalog/tracks` paging | `limit=<1..50, default 20>`, `offset=<decoded from cursor>` |
| `GET /catalog/tracks/{id}` | `/tracks/?id=<id>` |
| `GET /catalog/artists/{id}` | `/artists/?id=<id>` |
| `GET /catalog/albums/{id}` | `/albums/?id=<id>` |
| audio | `audioformat=<JAMENDO_AUDIOFORMAT=mp31>` → drives `audio`/`audiodownload` = `stream_url` |
| track metadata | `include=musicinfo+licenses` → genres (`musicinfo.tags.genres`) + `license_ccurl` |
| license label | `license_ccurl` CC deed URL → CC label via lookup constant (e.g. `by-nc-sa` → `"CC BY-NC-SA"`); unknown → raw `musicinfo.licenses` string, else `""`. Raw URL never emitted (data-model.md) |

- **Decision on `search`**: use Jamendo `search` (not `namesearch`) because the
  clarified requirement is "track name + artist name"; `namesearch` matches track
  name only. `search` is broader (also album/tags) but is the parameter that includes
  artist — acceptable and documented.
- **`fullcount`**: request `fullcount=true` so the response `headers.results_fullcount`
  gives the total, enabling exact `has_more` (see §5).

## 4. Caching — key strategy & TTLs

- **Decision**: `apps/catalog/services/cache.py` provides `get_or_fetch(key, ttl, fn)`
  over Django's default cache (Redis via `django_redis`; LocMem in tests/dev). The
  **mapped** result (contract dict) is cached — never raw upstream JSON — so a hit
  serves the exact response shape and re-mapping is skipped.
- **Key format**: `catalog:v1:<resource>:<sha1(sorted params)>`, e.g.
  `catalog:v1:tracks:<hash{search,genre,limit,offset}>`. Namespaced + includes every
  query param that affects the result (Principle IV). Detail keys include the id.
- **TTLs (named settings, seconds)** — differ by volatility:

  | Resource | Setting | Default |
  |---|---|---|
  | trending | `CACHE_TTL_TRENDING` | 3600 (1h) |
  | genres | `CACHE_TTL_GENRES` | 86400 (24h) — served in-process from settings (no Redis layer, no upstream); `CACHE_TTL_GENRES` only drives an HTTP `Cache-Control: max-age` header. See §6 |
  | tracks/search | `CACHE_TTL_SEARCH` | 120 (2m) |
  | detail (track/artist/album) | `CACHE_TTL_DETAIL` | 1800 (30m) |

- **Negative caching**: upstream failures are **not** cached — we do not want to
  persist a `502`. Empty search results **are** cached (valid result, short TTL).
- **Rationale**: cuts Jamendo quota (Principle IV) while keeping volatile search fresh.

## 5. Cursor pagination over an offset upstream

- **Decision**: `apps/catalog/pagination.py` defines an opaque cursor =
  `base64url(json({"offset": N}))`. `GET /catalog/tracks` reads `limit` (1..50,
  default 20) and `cursor` → decodes `offset` → calls Jamendo with `limit`/`offset`
  → returns `{items, next_cursor, has_more}` (same envelope as
  `core.pagination.CursorPage`, but computed here for proxied data).
- **`has_more`**: `offset + len(items) < headers.results_fullcount`. `next_cursor`
  encodes `offset + limit` when `has_more`, else `null`.
- **Malformed cursor** → `AppError(ErrorCode.VALIDATION_ERROR)` (400), never a 500.
- **Why not `core.pagination.CursorPage`**: that class is DRF's DB-`CursorPagination`
  (needs a queryset + ordering column). Proxied Jamendo results are not a queryset;
  reusing it would force a fake queryset. The envelope is identical, so mobile sees
  no difference. `CursorPage` remains the tool for BE-003's DB-backed `/me/*` lists.

## 6. Genre source — curated static list

- **Decision**: `settings.CATALOG_GENRES` holds a curated list of
  `{slug, name, tag}` (seeded from Jamendo's featured genres: electronic, jazz, pop,
  hiphop, rock, metal, classical, lounge, songwriter, world, relaxation, soundtrack,
  …). `GET /catalog/genres` returns `[{slug, name}]` from this list with **no upstream
  call**. `genre=<slug>` filters map `slug → tag`. Unknown slug → `VALIDATION_ERROR`.
- **Rationale**: Jamendo v3.0 has **no** "list all genres" endpoint (confirmed in
  docs); genres are just tags with a noisy, unbounded vocabulary. A curated list gives
  a stable, controllable filter UX and a permanently cacheable response. It is a domain
  constant (like `APPLE_KEYS_URL` in BE-001 settings), not a secret — Principle VI is
  satisfied by keeping it in settings, env-overridable.
- **Alternatives**: deriving tags dynamically from Jamendo (noisy, unstable, extra
  upstream calls, unpredictable UI) — rejected.

## 7. `is_liked` in BE-002

- **Decision**: `Track.is_liked` is always `False` in this feature. The serializer
  emits a constant default; catalog endpoints accept no user token.
- **Rationale**: the liked-tracks store is BE-003 (`apps/library`). Wiring per-user
  `is_liked` (optional Bearer on catalog reads) is deferred to BE-003; the contract
  already documents `is_liked` as false/null for anonymous requests.

## 8. Auth & error reuse (no new primitives)

- Layer-1 `X-App-Key` is enforced globally by the existing `core.middleware.AppKeyMiddleware`;
  catalog URLs are **not** added to `APP_KEY_EXEMPT_PREFIXES`, so all six endpoints
  require a valid key automatically. No Layer-2 (Bearer) required.
- Errors reuse `AppError` + `api_exception_handler` + `ErrorCode`. **No new error code
  is introduced** — every case maps to an existing catalog code.

## 9. Legal / licensing (Principle XIII)

- Jamendo free API is **non-commercial only**. `Track.license_type` is surfaced so the
  client can display attribution. No monetization hooks are added. Documented here and
  in the changelog at implement time.
