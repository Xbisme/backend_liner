# Contract: User Library `/me/*` endpoints (BE-003)

**Status vs `contracts/openapi.yaml`**: all paths and request/response schemas below **already exist** in the frozen-draft contract (`v0.1.0`). BE-003 implements them as-is. The **only change** is an additive field on `Track` (§ Track.available). Authoring order (Constitution II): update `openapi.yaml` + `.claude/api-context.md` **before** code.

All endpoints require **both** auth layers: `X-App-Key` (Layer-1 middleware) **and** `Authorization: Bearer <access_token>` (Layer-2, `IsAuthenticated`). Ownership derives from the token only. Errors use the standard envelope `{ "error": { "code", "message" } }`.

## Endpoints

| Method & path | Request | Success | Errors |
|---|---|---|---|
| `GET /me/playlists` | `?cursor=&limit=` | `200` `{ items: Playlist[], next_cursor, has_more }` sorted `updated_at` desc | `VALIDATION_ERROR` (bad cursor/limit) |
| `POST /me/playlists` | `CreatePlaylistRequest {name}` | `201` `Playlist` (empty, `track_count:0`, `cover_url:null`) | `VALIDATION_ERROR` (blank/too-long name) |
| `GET /me/playlists/{id}` | — | `200` `PlaylistDetail` (`tracks[]` hydrated, in order) | `FORBIDDEN` (other user), `NOT_FOUND`, `CATALOG_UPSTREAM_ERROR` (hydrate down) |
| `PATCH /me/playlists/{id}` | `UpdatePlaylistRequest {name}` | `200` `Playlist` | `FORBIDDEN`, `NOT_FOUND`, `VALIDATION_ERROR` |
| `DELETE /me/playlists/{id}` | — | `204` | `FORBIDDEN`, `NOT_FOUND` |
| `POST /me/playlists/{id}/tracks` | `AddTrackToPlaylistRequest {track_id}` | `204` (appended at end) | `FORBIDDEN`, `NOT_FOUND`, `TRACK_ALREADY_IN_PLAYLIST` (409), `VALIDATION_ERROR` |
| `DELETE /me/playlists/{id}/tracks/{track_id}` | — | `204` (idempotent — 204 even if track absent) | `FORBIDDEN`, `NOT_FOUND` (playlist) |
| `PATCH /me/playlists/{id}/tracks/reorder` | `ReorderPlaylistRequest {track_ids[]}` (full new order) | `200` `PlaylistDetail` | `FORBIDDEN`, `NOT_FOUND`, `REORDER_MISMATCH` (400) |
| `GET /me/liked-tracks` | `?cursor=&limit=` | `200` `TrackCursorPage` (all `is_liked:true`) sorted like-recency desc | `VALIDATION_ERROR`, `CATALOG_UPSTREAM_ERROR` |
| `POST /me/liked-tracks/{track_id}` | — | `204` (idempotent) | — |
| `DELETE /me/liked-tracks/{track_id}` | — | `204` (idempotent — 204 even if not liked) | — |
| `GET /me/history` | `?cursor=&limit=` | `200` `TrackCursorPage` sorted `played_at` desc, **distinct per track** | `VALIDATION_ERROR`, `CATALOG_UPSTREAM_ERROR` |
| `POST /me/history` | `LogHistoryRequest {track_id, played_at?, completed?}` | `201` | `VALIDATION_ERROR` (future/invalid `played_at`) |

Notes:
- `403 FORBIDDEN` is returned for a resource that exists but belongs to another user (matches existing `openapi.yaml` descriptions "Playlist thuộc user khác"). `404 NOT_FOUND` only when the id does not exist at all.
- `limit`: default `LIBRARY_PAGE_SIZE_DEFAULT` (20), max `LIBRARY_PAGE_SIZE_MAX` (50), same clamp rule as catalog.
- Hydrated lists (`liked-tracks`, `history`, playlist `tracks`) fetch metadata at read time; a globally-unreachable upstream → `502 CATALOG_UPSTREAM_ERROR`; individual unresolved ids → tombstone items (`available:false`), not an error.

## Contract change: `Track.available` (additive)

The only edit to `contracts/openapi.yaml`. In `components.schemas.Track`:

```yaml
    Track:
      type: object
      properties:
        id: { type: string, description: "Jamendo track id" }
        available:
          type: boolean
          default: true
          description: >
            false = "tombstone": track không còn tra được từ nguồn nhạc; các field
            metadata bên dưới là null. Endpoint catalog luôn trả true.
        title: { type: string, nullable: true }
        artist: { allOf: [ { $ref: '#/components/schemas/Artist' } ], nullable: true }
        album:  { allOf: [ { $ref: '#/components/schemas/Album' } ],  nullable: true }
        genres:
          type: array
          items: { $ref: '#/components/schemas/Genre' }
        duration_seconds: { type: integer, nullable: true }
        cover_url: { type: string, format: uri, nullable: true }
        stream_url: { type: string, format: uri, nullable: true }
        license_type: { type: string, example: "CC BY-NC-SA", nullable: true }
        is_liked: { type: boolean }
```

- **Not a breaking change**: additive optional field; existing catalog responses always send `available:true` with full metadata, so mobile's current parsing keeps working. Version stays `v0.1.0` (draft) with a changelog note; confirm at freeze #000 (Contract Sync).
- Mirror the change in `.claude/api-context.md` (Track JSON example + one line describing `available`/tombstone), and add a changelog entry.

## Implementation-side serializer impact (`apps/catalog/serializers.py`)

`TrackSerializer` gains `available = BooleanField(default=True)` and makes metadata fields `allow_null=True` (so tombstones serialize). Catalog Layer-1 responses are unchanged in practice (mapper always sets `available=True`, full metadata). `PlaylistSerializer`/`PlaylistDetailSerializer` are added in `apps/library/serializers.py` matching `Playlist`/`PlaylistDetail`.
