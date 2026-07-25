# Contract: Catalog Endpoints (BE-002)

**Authoritative source**: [`contracts/openapi.yaml`](../../../contracts/openapi.yaml)
(v0.1.0 draft) + [`.claude/api-context.md`](../../../.claude/api-context.md).
This file is the **contract-test checklist** for BE-002 — every row below MUST have
an automated test asserting the status code, error `code`, and response shape (Jamendo
mocked). It does not redefine the contract; it enumerates what to verify.

## Common rules (all endpoints)

- **`X-App-Key` required on every endpoint.** Missing/invalid → `401` +
  `{ "error": { "code": "INVALID_APP_KEY" } }` (checked by `AppKeyMiddleware` before
  the view runs). Verified once here; not repeated per row.
- **No user token.** Catalog is public — endpoints MUST work with only `X-App-Key`
  and MUST NOT require `Authorization: Bearer`.
- All error bodies use the envelope `{ "error": { "code", "message" } }`. Clients
  branch on `code`.
- **No leakage**: no response (success or error) contains the Jamendo `client_id` or
  any raw upstream-only field. Asserted in `test_jamendo_client.py` / `test_mapper.py`.
- **Upstream failure**: any Jamendo timeout / 5xx / rate-limit / `status:failed`
  envelope → `502` + `code: CATALOG_UPSTREAM_ERROR` (raw error never propagated).

## Endpoints in scope

| Method & path | Auth | Success | Request → Response | Error cases (code / HTTP) |
|---|---|---|---|---|
| `GET /catalog/trending` | AppKey | `200` `Track[]` | `?genre=<slug>?` → 50 trending tracks (popularity_month) | `VALIDATION_ERROR`/400 (bad genre) · `CATALOG_UPSTREAM_ERROR`/502 · `INVALID_APP_KEY`/401 |
| `GET /catalog/genres` | AppKey | `200` `Genre[]` | — → curated `[{slug,name}]`, **no upstream call** | `INVALID_APP_KEY`/401 |
| `GET /catalog/tracks` | AppKey | `200` `TrackCursorPage` | `?search&genre&cursor&limit(1..50,def 20)` → `{items,next_cursor,has_more}` | `VALIDATION_ERROR`/400 (bad limit/cursor/genre) · `CATALOG_UPSTREAM_ERROR`/502 |
| `GET /catalog/tracks/{id}` | AppKey | `200` `Track` | id → one track (w/ stream_url) | `NOT_FOUND`/404 · `CATALOG_UPSTREAM_ERROR`/502 |
| `GET /catalog/artists/{id}` | AppKey | `200` `Artist` | id → artist | `NOT_FOUND`/404 · `CATALOG_UPSTREAM_ERROR`/502 |
| `GET /catalog/albums/{id}` | AppKey | `200` `Album` | id → album | `NOT_FOUND`/404 · `CATALOG_UPSTREAM_ERROR`/502 |

## Response shape assertions

- **Track** has exactly: `id`(str), `title`, `artist`{id,name,image_url},
  `album`{id,title,artist,cover_url}, `genres`[{slug,name}], `duration_seconds`(int),
  `cover_url`, `stream_url`, `license_type`, `is_liked`(bool, always `false` in BE-002).
- **TrackCursorPage** has exactly: `items`(Track[]), `next_cursor`(str|null),
  `has_more`(bool). `next_cursor` is `null` iff `has_more` is `false`.
- **Genre** has exactly `{slug, name}` — the internal Jamendo `tag` is NEVER emitted.
- **Artist** = `{id, name, image_url}`; **Album** = `{id, title, artist, cover_url}`.

## Behavior assertions (beyond shape)

- **Cache**: two identical `GET /catalog/tracks` within TTL → Jamendo called **once**
  (assert mock transport call count == 1). Different params → separate upstream call.
- **Genre filter**: `?genre=<slug>` sends the mapped `tags=<tag>` to Jamendo; unknown
  slug → `VALIDATION_ERROR` **before** any upstream call.
- **Pagination**: page 1 `has_more:true` → follow `next_cursor` → page 2 items are the
  next offset window (no overlap); malformed `cursor` → `VALIDATION_ERROR`.
- **Empty results**: search matching nothing → `200` with `items:[]`, `has_more:false`
  (not an error).
- **Detail not found**: Jamendo returns empty `results` for an id → `NOT_FOUND`/404.
