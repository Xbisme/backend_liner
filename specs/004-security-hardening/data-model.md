# Data Model — BE-004 Security Hardening

> BE-004 **không thêm/đổi model DB nào** → **không có migration mới**. "Dữ liệu" ở đây là cấu hình throttle (ephemeral trong Redis) và các bản ghi token đã tồn tại từ BE-001. Mục này mô tả các cấu trúc phi-DB để định hướng thiết kế.

## 1. Throttle scope map (cấu hình, không phải bảng)

Mỗi throttle class ↔ một scope ↔ một rate env-driven. Bộ đếm sống trong Redis (cache `default`), key theo DRF `SimpleRateThrottle.get_cache_key`, tự hết hạn theo cửa sổ.

| Throttle class (`core/throttling.py`) | Scope | Định danh (cache key ident) | Áp cho | fail_open |
|---|---|---|---|---|
| `AuthRateThrottle` | `auth` | IP client | `/auth/login`, `/auth/register`, `/auth/social-login` | **False** (fail-closed) |
| `CatalogRateThrottle` | `catalog` | IP client | tất cả `GET /catalog/*` | True |
| `UserWriteRateThrottle` | `user_write` | `user.pk` | ghi `/me/*` (playlist CRUD, track add/remove/reorder, like/unlike, DELETE /me) | True |
| `HistoryRateThrottle` | `history` | `user.pk` | `POST /me/history` | True |

- **Isolation** (FR-006): cache key gồm scope + ident (user pk / IP) → bucket của A tách bucket của B.
- **IP an toàn sau proxy** (FR-002): dùng DRF `NUM_PROXIES` (settings, env `NUM_PROXIES` default 0) để `get_ident` bóc đúng số hop `X-Forwarded-For`; không tin XFF mù quáng.
- **Store lỗi** (FR-006a): base `_ResilientThrottle` bắt exception từ `cache`; `fail_open` quyết định cho qua hay chặn.

## 2. Settings mới (env-driven — Constitution VI)

| Setting | Env var | Default | Ghi chú |
|---|---|---|---|
| `DEFAULT_THROTTLE_RATES["auth"]` | `THROTTLE_AUTH` | `10/min` | per-IP |
| `DEFAULT_THROTTLE_RATES["user_write"]` | `THROTTLE_USER` | `60/min` | per-user |
| `DEFAULT_THROTTLE_RATES["history"]` | `THROTTLE_HISTORY` | `120/min` | per-user |
| `DEFAULT_THROTTLE_RATES["catalog"]` | `THROTTLE_CATALOG` | `120/min` | per-IP |
| `NUM_PROXIES` | `NUM_PROXIES` | `0` | số hop proxy tin cậy cho client IP |
| `JWT_MIN_SECRET_BYTES` | `JWT_MIN_SECRET_BYTES` | `32` | ngưỡng fail-fast khóa ký |
| `CORS_ALLOWED_ORIGINS` | `CORS_ALLOWED_ORIGINS` | `[]` | đã có; nay được `corsheaders` thực thi |
| `SENTRY_DSN` | `SENTRY_DSN` | `""` | đã có; nay có dep + scrubber |

## 3. Token records (đã tồn tại — BE-001, KHÔNG đổi schema)

Từ `rest_framework_simplejwt.token_blacklist` (đã `INSTALLED_APPS` + migration):

- **`OutstandingToken`**: mọi refresh token đã phát (jti, user, expires_at). Dùng bởi `revoke_all` (giữ cho `DELETE /me`, không cho logout thường).
- **`BlacklistedToken`**: token đã thu hồi (rotation/logout). Refresh dùng token đã blacklist → `TokenError` → `TOKEN_INVALID`.

**Thay đổi hành vi (không đổi schema)** — `apps/accounts`:
- `LogoutView`: bỏ nhánh `revoke_all` khi thiếu `refresh_token`; logout **chỉ** blacklist token được trình (FR-008). Thiếu/không hợp lệ → idempotent `204` (FR-011), không 500.
- `tokens.revoke`: giữ; logout nuốt `TokenError` (đã thu hồi/hết hạn = coi như thành công per-session).

## 4. State transitions — refresh token

```
issued (OutstandingToken)
   │  refresh_tokens(): blacklist cũ → phát mới (rotation)
   ▼
rotated: cũ ∈ BlacklistedToken  → dùng lại cũ = TOKEN_INVALID (FR-007)
   │  logout(presented): blacklist token đang cầm
   ▼
revoked: ∈ BlacklistedToken     → refresh = TOKEN_INVALID (FR-008)
   │  hết hạn tự nhiên
   ▼
expired                          → TOKEN_EXPIRED (access) / TOKEN_INVALID (refresh) (FR-009)
```

## 5. Không có

- Không bảng mới, không field mới, không migration.
- Không lưu event Sentry trong DB (gửi ngoài, đã scrub — mục 7 research).
- Không lưu bộ đếm throttle lâu dài (ephemeral Redis, tự hết hạn).
