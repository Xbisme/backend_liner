# SoundWave Backend — Project Context

> Repo: `soundwave-backend` (Django + DRF)
> Repo liên quan: `soundwave-mobile` (Flutter) — độc lập, đồng bộ qua `contracts/openapi.yaml` + `.claude/api-context.md`
>
> Last updated: 2026-07-25 (BE-001 + BE-002 + BE-003 User Library đã merge vào main; BE-004 Security Hardening là spec kế tiếp)

## Snapshot

- **Vai trò repo này**: Backend cho app nghe nhạc SoundWave (placeholder name) — **proxy + cache Jamendo API** (Creative Commons, non-commercial), quản lý tài khoản người dùng thật (email/social login), playlist, liked tracks, lịch sử nghe.
- **Stack**: Django + DRF, PostgreSQL, Redis (cache response Jamendo + rate-limit quota), JWT (`djangorestframework-simplejwt`) cho user auth.
- **KHÔNG có S3/CDN cho audio** — file nhạc luôn stream thẳng từ Jamendo, backend không lưu trữ/transcode. Khác biệt lớn nhất so với kiến trúc LiveCanvas.
- **KHÔNG có admin upload pipeline** ở v1 — nội dung tự động từ Jamendo, không cần màn quản trị.
- **2 tầng auth**: `X-App-Key` (mọi request) + `Authorization: Bearer <user_access_token>` (endpoint `/me/*`, `/auth/logout`) — khác LiveCanvas ở chỗ đây là **user token thật**, không phải admin token.
- **Giới hạn pháp lý quan trọng**: Jamendo API chỉ miễn phí cho mục đích **phi thương mại**. Nếu sau này có ý định monetize (ads/premium), phải liên hệ Jamendo xin giấy phép thương mại trước — không tự ý thêm doanh thu vào app khi vẫn dùng free tier.
- **Communication**: Tiếng Việt giữa user + Claude · Tiếng Anh cho code/comment/commit.

## Current Focus

- **Trạng thái**: BE-001 + BE-002 + BE-003 đã merge vào `main`. **BE-004 (Security Hardening) triển khai xong** trên branch `BE-004-security-hardening` — rate limiting (per-scope, fail-open/closed), token lifecycle hardening (logout per-session, fail-fast khóa ký JWT), Sentry + scrub, CORS, IDOR sweep, cache load, OWASP review. Cross-cutting ở `core/`, **không model/migration mới**. **134 test toàn repo pass**; black/ruff/mypy xanh. Contract **v0.3.0** (thêm `RATE_LIMITED` 429). Chờ review/merge. **Spec kế tiếp: BE-005 (Deploy & Launch)**.
- **Đã có sẵn**: `docs/screen-inventory.md`, `contracts/openapi.yaml` **v0.2.0**, `.claude/api-context.md` v0.2.0 (draft, chờ review cùng phía mobile), `.specify/memory/constitution.md` v1.0.0, `.claude/dev-workflow.md`, `.claude/changelog.md`, `.claude/decisions/`, `specs/003-user-library/`.
- **Spec tiếp theo**: `BE-005-deploy-launch` (sau khi merge BE-004). **Đang treo**: báo mobile MO-002 (catalog thật + album/artist detail đã sẵn sàng) + freeze contract #000 cùng repo mobile (gồm `RATE_LIMITED` v0.3.0).
- **Đã quyết định**: Jamendo client_id thật (đã cấu hình trong `.env`); cache TTL theo loại (`CACHE_TTL_*` trong settings); genres = danh sách curated trong settings (`CATALOG_GENRES`).
- **Chưa quyết định**:
  - Google/Apple Sign-In credentials thật cho production (hiện `.env` để placeholder).
  - Freeze contract #000 chính thức cùng repo mobile (gồm 2 refinement pre-freeze: `User.email` nullable + `LimitParam` max 50).

## Repo Layout

```
.claude/
├── project-context.md
├── sdd-roadmap.md
├── dev-workflow.md
├── api-context.md
├── changelog.md
└── decisions/

contracts/
└── openapi.yaml

config/                       # Django settings, celery.py (nếu cần background refresh cache)
apps/
├── accounts/                  # User model, auth (email + social), JWT
├── catalog/                   # Jamendo proxy + cache layer
└── library/                   # Playlist, LikedTrack, ListeningHistory
requirements/
specs/                         # BE-NNN-*/ folders
docs/
├── PRD.md
└── screen-inventory.md
manage.py
```

## Key Documents

| File | Vai trò |
|---|---|
| [`../docs/screen-inventory.md`](../docs/screen-inventory.md) | Màn hình cần gì → đọc TRƯỚC khi sửa API |
| [`api-context.md`](api-context.md) | Chi tiết endpoint |
| [`../contracts/openapi.yaml`](../contracts/openapi.yaml) | Contract máy-đọc |
| [`sdd-roadmap.md`](sdd-roadmap.md) | Spec planning track backend |
| [`dev-workflow.md`](dev-workflow.md) | Quy trình speckit + Contract Sync |
