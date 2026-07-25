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

## Bắt đầu

```bash
cp .env.example .env          # điền secrets thật
# (BE-001 sẽ thêm) python -m venv .venv && pip install -r requirements/dev.txt
# (BE-001 sẽ thêm) python manage.py migrate && python manage.py runserver
```

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
