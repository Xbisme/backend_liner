# Quickstart: Catalog Proxy (BE-002)

End-to-end validation guide. Proves the six catalog endpoints proxy Jamendo, cache,
map to the contract schemas, and translate upstream failures — without leaking the
`client_id`. Implementation lives in `apps/catalog` (see [plan.md](plan.md)).

## Prerequisites

- BE-001 merged (Django+DRF skeleton, `core/`, `AppKeyMiddleware`).
- `.env` present with a real `JAMENDO_CLIENT_ID` (already set) and an `X_APP_KEY`.
- Redis running for real cache behavior (tests use LocMem / mocked transport — no Redis needed).
- New dependency installed: `pip install -r requirements/dev.txt` (adds `httpx==0.28.1`).

## Automated validation (primary — no live upstream)

Jamendo is mocked at the httpx transport layer, so the full suite runs offline.

```bash
pytest apps/catalog -q            # all catalog tests (mapper, client, cache, endpoints)
pytest -q                         # full suite (BE-001 + BE-002) stays green
```

Pre-commit gates (must all be green — see `.claude/dev-workflow.md`):

```bash
black . && ruff check . && mypy . && pytest
python manage.py makemigrations --check --dry-run   # expect: "No changes" (catalog has no models)
```

**Expected**: catalog contract tests pass (status/code/shape per
[contracts/catalog-endpoints.md](contracts/catalog-endpoints.md)); no new migration.

## Manual smoke test (optional — hits real Jamendo)

```bash
python manage.py runserver
APP=$X_APP_KEY   # your .env X_APP_KEY value

# Genres — served from the curated list, no upstream call
curl -s -H "X-App-Key: $APP" localhost:8000/catalog/genres | jq

# Trending — 50 tracks, optional genre filter
curl -s -H "X-App-Key: $APP" "localhost:8000/catalog/trending?genre=electronic" | jq 'length'

# Browse/search with cursor paging
curl -s -H "X-App-Key: $APP" "localhost:8000/catalog/tracks?search=night&limit=20" | jq '{count: (.items|length), has_more, next_cursor}'

# Track detail (use an id from the previous call)
curl -s -H "X-App-Key: $APP" "localhost:8000/catalog/tracks/<ID>" | jq '{id,title,stream_url,license_type,is_liked}'
```

**Expected outcomes**

| Check | Pass condition |
|---|---|
| Auth gate | Same calls **without** `X-App-Key` → `401 INVALID_APP_KEY`. |
| Genres | Returns `[{slug,name}]`; no `tag` field; identical on repeat (cached). |
| Trending | Returns ≤ 50 mapped `Track` objects; `?genre=` filters. |
| Tracks | `{items,next_cursor,has_more}`; following `next_cursor` yields non-overlapping page 2. |
| Detail | Full `Track` with a working `stream_url`; unknown id → `404 NOT_FOUND`. |
| No leak | No response contains `client_id` or raw Jamendo-only keys. |
| Cache | Two identical `tracks` calls within TTL → only one upstream request (observe logs / mock count). |
| Upstream down | Simulated Jamendo timeout/5xx → `502 CATALOG_UPSTREAM_ERROR`, never a 500 or raw error. |

## Definition of Done (this feature)

- [ ] All rows in [contracts/catalog-endpoints.md](contracts/catalog-endpoints.md) have passing tests.
- [ ] `black`/`ruff`/`mypy`/`pytest` green; `makemigrations --check` clean.
- [ ] No hardcoded secret/URL/TTL — all via settings/env; `JAMENDO_AUDIOFORMAT` added to `.env.example`.
- [ ] `contracts/openapi.yaml` + `.claude/api-context.md` still match (no shape drift). If drift → update all 3 + version per Contract Sync.
- [ ] `.claude/changelog.md` updated; note the **MO-002 sync point** (mobile switches mock → real API).
