# Data Model: User Library (BE-003)

App: `apps/library`. Owner is always `accounts.User` (FK, `on_delete=CASCADE`) so `DELETE /me` removes all rows with no orphans (FR-019, Constitution VII). All models store `track_id` as an opaque **string** referencing Jamendo — **never** a FK to catalog and **never** any song metadata (FR-004).

## Entities

### Playlist
| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField (PK) | contract `Playlist.id: integer` |
| `owner` | FK → `accounts.User`, `related_name="playlists"`, `CASCADE` | IDOR scope key |
| `name` | CharField(max_length=`PLAYLIST_NAME_MAX_LENGTH`=200) | validated non-blank (FR-012) |
| `created_at` | DateTimeField(`auto_now_add=True`) | |
| `updated_at` | DateTimeField(`auto_now=True`) | cursor key; **must be bumped on track add/remove/reorder** (see note) |

- **Meta**: `db_table = "library_playlist"`; `ordering = ["-updated_at", "-id"]`; `indexes = [Index(fields=["owner", "-updated_at", "-id"])]`.
- `track_count` (contract) and `cover_url` (contract: composed from first ≤4 track covers, null if empty) are **derived** at serialization, not stored.
- **updated_at bump**: track mutations change child rows, not the Playlist row, so `auto_now` won't fire. Services that add/remove/reorder tracks must `Playlist.objects.filter(pk=...).update(updated_at=timezone.now())` (or `save(update_fields=["updated_at"])`) in the same transaction so recency ordering (FR-007) is correct.
- **Name uniqueness**: none — a user may have duplicate names (spec Assumption).

### PlaylistTrack
| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField (PK) | |
| `playlist` | FK → `Playlist`, `related_name="tracks"`, `CASCADE` | delete playlist ⇒ delete its tracks (FR-008) |
| `track_id` | CharField(max_length=64) | Jamendo id string |
| `position` | PositiveIntegerField | 0-based order within playlist |
| `added_at` | DateTimeField(`auto_now_add=True`) | |

- **Meta**: `db_table = "library_playlist_track"`; `ordering = ["position"]`;
  `constraints = [UniqueConstraint(fields=["playlist", "track_id"], name="uniq_playlist_track"), UniqueConstraint(fields=["playlist", "position"], name="uniq_playlist_position", deferrable=Deferred?)]`.
- Adding a duplicate `track_id` → caught as `TRACK_ALREADY_IN_PLAYLIST` (409, FR-009); enforced by the unique constraint + a pre-check in the service.
- New track appends at `position = max(existing)+1` (0 if empty).
- **Reorder** rewrites `position` for all rows in one `transaction.atomic()` after validating the submitted `track_ids` are an exact permutation (FR-011). To avoid transient collisions on the `(playlist, position)` unique constraint during rewrite, either make that constraint `DEFERRABLE INITIALLY DEFERRED` (Postgres) or two-phase the update (offset positions, then set final) — decided at implementation; both keep ordering stable and unique.

### LikedTrack
| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField (PK) | |
| `user` | FK → `accounts.User`, `related_name="liked_tracks"`, `CASCADE` | |
| `track_id` | CharField(max_length=64) | |
| `created_at` | DateTimeField(`auto_now_add=True`) | cursor key (recency) |

- **Meta**: `db_table = "library_liked_track"`; `ordering = ["-created_at", "-id"]`;
  `constraints = [UniqueConstraint(fields=["user", "track_id"], name="uniq_user_liked_track")]`;
  `indexes = [Index(fields=["user", "-created_at", "-id"])]`.
- Like = `get_or_create(user, track_id)` → **204** whether created or already present (idempotent, FR-013). Unlike = `filter(user, track_id).delete()` → **204** even if nothing deleted (FR-014).

### ListeningHistory
| Field | Type | Notes |
|---|---|---|
| `id` | BigAutoField (PK) | |
| `user` | FK → `accounts.User`, `related_name="history"`, `CASCADE` | |
| `track_id` | CharField(max_length=64) | |
| `played_at` | DateTimeField | body value or `timezone.now()`; future/invalid → `VALIDATION_ERROR` (FR-018) |
| `completed` | BooleanField(default=False) | listened-through vs skipped |

- **Meta**: `db_table = "library_listening_history"`; `ordering = ["-played_at", "-id"]`;
  `constraints = [UniqueConstraint(fields=["user", "track_id"], name="uniq_user_history_track")]`;
  `indexes = [Index(fields=["user", "-played_at", "-id"])]`.
- Record = `update_or_create(user, track_id, defaults={played_at, completed})` → **distinct per track** (FR-016/017). After write, trim to newest `settings.HISTORY_MAX_ENTRIES` (default 100) rows for the user (FR-017a).

## Relationships

```
accounts.User 1───∞ Playlist 1───∞ PlaylistTrack   (track_id: str → Jamendo)
      │
      ├────────∞ LikedTrack        (track_id: str → Jamendo)
      └────────∞ ListeningHistory  (track_id: str → Jamendo)
```

All FKs `CASCADE` from `User`, so `request.user.delete()` in the existing `MeView.delete` (BE-001) already removes every library row — a test asserts zero orphans (SC-005). No change to `MeView` needed.

## Migration

- `apps/library/migrations/0001_initial.py` — creates the four tables + constraints + indexes above. Non-destructive (new tables only); no data backfill. Committed and reviewed (Constitution VII).
- `apps/library` added to `INSTALLED_APPS` in `config/settings/base.py`.
- `python manage.py makemigrations --check --dry-run` must be clean after generation.

## Settings additions (`config/settings/base.py`, env-driven — Constitution VI)

```python
# --- User library — BE-003 ---
HISTORY_MAX_ENTRIES = env.int("HISTORY_MAX_ENTRIES", default=100)
LIBRARY_PAGE_SIZE_DEFAULT = env.int("LIBRARY_PAGE_SIZE_DEFAULT", default=20)
LIBRARY_PAGE_SIZE_MAX = env.int("LIBRARY_PAGE_SIZE_MAX", default=50)
PLAYLIST_NAME_MAX_LENGTH = env.int("PLAYLIST_NAME_MAX_LENGTH", default=200)
```

## Derived / non-stored fields

| Contract field | Source |
|---|---|
| `Playlist.track_count` | `playlist.tracks.count()` (or annotated `Count`) |
| `Playlist.cover_url` | compose from first ≤4 hydrated track `cover_url`s; `null` if empty |
| `Track.is_liked` (in library responses) | membership in the user's liked-track set for the page (research §5) |
| `Track.available` | `True` when hydrated from upstream; `False` tombstone when id unresolved (research §1) |
