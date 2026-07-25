# Phase 1 Data Model: Catalog Proxy

**No database models, no migrations.** The catalog is a stateless proxy. The
"entities" here are transient DTOs produced by `services/mapper.py` and validated by
`serializers.py` against `contracts/openapi.yaml`. Jamendo is the source of truth;
the backend persists nothing.

Legend: **Out** = field emitted in our contract · **From** = Jamendo raw field ·
`—` = derived/constant.

## Artist  (`ArtistSerializer`)

| Out field | Type | From (Jamendo) | Notes |
|---|---|---|---|
| `id` | string | `id` | cast to string |
| `name` | string | `name` | |
| `image_url` | uri | `image` | may be empty → emit `""`/null-safe |

## Album  (`AlbumSerializer`)

| Out field | Type | From (Jamendo) | Notes |
|---|---|---|---|
| `id` | string | `id` | cast to string |
| `title` | string | `name` | Jamendo calls it `name` |
| `artist` | Artist | `artist_id`+`artist_name`(+`artist_image`) | nested Artist; on `/tracks` these come as flat fields |
| `cover_url` | uri | `image` | album cover |

## Genre  (`GenreSerializer`)

| Out field | Type | From | Notes |
|---|---|---|---|
| `slug` | string | `settings.CATALOG_GENRES[].slug` | curated (research §6) |
| `name` | string | `settings.CATALOG_GENRES[].name` | display label |

> `tag` (Jamendo filter value) exists in the settings entry but is **internal** — never
> serialized out. On a `Track`, per-track genres are mapped from `musicinfo.tags.genres`
> intersected/looked-up against the curated list (unknown tags dropped).

## Track  (`TrackSerializer`)

| Out field | Type | From (Jamendo `/tracks` + `include=musicinfo+licenses`) | Notes |
|---|---|---|---|
| `id` | string | `id` | cast to string |
| `title` | string | `name` | |
| `artist` | Artist | `artist_id`, `artist_name`, `artist_image` | flat → nested |
| `album` | Album | `album_id`, `album_name`, `album_image` (+artist) | flat → nested |
| `genres` | Genre[] | `musicinfo.tags.genres` → curated lookup | unknown tags dropped; `[]` if none |
| `duration_seconds` | int | `duration` | integer seconds |
| `cover_url` | uri | `image` (or `album_image`) | track/album art |
| `stream_url` | uri | `audio` | direct Jamendo stream (drives the player) |
| `license_type` | string | `license_ccurl` → label (see rule below) | e.g. `"CC BY-NC-SA"` |
| `is_liked` | bool | `—` constant `false` | BE-003 wires per-user (research §7) |

## TrackCursorPage  (`GET /catalog/tracks` response)

| Out field | Type | Source | Notes |
|---|---|---|---|
| `items` | Track[] | mapped `results` | |
| `next_cursor` | string \| null | `base64url({"offset": offset+limit})` | null when `!has_more` |
| `has_more` | bool | `offset + len(items) < headers.results_fullcount` | research §5 |

## Validation & mapping rules

- **Missing upstream fields**: mapper MUST tolerate absent `album`, `image`,
  `musicinfo`, or `genres` — emit safe empties (`""`, `null`, `[]`), never raise
  (spec Edge Case "Trường thượng nguồn thiếu").
- **Type coercion**: all Jamendo ids are strings in our contract even if numeric upstream.
- **`limit`**: parse as integer; if absent → `CATALOG_TRACKS_PAGE_SIZE_DEFAULT (20)`.
  An out-of-range **integer** is **clamped** to `1..CATALOG_TRACKS_PAGE_SIZE_MAX (50)`
  (deterministic, no error). A **non-integer** `limit` → `VALIDATION_ERROR` (400).
- **`license_type` derivation** (`Track.license_type`): map Jamendo `license_ccurl`
  (a Creative Commons deed URL) to its CC label via a lookup constant, e.g.
  `.../by-nc-sa/...` → `"CC BY-NC-SA"`, `.../by-nc-nd/...` → `"CC BY-NC-ND"`,
  `.../by-nc/...` → `"CC BY-NC"`, `.../by/...` → `"CC BY"`, `.../by-sa/...` →
  `"CC BY-SA"`, `.../by-nd/...` → `"CC BY-ND"`. If the URL is missing/unrecognized,
  fall back to the raw license string from `musicinfo.licenses` (or `""`). The lookup
  table lives in `apps/catalog/constants.py`; never emit the raw `license_ccurl` URL.
- **`genre` slug**: MUST exist in `CATALOG_GENRES`; else `VALIDATION_ERROR` (not silent).
- **No raw passthrough**: serializers define explicit fields only; extra Jamendo keys
  are never forwarded (Principle IV).

## Settings additions (config/settings/base.py)

```text
JAMENDO_CLIENT_ID              (env, secret — already in .env)
JAMENDO_API_BASE_URL           (env, default https://api.jamendo.com/v3.0)
JAMENDO_REQUEST_TIMEOUT_SECONDS(env int, default 5)
JAMENDO_AUDIOFORMAT            (env, default "mp31")          # NEW key → add to .env.example
CACHE_TTL_TRENDING / _GENRES / _SEARCH / _DETAIL  (env int)  # already in .env.example
CATALOG_TRENDING_SIZE          (env int, default 50)
CATALOG_TRACKS_PAGE_SIZE_DEFAULT (env int, default 20)
CATALOG_TRACKS_PAGE_SIZE_MAX   (env int, default 50)
CATALOG_GENRES                 (list[{slug,name,tag}] constant, env-overridable)
```
