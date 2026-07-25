# API Context — SoundWave

> Companion đọc-được-cho-người/LLM của [`contracts/openapi.yaml`](../contracts/openapi.yaml), suy ra từ [`docs/screen-inventory.md`](../docs/screen-inventory.md). Tồn tại độc lập ở CẢ 2 REPO, đồng bộ tay (xem "Contract Sync" trong `dev-workflow.md`).
>
> Last updated: 2026-07-24 · Contract version: **`v0.1.0`**

## Quy ước chung

### Auth Headers

| Header | Dùng cho |
|---|---|
| `X-App-Key` | **Mọi** endpoint (kể cả anonymous) |
| `Authorization: Bearer <user_access_token>` | Toàn bộ `/me/*` + `/auth/logout` — thêm vào cùng với `X-App-Key`, không thay thế |

`access_token` sống ngắn (khuyến nghị 15-30 phút), dùng `POST /auth/refresh` với `refresh_token` (sống dài, revoke được) để lấy token mới — client tự động refresh khi gặp `401` với code `TOKEN_EXPIRED`.

### Cursor Pagination

Giống chuẩn LiveCanvas: `?cursor=...&limit=...` → `{ items, next_cursor, has_more }`. Áp dụng cho `catalog/tracks`, `me/liked-tracks`, `me/playlists`, `me/history`.

### Error Code Catalog

| Code | HTTP | Ý nghĩa |
|---|---|---|
| `INVALID_APP_KEY` | 401 | Thiếu/sai `X-App-Key` |
| `UNAUTHORIZED_USER` | 401 | Thiếu `Authorization` ở endpoint cần login |
| `TOKEN_EXPIRED` | 401 | `access_token` hết hạn — client gọi `/auth/refresh` |
| `TOKEN_INVALID` | 401 | `refresh_token`/`access_token` sai hoặc đã bị revoke |
| `FORBIDDEN` | 403 | Thao tác trên resource không thuộc user hiện tại (vd sửa playlist người khác) |
| `EMAIL_ALREADY_EXISTS` | 409 | Đăng ký với email đã tồn tại |
| `INVALID_CREDENTIALS` | 401 | Sai email/password lúc login |
| `SOCIAL_TOKEN_INVALID` | 400 | `id_token` Google/Apple không verify được |
| `VALIDATION_ERROR` | 400 | Body/query sai định dạng |
| `NOT_FOUND` | 404 | Resource không tồn tại |
| `TRACK_ALREADY_IN_PLAYLIST` | 409 | Thêm track đã có sẵn trong playlist |
| `REORDER_MISMATCH` | 400 | `track_ids` gửi lên không khớp track thực tế trong playlist |
| `CATALOG_UPSTREAM_ERROR` | 502 | Jamendo API lỗi/timeout — client nên retry sau vài giây |

Format chung: `{ "error": { "code": "...", "message": "..." } }`

---

## Auth Endpoints

### `POST /auth/register`
- Header: `X-App-Key`
- Body: `{ "email": "a@b.com", "password": "minimum8ky tu", "display_name": "Bao Phan" }`
- **201**: `AuthTokenResponse` — `{ access_token, refresh_token, expires_in, user }`
- **409**: `EMAIL_ALREADY_EXISTS`

### `POST /auth/login`
- Header: `X-App-Key`
- Body: `{ "email": "a@b.com", "password": "..." }`
- **200**: `AuthTokenResponse`
- **401**: `INVALID_CREDENTIALS`

### `POST /auth/social-login`
- Header: `X-App-Key`
- Body: `{ "provider": "google", "id_token": "<token từ Google/Apple SDK>" }`
- **200**: `AuthTokenResponse` (tự tạo user nếu lần đầu đăng nhập)
- **400**: `SOCIAL_TOKEN_INVALID`

### `POST /auth/refresh`
- Header: `X-App-Key`
- Body: `{ "refresh_token": "..." }`
- **200**: `AuthTokenResponse` mới
- **401**: `TOKEN_INVALID`

### `POST /auth/logout`
- Header: `X-App-Key`, `Authorization: Bearer <access_token>`
- **204**: refresh_token hiện tại bị revoke

