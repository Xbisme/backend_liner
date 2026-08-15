# Research — BE-004 Security Hardening

> Phase 0. Giải quyết mọi ẩn số kỹ thuật trước khi thiết kế. Mỗi mục: Decision / Rationale / Alternatives.

## R1. Định danh throttle cho `/catalog/*` — X-App-Key là secret DÙNG CHUNG

**Bối cảnh phát hiện khi khảo sát code**: `X-App-Key` là **một secret toàn cục dùng chung cho toàn bộ app build** (mọi cài đặt mobile gửi cùng một key — xem `AppKeyMiddleware` so khớp một `settings.X_APP_KEY` duy nhất). Do đó throttle keyed thuần theo `X-App-Key` = **một bucket toàn cục cho tất cả người dùng** → hoặc phải đặt hạn mức cực cao (vô dụng) hoặc sẽ chặn nhầm toàn bộ userbase.

**Decision**: `/catalog/*` throttle **keyed theo IP client (per-device)** làm định danh hiệu dụng. Đây chính là nhánh "IP fallback" trong quyết định clarify, được nâng thành *primary* vì `X-App-Key` không phân biệt được caller. `X-App-Key` vẫn là cổng Layer-1 (đã có middleware). Cache đã chặn phần lớn tải tới Jamendo (BE-002), nên rủi ro còn lại là một thiết bị bắn nhiều query cache-miss (search lạ) → per-IP xử lý đúng đối tượng này.

**Rationale**: Per-IP nhắm đúng nguồn lạm dụng (một thiết bị/kẻ tấn công), không chặn nhầm cả app. Giữ đơn giản một throttle (Constitution XII) thay vì thêm bucket toàn cục phức tạp.

**Alternatives considered**:
- *Per-X-App-Key global bucket*: là một circuit-breaker toàn cục hợp lệ, nhưng một IP lạm dụng có thể đốt cạn bucket chung → DoS mọi người; và cache đã lo phần quota. Bỏ (YAGNI). Có thể thêm sau nếu quota Jamendo thực sự bị đe dọa ở tầng tổng.
- *Per-user*: catalog là endpoint ẩn danh (không cần user token) → không có user để key.

> ⚠️ Đây là **refinement của quyết định clarify** dựa trên sự thật kỹ thuật mới (X-App-Key dùng chung). Cần user xác nhận; nếu user muốn thêm circuit-breaker toàn cục theo X-App-Key, bổ sung dễ dàng như throttle thứ hai.

## R2. Định danh throttle cho các nhóm còn lại

**Decision**:
- `/auth/login|register|social-login` → **per-IP** (`AuthRateThrottle`), **fail-closed** khi Redis lỗi.
- `/me/*` ghi (POST/PUT/PATCH/DELETE playlist, add/remove/reorder, like/unlike) → **per-user** (`UserWriteRateThrottle`), fail-open.
- `POST /me/history` → **per-user, scope riêng, hạn mức cao hơn** (`HistoryRateThrottle`) vì tua/skip nhanh sinh nhiều lượt ghi hợp lệ.
- Endpoint **đọc** `/me/*` (GET list playlist/liked/history) và catalog GET: chỉ áp throttle catalog per-IP; không throttle chặt các GET `/me/*` (đọc của chính chủ, ít rủi ro) — giữ đơn giản.

**Rationale**: Khớp FR-002/003/006; nhắm throttle vào endpoint ghi/ẩn danh (bề mặt lạm dụng thật), tránh false-positive ở đường đọc.

## R3. Fail-open (chức năng) / fail-closed (auth) khi Redis sự cố

**Decision**: Viết một base class `_ResilientThrottle(SimpleRateThrottle)` bọc `allow_request`:
- Bắt lỗi kết nối cache (Redis `ConnectionError`/`TimeoutError`, hoặc bất kỳ exception nào từ `cache`): 
  - throttle có cờ `fail_open = True` (Catalog/UserWrite/History) → trả `True` (cho qua) + `logger.warning("throttle store unavailable, failing open", ...)`.
  - throttle có cờ `fail_open = False` (Auth) → trả `False` (chặn) hoặc raise `Throttled` → 429 (không mở toang brute-force).

**Rationale**: FR-006a. Không để store lỗi biến thành DoS người dùng hợp lệ, nhưng không hy sinh phòng thủ brute-force auth.

**Alternatives**: Dùng `DjangoRateLimitMiddleware` bên thứ ba — thừa (Constitution XII); DRF built-in đủ dùng.

## R4. `RATE_LIMITED` (429) + header `Retry-After` qua exception handler

**Bối cảnh**: `core/exceptions.py` bước 3 gọi `drf_exception_handler` rồi **dựng lại** `_envelope(...)` — làm **mất header `Retry-After`** mà DRF gắn cho `Throttled`, và render code `THROTTLED` (từ `default_code`) thay vì `RATE_LIMITED`.

**Decision**:
1. Thêm `ErrorCode.RATE_LIMITED` + `ERROR_MAP[RATE_LIMITED] = (429, "Too many requests, retry later.")` trong `core/errors.py`.
2. Trong `api_exception_handler`, thêm nhánh **trước** bước 3: `if isinstance(exc, drf_exc.Throttled): resp = _envelope(RATE_LIMITED, msg, 429); if exc.wait: resp["Retry-After"] = str(int(exc.wait)); return resp`.

**Rationale**: Constitution V (một mã cho một điều kiện) + FR-004. Giữ envelope chuẩn, thêm `Retry-After` cho client biết thời điểm thử lại.

## R5. Fail-fast độ dài khóa ký JWT

