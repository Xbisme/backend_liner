# Implementation Plan: Catalog Proxy

**Branch**: `BE-002-catalog-proxy` | **Date**: 2026-07-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-catalog-proxy/spec.md`

## Summary

Build `apps/catalog` — a read-only proxy over the Jamendo API v3.0 that exposes six
catalog endpoints (`trending`, `genres`, `tracks`, `tracks/{id}`, `artists/{id}`,
`albums/{id}`). All upstream access is centralized in one `JamendoClient`; raw
Jamendo JSON is mapped into the contract's `Track`/`Artist`/`Album`/`Genre` schemas
before leaving the backend, and the Jamendo `client_id` never reaches clients.
Responses are cached in Redis with TTLs that differ by volatility. Upstream
timeouts/rate-limits/5xx are translated to `502 CATALOG_UPSTREAM_ERROR` through the
existing error envelope. Endpoints require only Layer-1 auth (`X-App-Key`); content
is public. No database models, no migrations — the catalog is stateless proxy+cache.

## Technical Context

**Language/Version**: Python 3.12 (matches BE-001 `.venv`)

**Primary Dependencies**: Django 5.2 + DRF 3.17 (existing); **httpx 0.28.1** (new — HTTP client with first-class explicit timeouts); `django-redis` 7.0 (existing) for the cache

**Storage**: Redis (cache only, via existing `CACHES["default"]`). **No PostgreSQL models** — catalog data lives upstream; backend holds nothing persistent.

**Testing**: pytest + pytest-django (existing); Jamendo mocked at the httpx transport layer (`httpx.MockTransport`) — no live upstream calls in tests.

**Target Platform**: Linux server (Django app)

**Project Type**: Web service (backend API)

**Performance Goals**: Cache hit serves without any upstream call; repeated identical requests within TTL hit Redis. Upstream calls use an explicit timeout (`JAMENDO_REQUEST_TIMEOUT_SECONDS`, default 5s).

**Constraints**: Jamendo `client_id` and raw upstream shape MUST never leak (Principle IV); `limit` ≤ 50; non-commercial use only (Principle XIII).

**Scale/Scope**: 6 endpoints, 1 new Django app, 1 new dependency, 0 migrations.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Relevance | Compliance in this plan |
|---|---|---|
| I. Two-Tier Auth | Catalog = public content | Layer-1 `X-App-Key` only (existing `AppKeyMiddleware`); no `/me` semantics, no user token required. ✅ |
| II. Contract-First | Schemas pre-defined | `Track/Artist/Album/Genre/TrackCursorPage` already in `openapi.yaml` v0.1.0; serializers enforce them; no shape invented in code. ✅ |
| III. Layered Architecture | proxy pipeline | `views → services (JamendoClient, mapper, cache) → upstream`; views hold no upstream logic. ✅ |
| IV. Catalog Proxy & Cache | **core of feature** | Single `JamendoClient` wrapper; mapping before egress; named TTL settings by volatility; namespaced cache keys with all params; timeout + 502 translation. ✅ |
| V. Consistent Errors | reuse | Reuse `AppError` + `api_exception_handler` + `ErrorCode`; add no new code (all needed codes exist: `CATALOG_UPSTREAM_ERROR`, `NOT_FOUND`, `VALIDATION_ERROR`, `INVALID_APP_KEY`). ✅ |
| VI. Config & Secrets | new settings | `JAMENDO_*`, `CACHE_TTL_*`, `CATALOG_*` all read from env/settings; nothing hardcoded. ✅ |
| VII. Data Integrity & Migrations | no models | No DB models → no migrations. `makemigrations --check` stays clean. ✅ |
| VIII. Security Hardening | out of scope | Rate-limit/Sentry are BE-004; this plan only ensures no secret/raw-shape leak. ✅ |
| IX. Observability | upstream logging | Log upstream failures via existing redaction filter; `client_id` never logged. ✅ |
| X. Code Quality & Typing | gates | Full type hints; black/ruff/mypy green. ✅ |
| XI. Testing Discipline | mocked upstream | unit (mapper), service (client w/ mocked transport), API (endpoint contract tests). ✅ |
| XII. Simplicity & YAGNI | no background jobs | No Celery, no pre-warm, no DB caching of tracks. Cache-on-read only. ✅ |
| XIII. Legal & Licensing | Jamendo TOS | Non-commercial; `license_type` surfaced per track; documented in research. ✅ |
| XIV. Dependency Hygiene | new dep | `httpx==0.28.1` justified (timeout-first HTTP client; `requests` not installed) + version-verified on PyPI 2026-07-25. ✅ |

**Result**: PASS — no violations. Complexity Tracking table intentionally empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-catalog-proxy/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions (httpx, cursor, cache, genre source, param mapping)
├── data-model.md        # Phase 1 — DTO/serializer field map (no DB models)
├── quickstart.md        # Phase 1 — validation guide
├── contracts/
│   └── catalog-endpoints.md   # Phase 1 — contract-test checklist
└── tasks.md             # /speckit-tasks (NOT created here)
```

