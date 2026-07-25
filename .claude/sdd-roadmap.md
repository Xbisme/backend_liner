# SoundWave Backend v1.0 — Spec Roadmap

> Repo: `soundwave-backend`. Track song song bên `soundwave-mobile` (spec `MO-NNN`).
> Last updated: 2026-07-24 (Chưa có spec nào merge)

## Dependency Graph

```
Spec #000: API Contract Freeze          ← SHARED — phối hợp với repo mobile
    │
    ▼
BE-001: Backend Foundation & Auth
(Django+DRF skeleton, PostgreSQL, Redis,
 JWT user auth, Google/Apple Sign-In verify,
 /auth/* endpoints, X-App-Key middleware)
    │
    ▼
BE-002: Catalog Proxy                    ⇄ Điểm đồng bộ: mobile cần API này
(Jamendo client wrapper, cache Redis,          thật trước khi merge MO-002
 /catalog/trending, /catalog/genres,
 /catalog/tracks (cursor), /catalog/tracks/{id},
 /catalog/artists/{id}, /catalog/albums/{id})
    │
    ▼
BE-003: User Library
(Playlist CRUD, reorder, liked-tracks,
 listening history — toàn bộ /me/*)
    │
    ▼
BE-004: Security Hardening & Production Readiness
(Rate limit, refresh token rotation/revoke,
 Sentry, load test cache layer)
    │
    ▼
BE-005: Deploy & Launch Support
```

## Spec Details

### Spec #000: API Contract Freeze
- **Status**: 🟡 In progress
- Review `contracts/openapi.yaml` + `.claude/api-context.md` cùng repo mobile. Thứ tự bắt buộc: `docs/screen-inventory.md` trước, rồi mới tới contract.

### BE-001: Backend Foundation & Auth
- **Branch**: `BE-001-backend-foundation-auth`
- **Depends on**: #000
- **Scope**: Django+DRF skeleton; `apps/accounts` (User model, email/password auth, JWT access+refresh); verify Google ID token (`google-auth`) và Apple Sign-In (`python-jose` verify JWS từ Apple); `POST /auth/register|login|social-login|refresh|logout`; middleware `X-App-Key`.

### BE-002: Catalog Proxy
- **Branch**: `BE-002-catalog-proxy`
- **Depends on**: BE-001
- **Scope**: `apps/catalog` — client wrapper gọi Jamendo API (client_id riêng, không lộ ra client); cache Redis (TTL khác nhau: `trending`/`genres` cache dài, `search` cache ngắn); map response Jamendo sang schema `Track`/`Artist`/`Album` trong `openapi.yaml`; xử lý `502 CATALOG_UPSTREAM_ERROR` khi Jamendo timeout/rate-limit.
- **⚠️ Điểm đồng bộ**: báo mobile khi merge — chuyển từ mock sang API thật (MO-002).

### BE-003: User Library
- **Branch**: `BE-003-user-library`
- **Depends on**: BE-002
- **Scope**: `apps/library` — model `Playlist`, `PlaylistTrack` (lưu `track_id` Jamendo + thứ tự), `LikedTrack`, `ListeningHistory`; toàn bộ endpoint `/me/*`; kiểm tra `FORBIDDEN` khi thao tác playlist không thuộc user hiện tại (không dựa vào client tự khai `user_id`).

### BE-004: Security Hardening & Production Readiness
- **Branch**: `BE-004-security-hardening`
- **Depends on**: BE-003
- **Scope**: Rate limit theo user (chống spam `/me/history`), refresh token rotation + blacklist khi logout, Sentry, load test cache layer catalog, OWASP review (đặc biệt IDOR ở `/me/playlists/{id}`).

### BE-005: Deploy & Launch Support
- **Branch**: `BE-005-deploy-launch`
- **Depends on**: BE-004
- **Scope**: Staging → Production, backup PostgreSQL định kỳ, runbook.
- **⚠️ Điểm đồng bộ**: báo mobile khi production sẵn sàng (MO-005).