---

## Catalog Endpoints (proxy Jamendo, có cache)

### `GET /catalog/trending`
- Header: `X-App-Key` · Query: `genre` (optional)
- **200**: mảng `Track`

### `GET /catalog/genres`
- Header: `X-App-Key`
- **200**: `[{ "slug": "ambient", "name": "Ambient" }]`

### `GET /catalog/tracks`
- Header: `X-App-Key` · Query: `cursor`, `limit`, `search`, `genre`
- **200**: `TrackCursorPage`
```json
{
  "items": [{
    "id": "1234567",
    "title": "Night Drive",
    "artist": { "id": "998", "name": "Aeon Waves", "image_url": "https://..." },
    "album": { "id": "555", "title": "Synth Horizons", "artist": {"...": "..."}, "cover_url": "https://..." },
    "genres": [{ "slug": "synthwave", "name": "Synthwave" }],
    "duration_seconds": 214,
    "cover_url": "https://usercontent.jamendo.com/...",
    "stream_url": "https://prod-1.storage.jamendo.com/...",
    "license_type": "CC BY-NC-SA",
    "is_liked": false
  }],
  "next_cursor": "eyJvZmZzZXQiOjIwfQ==",
  "has_more": true
}
```
- **502**: `CATALOG_UPSTREAM_ERROR` — Jamendo timeout, client hiện thông báo thử lại

### `GET /catalog/tracks/{id}` · `GET /catalog/artists/{id}` · `GET /catalog/albums/{id}`
- Header: `X-App-Key`
- **200**: object tương ứng · **404**: `NOT_FOUND`

---

## User Endpoints (`/me/*`)

Tất cả yêu cầu `X-App-Key` + `Authorization: Bearer <access_token>`.

### `GET /me`
- **200**: `User` object · **401**: `TOKEN_EXPIRED`/`UNAUTHORIZED_USER`

### `DELETE /me`
- **204**: xóa tài khoản + toàn bộ playlist/liked/history liên quan

### `GET /me/liked-tracks`
- Query: `cursor`, `limit` · **200**: `TrackCursorPage`

### `POST /me/liked-tracks/{track_id}`
- **204**: like thành công (gọi lại track đã like vẫn `204`, không lỗi — idempotent)

### `DELETE /me/liked-tracks/{track_id}`
- **204**: bỏ like

### `GET /me/playlists`
- Query: `cursor`, `limit`
- **200**: `{ items: Playlist[], next_cursor, has_more }`

### `POST /me/playlists`
- Body: `{ "name": "Chill tối nay" }`
- **201**: `Playlist` (rỗng, `track_count: 0`)

### `GET /me/playlists/{id}`
- **200**: `PlaylistDetail` (kèm mảng `tracks`)
- **403**: `FORBIDDEN` (playlist người khác) · **404**: `NOT_FOUND`

### `PATCH /me/playlists/{id}`
- Body: `{ "name": "Tên mới" }` · **200**: `Playlist`

### `DELETE /me/playlists/{id}`
- **204**: đã xóa · **403**: `FORBIDDEN`

### `POST /me/playlists/{id}/tracks`
- Body: `{ "track_id": "1234567" }`
- **204**: đã thêm (cuối danh sách) · **409**: `TRACK_ALREADY_IN_PLAYLIST`

### `DELETE /me/playlists/{id}/tracks/{track_id}`
- **204**: đã xóa khỏi playlist

### `PATCH /me/playlists/{id}/tracks/reorder`
- Body: `{ "track_ids": ["1234567", "998877", "..."] }` (toàn bộ danh sách theo thứ tự mới)
- **200**: `PlaylistDetail` · **400**: `REORDER_MISMATCH`

### `GET /me/history`
- Query: `cursor`, `limit` · **200**: `TrackCursorPage` (sắp theo `played_at` giảm dần)

### `POST /me/history`
- Body: `{ "track_id": "1234567", "played_at": "2026-07-24T20:10:00Z", "completed": true }`
- **201**: ghi nhận thành công — gọi khi track kết thúc hoặc user chuyển bài giữa chừng (`completed: false`)