**Bối cảnh**: SimpleJWT mặc định `SIGNING_KEY = SECRET_KEY`, thuật toán HS256 → khóa nên ≥ 32 bytes. Tín hiệu: khóa test 22 bytes.

**Decision**: Guard tường minh trong `config/settings/production.py` (staging kế thừa):
```python
if len(SECRET_KEY.encode()) < 32:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be >= 32 bytes for HS256 JWT signing.")
```
Bổ sung một Django system check trong `core/checks.py` (chỉ cảnh báo/lỗi khi `not DEBUG`) để `manage.py check --deploy` cũng bắt được.

**Rationale**: FR-010/SC-003 — fail-fast lúc khởi động, không chạy production với khóa yếu. Guard ở settings đảm bảo chặn thật khi import settings (gunicorn boot). Ngưỡng 32 là env-overridable (`JWT_MIN_SECRET_BYTES`, default 32) để không hardcode (Constitution VI).

**Alternatives**: Chỉ dùng system check — nhưng gunicorn không tự chạy `check` khi boot → không đảm bảo fail-fast. Dùng cả hai.

## R6. Load test cache-hit chống stampede — deterministic, không chạm Jamendo

**Decision**: Test chính (CI) trong `apps/catalog/tests/test_cache_load.py`:
- Mock `JamendoClient` đếm số lần gọi upstream.
- Gọi cùng một endpoint đọc (vd `/catalog/trending`) **N lần** (N lớn, vd 50) — có thể dùng `ThreadPoolExecutor` với Django test client hoặc tuần tự.
- Assert: sau request đầu (miss → 1 upstream call), các request sau phục vụ từ cache → **tổng upstream call ≈ hằng số nhỏ**, KHÔNG = N (SC-005/FR-017).
- Test riêng cho "no persist on error": upstream lỗi → không cache (đã có ở BE-002, tái khẳng định).

**Rationale**: Deterministic, không network (Constitution XI), chứng minh *hình dạng* cache-hit chặn tải upstream. Không cam kết RPS tuyệt đối (phụ thuộc phần cứng).

**Alternatives**: Locust/k6 chạy tải thật — hữu ích cho số RPS nhưng non-deterministic, không hợp CI. **Cung cấp một script Locust tùy chọn** mô tả trong `quickstart.md` cho đo tải thật ở dev/staging (không thuộc bộ test bắt buộc). Ghi rõ giới hạn: không chạy CI, phải mock/nạp cache để không đốt quota Jamendo thật.

**Ghi chú stampede-on-miss**: `get_or_fetch` hiện không khóa; nhiều miss đồng thời cho cùng key có thể gọi upstream song song (thundering herd on cold cache). FR-017 chỉ yêu cầu cache-**hit** phục vụ tải — đã thỏa. Cache-lock cho miss là cải tiến tùy chọn, **ngoài phạm vi BE-004** trừ khi load test cho thấy vấn đề (YAGNI).

## R7. Sentry wiring + scrubbing

**Decision**: `core/observability.py` cung cấp `init_sentry(dsn)`:
- `sentry_sdk.init(dsn=dsn, integrations=[DjangoIntegration()], send_default_pii=False, before_send=_scrub)`.
- `_scrub(event, hint)`: xóa/che các key nhạy cảm (Authorization header, password, token, id_token, client_id) trong `event["request"]` và `extra` — belt-and-suspenders cùng `SensitiveDataFilter` cho log.
- Gọi từ `production.py` khi có `SENTRY_DSN`. Dev/test không DSN → không init.

**Rationale**: FR-012/013/015, Constitution IX. `send_default_pii=False` + `before_send` scrub kép đảm bảo 0 secret rời hệ thống (SC-004).

## Rates mặc định (settings-driven — defer từ spec Assumptions)

Đặt trong `base.py` `DEFAULT_THROTTLE_RATES`, mọi giá trị env-overridable. Mặc định thận trọng, trên mức dùng thật:

| Scope | Env var | Default | Lý do |
|---|---|---|---|
| `auth` (per-IP) | `THROTTLE_AUTH` | `10/min` | Chống brute-force; người thật đăng nhập vài lần |
| `user_write` (per-user) | `THROTTLE_USER` | `60/min` | Thao tác playlist/like — thoải mái cho dùng thật |
| `history` (per-user) | `THROTTLE_HISTORY` | `120/min` | Tua/skip nhanh sinh nhiều lượt ghi |
| `catalog` (per-IP) | `THROTTLE_CATALOG` | `120/min` | Duyệt/tìm nhạc; phần lớn hit cache |

> `THROTTLE_ANON`/`THROTTLE_USER` đã có trong `.env.example` từ trước; thêm `THROTTLE_AUTH`, `THROTTLE_CATALOG`, `THROTTLE_HISTORY` (history đã có). Con số chỉ là mặc định — điều chỉnh là sửa env (FR-005).

## Dependencies (PyPI, tra 2026-07-25 — Constitution XIV)

| Package | Version | Nơi pin | Ghi chú |
|---|---|---|---|
| `sentry-sdk` | `2.66.1` | `production.txt` | Chỉ prod/staging cần; DjangoIntegration |
| `django-cors-headers` | `4.9.0` | `base.txt` | Kích hoạt `CORS_ALLOWED_ORIGINS` đã có |

**CORS tradeoff**: client là Flutter native (không bị CORS như browser). Tuy nhiên Constitution VIII yêu cầu "CORS allowlist, không `*`", và `CORS_ALLOWED_ORIGINS` đã tồn tại trong `production.py` (hiện vô hiệu vì thiếu package). Thêm `django-cors-headers` để setting thành thật + phòng thủ cho bất kỳ web client tương lai. Chi phí thấp, giữ nhất quán constitution.
