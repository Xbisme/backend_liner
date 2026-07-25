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

- **Contract refinement (pre-freeze, vẫn v0.1.0 draft)** từ BE-003: (1) `Track`
  thêm field `available: boolean` (default true) và cho phép mọi field metadata
  `nullable` — hỗ trợ **tombstone** khi track đã lưu không còn tra được từ nguồn;
  (2) `LogHistoryRequest.played_at` chuyển thành **optional** (`required: [track_id]`)
  — server mặc định thời điểm hiện tại nếu thiếu. Cả hai additive/nới lỏng, không
  breaking. Cập nhật `openapi.yaml` + `api-context.md`. ⚠️ Xác nhận cùng mobile khi
  freeze #000.

- **BE-003 User Library — triển khai xong** (branch `BE-003-user-library`):
  `apps/library` — models `Playlist`, `PlaylistTrack` (`track_id` Jamendo +
  `position`), `LikedTrack`, `ListeningHistory`; toàn bộ `/me/*` (playlist CRUD +
  add/remove/reorder, liked idempotent, history distinct+cap). IDOR-proof qua
  `selectors.get_owned_playlist_or_error` (403 cross-user, 404 khi thật sự không
  tồn tại). Không lưu metadata bài hát — hydrate lúc đọc qua public
  `catalog.get_tracks_by_ids` (batch 1 call/trang, tái dùng cache per-id, tombstone
  cho id chết, 502 khi upstream lỗi toàn cục). Keyset cursor (`updated_at`/
  `created_at`/`played_at`). Settings mới: `HISTORY_MAX_ENTRIES`,
  `LIBRARY_PAGE_SIZE_*`, `PLAYLIST_NAME_MAX_LENGTH`. Migration `library/0001`.
  39 test mới (playlists/IDOR/liked/history/hydration/cascade); **104 test toàn
  repo pass**; black/ruff/mypy xanh. Không dep mới.

- **Contract `v0.2.0` (mobile MO-002)** — theo yêu cầu phía mobile: `GET
  /catalog/albums/{id}` trả **`AlbumDetail`** (`Album` + `tracks[]`), `GET
  /catalog/artists/{id}` trả **`ArtistDetail`** (`Artist` + `tracks[]` +
  `albums[]`). Backend (`apps/catalog`) bổ sung: `jamendo.get_album`/`get_artist`
  dùng `/albums/tracks`·`/artists/tracks` (đã verify shape qua Jamendo docs —
  Constitution XIV), `/albums?artist_id=` cho albums; mapper `map_album_detail`/
  `map_artist_detail` (inject parent artist/album vào nested track); serializers
  `AlbumDetailSerializer`/`ArtistDetailSerializer`. Additive → không breaking. Bump
  contract `v0.1.0 → v0.2.0`.

- **BE-004 Security Hardening & Production Readiness — triển khai xong** (branch
  `BE-004-security-hardening`): cross-cutting ở `core/` + `config/settings/`, không
  app/model mới → không migration. (1) **Rate limiting**: `core/throttling.py`
  (throttle per-scope: auth per-IP fail-closed, catalog per-IP, ghi `/me/*` per-user,
  history per-user — fail-open khi Redis lỗi); rates settings-driven
  (`THROTTLE_AUTH|CATALOG|USER|HISTORY`, `NUM_PROXIES`); áp per-view. (2) **Token
  lifecycle**: logout per-session idempotent (bỏ `revoke_all` vô tình), fail-fast
  khóa ký JWT <32 bytes ở production + deploy check (`core/checks.py`). (3)
  **Observability**: `core/observability.py` — Sentry env-driven + `before_send`
  scrub secret/PII (kép với log redaction); log ngữ cảnh sự cố upstream Jamendo
  (endpoint/status/latency). (4) **Audit & load**: CORS thực thi (`django-cors-headers`),
  IDOR sweep liked/history, cache-hit chống stampede, `owasp-review.md`. Dep mới:
  `django-cors-headers==4.9.0`, `sentry-sdk` (2.20.0→2.66.1, chuyển sang base.txt).
  **30 test mới; 134 test toàn repo pass**; black/ruff/mypy xanh; không migration.
  ADR `0002` (định danh throttle + fail mode).

- **Contract `v0.3.0` (BE-004)** — additive, không breaking: thêm mã lỗi
  **`RATE_LIMITED` (429)** + header **`Retry-After`** vào `openapi.yaml` (response
  `RateLimited`) + `api-context.md` (Error Code Catalog + mục Rate limiting) +
  `screen-inventory.md` (ghi chú cross-cutting). Bump `v0.2.0 → v0.3.0`. ⚠️ Đồng bộ
  mobile khi freeze #000.

### Fixed
- **Google social-login trả 500 thay vì 400** (phát hiện khi curl end-to-end): dep
  `requests` thiếu — `google.auth.transport.requests` cần nó nhưng `google-auth`
  không kéo về; import nằm ngoài try/except nên `ImportError` → 500. Bug BE-001 tiềm
  ẩn (test mock `verify_social_token` nên đường verify thật chưa từng chạy). Thêm
  `requests==2.34.2` vào `requirements/base.txt`. Nay token sai → `400
  SOCIAL_TOKEN_INVALID` đúng chuẩn.
- **Catalog trending trả rỗng** (phát hiện khi curl thật lúc review BE-004): Jamendo
  order `popularity_month`/`popularity_week` trả 0 kết quả ở free tier. Chuyển
  `JAMENDO_TRENDING_ORDER` từ hằng số `constants.py` → **settings env-driven**
  (`config/settings/base.py`, default `popularity_total` — hoạt động), cập nhật
  `jamendo.py` đọc từ settings + `.env.example`. `/catalog/trending` nay trả 50 track
  thật. Không breaking (Constitution VI: tunable env-driven).

### Status
- Contract **`v0.3.0`** (draft) chờ freeze #000 cùng repo mobile. BE-001 + BE-002
  + **BE-003 (User Library) đã merge vào `main`** (PR #3, commit `9c7a87f`; kèm
  catalog `AlbumDetail`/`ArtistDetail` cho MO-002). **BE-004 (Security Hardening)
  triển khai xong** trên branch `BE-004-security-hardening`, chờ review/merge. Spec
  kế tiếp: **BE-005 (Deploy & Launch)**. ⚠️ Treo: báo mobile MO-002 + freeze
  contract #000 (gồm `RATE_LIMITED`).
