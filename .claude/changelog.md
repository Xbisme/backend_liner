# Changelog — SoundWave Backend

Định dạng theo [Keep a Changelog](https://keepachangelog.com/). Ghi lại thay
đổi đáng chú ý ở tầng repo/contract (không phải mọi commit). Contract version đi
riêng, xem `api-context.md`.

## [Unreleased]

### Added
- `.specify/memory/constitution.md` v1.0.0 — 14 nguyên tắc cốt lõi cho backend
  Django+DRF (auth 2 tầng/IDOR, contract-first, proxy Jamendo, không hardcode…).
- Scaffolding repo: `README.md`, `.gitignore`, `.env.example`.
- `.claude/dev-workflow.md` (Spec Kit + Contract Sync), `.claude/changelog.md`,
  `.claude/decisions/` (ADR).

### Changed
- Chuyển `openapi.yaml` → `contracts/openapi.yaml` và `screen-inventory.md` →
  `docs/screen-inventory.md` cho khớp layout trong `project-context.md`; sửa
  link tương ứng trong `api-context.md`.
- **Contract refinement (pre-freeze, vẫn v0.1.0 draft)** từ BE-001 clarify:
  `User.email` đánh dấu `nullable: true` (tài khoản social-only có thể không có
  email; định danh bằng `provider + subject_id`); ghi chú cách suy ra
  `auth_provider`. ⚠️ Cần xác nhận cùng repo mobile khi freeze contract #000.

- **BE-001 Backend Foundation & Auth — triển khai xong** (branch
  `BE-001-backend-foundation-auth`): Django 5.2 + DRF skeleton, settings split
  env-driven, `core/` (error envelope, X-App-Key middleware, JWT auth typed
  errors, cursor pagination, log redaction), custom `User` (email nullable) +
  `SocialIdentity`, SimpleJWT rotation+blacklist; endpoints `/auth/register|
  login|social-login|refresh|logout`, `GET/DELETE /me`. Google (google-auth) +
  Apple (PyJWT) verify. 26 tests pass; black/ruff/mypy xanh.

- **BE-002 Catalog Proxy — triển khai xong** (branch `BE-002-catalog-proxy`):
  `apps/catalog` (models-free proxy + cache Jamendo). `JamendoClient` (httpx,
  timeout từ settings) là điểm truy cập upstream duy nhất — inject `client_id`
  (không lộ), dịch mọi lỗi upstream (timeout/5xx/429/`status:failed`) →
  `502 CATALOG_UPSTREAM_ERROR`, detail rỗng → `404`. Mapper JSON→schema
  `Track/Artist/Album/Genre`, cache Redis TTL theo loại (`get_or_fetch`, key
  namespaced), offset-cursor riêng (`{items,next_cursor,has_more}`), genres từ
  danh sách curated trong settings (không gọi upstream). Endpoints
  `GET /catalog/trending|genres|tracks|tracks/{id}|artists/{id}|albums/{id}`,
  Layer-1 `X-App-Key` (không cần user token). 39 test mới (mapper/client/cache/
  API, Jamendo mock qua `httpx.MockTransport`); 65 test toàn repo pass;
  black/ruff/mypy xanh, không có migration. Dep mới: `httpx==0.28.1`.
  ⚠️ **Điểm đồng bộ MO-002**: khi merge, báo mobile chuyển từ mock sang API thật.

- **Contract refinement (pre-freeze, vẫn v0.1.0 draft)** từ BE-002: `LimitParam`
  `maximum` 100 → **50** (khớp quyết định clarify catalog); thêm schema `Artist`/
  `Album` cho response `200` của `/catalog/artists|albums/{id}`; ghi rõ ràng buộc
  `limit`/`search`/`genre` trong `api-context.md`. ⚠️ Xác nhận cùng mobile khi
  freeze #000.

### Status
- Contract `v0.1.0` (draft) chờ freeze #000 cùng repo mobile. BE-002 (Catalog
  Proxy) đã xong; **BE-003 (User Library)** là spec kế tiếp.
