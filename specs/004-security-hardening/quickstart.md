# Quickstart — Verify BE-004 Security Hardening

> Kịch bản kiểm chứng end-to-end BE-004 thực sự hoạt động. Không chứa code triển khai — chỉ cách chạy/quan sát. Chi tiết thiết kế xem [plan.md](plan.md) / [research.md](research.md).

## Prerequisites

```bash
source .venv/bin/activate
# PostgreSQL + Redis đang chạy:
brew services start postgresql@16     # DB role/db 'soundwave' đã tạo
brew services start redis             # cần cho throttle + cache (dev)
# .env: đặt REDIS_URL=redis://localhost:6379/0 để throttle dùng Redis thật
```

## 1. Bộ test tự động (cổng chính)

```bash
black --check . && ruff check . && mypy .
pytest                                     # kỳ vọng: 104 cũ + test BE-004 mới, tất cả pass
python manage.py makemigrations --check --dry-run   # kỳ vọng: no changes (không model mới)
```

Các test BE-004 phải phủ (map tới FR/SC):
- **Throttle auth** (FR-002, SC-001): vượt `THROTTLE_AUTH` lần login → `429 RATE_LIMITED` + `Retry-After`; dưới ngưỡng luôn qua.
- **Throttle history/write** (FR-001, FR-006): vượt ngưỡng `POST /me/history` → 429; user A chạm ngưỡng KHÔNG ảnh hưởng user B.
- **Throttle catalog** (FR-003): vượt `THROTTLE_CATALOG` từ một IP → 429.
- **Fail-open/closed** (FR-006a): giả lập cache lỗi → `/me/*`,`/catalog/*` cho qua (fail-open) + log cảnh báo; `/auth/*` bị chặn (fail-closed).
- **Token lifecycle** (FR-007/008/009, SC-002): refresh xoay vòng → token cũ = `TOKEN_INVALID`; logout token được trình → refresh sau = `TOKEN_INVALID`; access hết hạn → `TOKEN_EXPIRED`; logout thiếu/không hợp lệ token → `204` idempotent (FR-011), không 500.
- **Logout per-session** (FR-008): user login 2 "thiết bị" (2 refresh); logout thiết bị 1 → refresh thiết bị 2 vẫn hợp lệ.
- **Signing key fail-fast** (FR-010, SC-003): import settings production với `DJANGO_SECRET_KEY` ngắn (<32 bytes) → `ImproperlyConfigured`.
- **RATE_LIMITED envelope** (FR-004): 429 trả đúng `{error:{code:RATE_LIMITED}}` + header `Retry-After`.
- **Redaction/scrub** (FR-013, SC-004): log/sự kiện chứa password/token/id_token → bị che; `before_send` scrub Authorization header.
- **IDOR sweep** (FR-016, SC-006): user A thử mọi thao tác đọc/ghi lên playlist/liked/history của B → toàn bộ `FORBIDDEN`/`NOT_FOUND`.
- **Cache-hit chống stampede** (FR-017, SC-005): gọi 1 endpoint đọc catalog N lần với JamendoClient mock → số upstream call ≈ hằng số (không = N).

## 2. Kiểm chứng thủ công 429 + Retry-After (dev)

```bash
export DJANGO_SETTINGS_MODULE=config.settings.dev
python manage.py runserver &
# Bắn vượt ngưỡng login (THROTTLE_AUTH mặc định 10/min):
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " \
    -H "X-App-Key: dev-app-key" -H "Content-Type: application/json" \
    -d '{"email":"x@y.z","password":"wrong"}' \
    http://localhost:8000/auth/login
done; echo
# Kỳ vọng: vài 401 (INVALID_CREDENTIALS) rồi chuyển sang 429.
curl -si -H "X-App-Key: dev-app-key" -d '{"email":"x@y.z","password":"w"}' \
  http://localhost:8000/auth/login | grep -iE "HTTP/|Retry-After|RATE_LIMITED"
```

## 3. Fail-fast khóa ký (production)

```bash
DJANGO_SETTINGS_MODULE=config.settings.production \
DJANGO_SECRET_KEY="short" \
python -c "import django; django.setup()"   # Kỳ vọng: ImproperlyConfigured (key < 32 bytes)
```

## 4. Load test tải thật (tùy chọn, KHÔNG thuộc CI)

> Chỉ chạy ở dev/staging với cache đã nạp hoặc JamendoClient mock — **không đốt quota Jamendo thật** (Constitution XI/XIII). Bộ test deterministic ở mục 1 mới là cổng bắt buộc; đây là đo RPS tham khảo.

```bash
# ví dụ dùng hey/wrk sau khi warm cache /catalog/trending:
curl -s -H "X-App-Key: $X_APP_KEY" http://localhost:8000/catalog/trending >/dev/null  # warm
hey -n 2000 -c 50 -H "X-App-Key: $X_APP_KEY" http://localhost:8000/catalog/trending
# Quan sát: latency ổn định, và (qua log/metrics) số call Jamendo KHÔNG tăng theo số request.
```

## 5. Definition of Done (đối chiếu dev-workflow §5)

- [ ] Toàn bộ test mục 1 xanh; không giảm baseline 104.
- [ ] Contract cập nhật (`openapi.yaml` + `api-context.md` + `screen-inventory.md`, bump v0.3.0) TRƯỚC code.
- [ ] Không hardcode: rates/ngưỡng khóa/DSN/CORS đều qua env.
- [ ] `owasp-review.md` điền đầy đủ; mỗi phát hiện có khắc phục hoặc lý do chấp nhận.
- [ ] `changelog.md` cập nhật; ADR nếu cần (vd refinement định danh throttle catalog — R1).
- [ ] Dep mới pinned + verify PyPI (`sentry-sdk==2.66.1`, `django-cors-headers==4.9.0`).
