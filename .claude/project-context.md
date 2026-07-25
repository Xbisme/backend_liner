# SoundWave Backend — Project Context

> Repo: `soundwave-backend` (Django + DRF)
> Repo liên quan: `soundwave-mobile` (Flutter) — độc lập, đồng bộ qua `contracts/openapi.yaml` + `.claude/api-context.md`
>
> Last updated: 2026-07-25 (Constitution v1.0.0 đã chốt; scaffolding repo xong — chưa có spec nào triển khai)

## Snapshot

- **Vai trò repo này**: Backend cho app nghe nhạc SoundWave (placeholder name) — **proxy + cache Jamendo API** (Creative Commons, non-commercial), quản lý tài khoản người dùng thật (email/social login), playlist, liked tracks, lịch sử nghe.
- **Stack**: Django + DRF, PostgreSQL, Redis (cache response Jamendo + rate-limit quota), JWT (`djangorestframework-simplejwt`) cho user auth.
- **KHÔNG có S3/CDN cho audio** — file nhạc luôn stream thẳng từ Jamendo, backend không lưu trữ/transcode. Khác biệt lớn nhất so với kiến trúc LiveCanvas.
- **KHÔNG có admin upload pipeline** ở v1 — nội dung tự động từ Jamendo, không cần màn quản trị.
- **2 tầng auth**: `X-App-Key` (mọi request) + `Authorization: Bearer <user_access_token>` (endpoint `/me/*`, `/auth/logout`) — khác LiveCanvas ở chỗ đây là **user token thật**, không phải admin token.
- **Giới hạn pháp lý quan trọng**: Jamendo API chỉ miễn phí cho mục đích **phi thương mại**. Nếu sau này có ý định monetize (ads/premium), phải liên hệ Jamendo xin giấy phép thương mại trước — không tự ý thêm doanh thu vào app khi vẫn dùng free tier.
- **Communication**: Tiếng Việt giữa user + Claude · Tiếng Anh cho code/comment/commit.

## Current Focus

- **Trạng thái**: Repo đã có nền tảng tài liệu + constitution v1.0.0, chưa merge spec code nào.
- **Đã có sẵn**: `docs/screen-inventory.md`, `contracts/openapi.yaml` v0.1.0, `.claude/api-context.md` v0.1.0 (draft, chờ review cùng phía mobile), `.specify/memory/constitution.md` v1.0.0, `.claude/dev-workflow.md`, `.claude/changelog.md`, `.claude/decisions/`.
- **Spec tiếp theo**: freeze contract #000 → `BE-001-backend-foundation`.
- **Chưa quyết định**:
  - Đăng ký Jamendo API client_id thật (cần trước `BE-002`).
  - Google/Apple Sign-In credentials (OAuth client ID, Apple Service ID) — cần trước `BE-001` để cấu hình verify token.
  - Chiến lược cache Redis cụ thể (TTL cho từng loại endpoint catalog).

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
