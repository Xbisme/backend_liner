# SoundWave Backend

Backend (Django + DRF) cho app nghe nhạc **SoundWave**. Repo này đóng vai trò
**proxy + cache trước Jamendo API** (Creative Commons, phi thương mại) và quản
lý tài khoản người dùng thật (email/social login), playlist, bài hát yêu thích,
lịch sử nghe. Backend **không** lưu trữ/transcode audio — nhạc stream thẳng từ
URL của Jamendo.

Repo liên quan: `soundwave-mobile` (Flutter) — độc lập, đồng bộ qua
[`contracts/openapi.yaml`](contracts/openapi.yaml) và
[`.claude/api-context.md`](.claude/api-context.md).

## Stack

- Python 3.12+ · Django + Django REST Framework
- PostgreSQL · Redis (cache catalog + rate-limit)
- JWT (`djangorestframework-simplejwt`) — access + rotating refresh
- Google (`google-auth`) / Apple (`python-jose`) social login
- black · ruff · mypy · pytest

## Auth 2 tầng

| Header | Dùng cho |
|---|---|
| `X-App-Key` | Mọi endpoint |
| `Authorization: Bearer <access_token>` | Toàn bộ `/me/*` + `/auth/logout` |

## Cấu trúc repo (mục tiêu)

```
config/            # settings/{base,dev,staging,production}, urls, middleware
core/              # base classes, pagination, exception handler, error codes
apps/
  accounts/        # User, auth (email + social), JWT, X-App-Key middleware
  catalog/         # JamendoClient, cache layer, /catalog/*
  library/         # Playlist, LikedTrack, ListeningHistory, /me/*
contracts/openapi.yaml   # contract máy-đọc (source of truth)
docs/              # PRD.md, screen-inventory.md
specs/             # BE-NNN-*/ feature specs (Spec Kit)
requirements/      # base.txt, dev.txt, production.txt
.claude/           # project-context, sdd-roadmap, api-context, dev-workflow, ...
```

## Bắt đầu (dev)

**Yêu cầu**: Python 3.12+, PostgreSQL, Redis.

```bash
# 1. Dịch vụ nền (macOS/brew — hoặc dùng Docker tùy ý)
brew services start postgresql@16
brew services start redis

# 2. Tạo DB role + database (khớp DATABASE_URL trong .env.example)
psql -h localhost -d postgres -c "CREATE ROLE soundwave WITH LOGIN PASSWORD 'soundwave' CREATEDB;"
psql -h localhost -d postgres -c "CREATE DATABASE soundwave OWNER soundwave;"

# 3. Cấu hình môi trường
cp .env.example .env          # điền JAMENDO_CLIENT_ID thật; các key khác có default hợp lý

# 4. Virtualenv + deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt

# 5. Migrate + chạy
python manage.py migrate
python manage.py runserver
```

> **Dev**: `DJANGO_SECRET_KEY` mặc định ngắn vẫn chạy được vì `DEBUG=True`. Social
> login (Google/Apple) chỉ verify token thật khi điền credentials thật; token sai
> trả `400 SOCIAL_TOKEN_INVALID`. Sentry tắt khi `SENTRY_DSN` trống.
>
> **Production**: `DJANGO_SECRET_KEY` **bắt buộc ≥ 32 bytes** (không boot nếu ngắn),
> đặt `NUM_PROXIES` theo reverse proxy, `CORS_ALLOWED_ORIGINS` allowlist, `SENTRY_DSN`,
> Google/Apple credentials thật. Xem `specs/004-security-hardening/quickstart.md`.

## Quy trình phát triển

- Nguyên tắc bất di bất dịch: [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
- Quy trình Spec Kit + Contract Sync: [`.claude/dev-workflow.md`](.claude/dev-workflow.md)
- Lộ trình spec: [`.claude/sdd-roadmap.md`](.claude/sdd-roadmap.md)

Pre-commit (bắt buộc):

```bash
black . && ruff check . && mypy . && pytest
python manage.py makemigrations --check --dry-run
```

## Ràng buộc pháp lý

Jamendo API chỉ miễn phí cho mục đích **phi thương mại**. Không thêm quảng cáo/
premium/IAP vào các luồng dùng Jamendo khi chưa có giấy phép thương mại
(Constitution: Principle XIII).