### Source Code (repository root)

```text
apps/catalog/
├── __init__.py
├── apps.py                    # CatalogConfig
├── constants.py               # cache-key namespaces, Jamendo `order`/param names
├── serializers.py             # Artist/Album/Genre/Track/TrackCursorPage serializers (enforce openapi)
├── pagination.py              # OffsetCursor: opaque cursor ⇄ Jamendo offset; {items,next_cursor,has_more}
├── services/
│   ├── __init__.py
│   ├── jamendo.py             # JamendoClient — the ONLY module that talks to Jamendo (httpx)
│   ├── mapper.py              # raw Jamendo JSON → Track/Artist/Album/Genre dicts
│   ├── cache.py               # cache_key() + get_or_fetch() (TTL by resource)
│   └── catalog.py             # orchestration used by views (trending/genres/tracks/detail)
├── genres.py                  # helpers over settings.CATALOG_GENRES (slug↔tag, validation)
├── views.py                   # 6 APIViews
├── urls.py                    # /catalog/* routes
└── tests/
    ├── __init__.py
    ├── conftest.py            # httpx.MockTransport fixtures + sample Jamendo payloads
    ├── factories.py           # raw-Jamendo payload builders
    ├── test_mapper.py         # unit: JSON→schema mapping (missing fields safe)
    ├── test_jamendo_client.py # service: timeout/5xx/rate-limit → AppError; no client_id leak
    ├── test_cache.py          # get_or_fetch hit/miss; upstream called once within TTL
    ├── test_trending.py       # API: 50 items, genre filter, 502 on upstream fail
    ├── test_genres.py         # API: curated list, no upstream call
    ├── test_tracks.py         # API: search/genre/limit validation, cursor paging
    └── test_detail.py         # API: track/artist/album detail + NOT_FOUND

core/                          # unchanged (reuse errors, exceptions, middleware, authentication)
config/settings/base.py        # + apps.catalog, JAMENDO_*, CACHE_TTL_*, CATALOG_* settings
config/urls.py                 # + include apps.catalog.urls
requirements/base.txt          # + httpx==0.28.1
.env.example / .env            # + JAMENDO_AUDIOFORMAT (others already present)
```

**Structure Decision**: New Django app `apps/catalog` mirroring the `apps/accounts`
layout established in BE-001 (models-free variant). Upstream access is isolated in
`services/jamendo.py`; the offset-cursor lives in `apps/catalog/pagination.py`
(catalog-specific — distinct from `core/pagination.CursorPage`, which is DRF's
DB-queryset cursor for BE-003's `/me/*` lists and does not fit proxied results).

## Complexity Tracking

> No Constitution violations — no entries.

## Phase Outputs

- **Phase 0** → [research.md](research.md): httpx choice, offset-cursor design, cache key/TTL strategy, curated-genre source, Jamendo param mapping, upstream-failure & has_more detection.
- **Phase 1** → [data-model.md](data-model.md) (field-level mapping, no DB), [contracts/catalog-endpoints.md](contracts/catalog-endpoints.md) (contract-test checklist), [quickstart.md](quickstart.md) (end-to-end validation).
- **Phase 2** (`/speckit-tasks`, not here) → tasks.md.
