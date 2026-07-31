---
description: "Task list — BE-004 Security Hardening & Production Readiness"
---

# Tasks: Security Hardening & Production Readiness

**Input**: Design documents from `specs/004-security-hardening/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/rate-limit.md](contracts/rate-limit.md), [quickstart.md](quickstart.md)
**Tests**: INCLUDED — Constitution XI (testing discipline) + FR-016/FR-021/SC-007 yêu cầu test tường minh.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: chạy song song được (khác file, không phụ thuộc task chưa xong)
- **[Story]**: US1..US4 map tới user story trong spec.md
- Đường dẫn file tuyệt đối tính từ repo root.

**Ghi chú cross-cutting**: BE-004 **không thêm model DB** → không migration. Contract-first (Constitution II): task cập nhật contract nằm ở Foundational, TRƯỚC mọi code emit `RATE_LIMITED`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Thêm và cài dependency mới (đã verify PyPI 2026-07-25).

- [X] T001 Thêm `django-cors-headers==4.9.0` + `sentry-sdk==2.66.1` vào `requirements/base.txt` (sentry chuyển từ production.txt → base để test observability import được ở dev; bump 2.20.0→2.66.1)
- [X] T002 Cài dep vào `.venv` và xác nhận `python -c "import corsheaders, sentry_sdk"` chạy được (corsheaders 4.9.0, sentry 2.66.1)

**Checkpoint**: Dependency sẵn sàng.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contract-first + mã lỗi dùng chung — BLOCKS mọi code phát sinh `RATE_LIMITED`.

**⚠️ CRITICAL**: Hoàn tất phase này trước khi bắt đầu US1.

- [X] T003 Contract-first update: `RATE_LIMITED` 429 + `Retry-After` vào `docs/screen-inventory.md` (ghi chú cross-cutting) → `contracts/openapi.yaml` (bump v0.3.0, response `RateLimited` + 429 ở 3 path auth) → `.claude/api-context.md` (Error Code Catalog + mục Rate limiting). YAML validated.
- [X] T004 Thêm `ErrorCode.RATE_LIMITED` + `ERROR_MAP` (429) trong `core/errors.py`

**Checkpoint**: Contract v0.3.0 + mã lỗi sẵn sàng — user story có thể bắt đầu.

---

## Phase 3: User Story 1 — Rate Limiting (Priority: P1) 🎯 MVP

**Goal**: Throttle endpoint dễ lạm dụng (auth per-IP, catalog per-IP, `/me/*` ghi per-user, history per-user); vượt hạn mức → `429 RATE_LIMITED` + `Retry-After`; fail-open chức năng / fail-closed auth khi Redis lỗi.

**Independent Test**: Bắn vượt ngưỡng từng nhóm endpoint → 429 sau ngưỡng; dưới ngưỡng luôn qua; user A chạm ngưỡng không ảnh hưởng user B.

### Tests for User Story 1 (viết trước, phải FAIL trước khi impl)

- [X] T005 [P] [US1] Test envelope 429 trong `core/tests/test_rate_limit_envelope.py`: `Throttled` → `{error:{code:RATE_LIMITED}}` + header `Retry-After`
- [X] T006 [P] [US1] Test throttle auth trong `apps/accounts/tests/test_throttle_auth.py`: vượt `THROTTLE_AUTH` login từ 1 IP → 429; fail-closed khi cache lỗi
- [X] T007 [P] [US1] Test throttle `/me/*` trong `apps/library/tests/test_throttle_me.py`: vượt `THROTTLE_HISTORY`/`THROTTLE_USER` → 429; user A vs user B isolation (FR-006); fail-open khi cache lỗi
- [X] T008 [P] [US1] Test throttle catalog trong `apps/catalog/tests/test_throttle_catalog.py`: vượt `THROTTLE_CATALOG` per-IP → 429; fail-open khi cache lỗi

### Implementation for User Story 1

- [X] T009 [US1] Thêm settings throttle trong `config/settings/base.py`: `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` (scopes `auth`/`user_write`/`history`/`catalog` từ env `THROTTLE_AUTH|USER|HISTORY|CATALOG`), `NUM_PROXIES` (env, default 0). KHÔNG đặt `DEFAULT_THROTTLE_CLASSES` toàn cục (áp per-view)
- [X] T010 [US1] Tạo `core/throttling.py`: base `_ResilientThrottle(SimpleRateThrottle)` (bắt lỗi cache → `fail_open` cho qua + log.warning / hoặc chặn) + `AuthRateThrottle`(scope auth, key IP, fail_open=False), `CatalogRateThrottle`(scope catalog, key IP, fail_open=True), `UserWriteRateThrottle`(scope user_write, key user.pk, fail_open=True), `HistoryRateThrottle`(scope history, key user.pk, fail_open=True)
- [X] T011 [US1] Trong `core/exceptions.py` thêm nhánh (trước bước gọi drf_exception_handler): `isinstance(exc, drf_exc.Throttled)` → `_envelope(RATE_LIMITED, msg, 429)` và set header `Retry-After` từ `exc.wait`
- [X] T012 [P] [US1] Áp `throttle_classes = [AuthRateThrottle]` cho `LoginView`/`RegisterView`/`SocialLoginView` trong `apps/accounts/views.py`
- [X] T013 [P] [US1] Áp `throttle_classes = [CatalogRateThrottle]` cho các view trong `apps/catalog/views.py`
- [X] T014 [P] [US1] Áp throttle cho `apps/library/views.py`: `HistoryRateThrottle` cho log history; `UserWriteRateThrottle` cho các thao tác ghi playlist/liked (per-view/action)
- [X] T015 [US1] Cập nhật `.env.example`: thêm `THROTTLE_AUTH`, `THROTTLE_CATALOG`, `NUM_PROXIES` (giữ `THROTTLE_USER`/`THROTTLE_HISTORY` đã có), kèm comment giá trị mặc định

**Checkpoint**: US1 hoạt động độc lập — throttle + 429 envelope đầy đủ. MVP sẵn sàng.

---

## Phase 4: User Story 2 — Token Lifecycle Hardening (Priority: P2)

**Goal**: Rotation + revoke on logout đúng ngữ nghĩa per-session; fail-fast khóa ký JWT <32 bytes ở production.

**Independent Test**: refresh xoay vòng → token cũ `TOKEN_INVALID`; logout token được trình → refresh sau `TOKEN_INVALID`; logout thiết bị 1 → thiết bị 2 vẫn hợp lệ; access hết hạn → `TOKEN_EXPIRED`; settings production khóa ngắn → `ImproperlyConfigured`.

### Tests for User Story 2 (viết trước, phải FAIL trước khi impl)

- [X] T016 [P] [US2] Test vòng đời token trong `apps/accounts/tests/test_token_lifecycle.py`: rotation reuse → `TOKEN_INVALID`; logout(presented) → refresh sau `TOKEN_INVALID`; logout per-session (2 refresh, thu hồi 1, còn 1 hợp lệ); logout thiếu/không hợp lệ token → `204` idempotent, không 500 (FR-011); access hết hạn → `TOKEN_EXPIRED`
- [X] T017 [P] [US2] Test fail-fast khóa ký trong `apps/accounts/tests/test_signing_key_check.py`: import `config.settings.production` với `DJANGO_SECRET_KEY` <32 bytes → `ImproperlyConfigured`; ≥32 bytes → OK

### Implementation for User Story 2

- [X] T018 [US2] Sửa `LogoutView` trong `apps/accounts/views.py`: chỉ revoke refresh token được trình; thiếu token → `204` no-op; nuốt `TokenError` (token đã thu hồi/hết hạn) → `204` idempotent. BỎ nhánh `revoke_all(request.user)` khỏi logout thường (giữ `tokens.revoke_all` cho dùng nội bộ khác)
- [X] T019 [US2] Thêm `JWT_MIN_SECRET_BYTES` (env, default 32) trong `config/settings/base.py`; thêm guard fail-fast trong `config/settings/production.py`: `len(SECRET_KEY.encode()) < JWT_MIN_SECRET_BYTES` → `raise ImproperlyConfigured(...)`
- [X] T020 [P] [US2] Tạo `core/checks.py`: Django system check (tag deploy) cảnh báo/lỗi khi `not DEBUG` và khóa ký < ngưỡng; đăng ký check trong một AppConfig phù hợp (vd `apps/accounts/apps.py` `ready()`)
- [X] T021 [P] [US2] Cập nhật `.env.example`: thêm `JWT_MIN_SECRET_BYTES` (comment: ≥32 cho HS256)

**Checkpoint**: US2 độc lập — token revoke chặt + fail-fast khóa yếu.

---

## Phase 5: User Story 3 — Observability (Priority: P3)

**Goal**: Sentry env-driven + scrub secret/PII (kép với redaction log); dev/test inert.

**Independent Test**: kích lỗi ở settings có DSN (mock) → event đã scrub Authorization/token/password; không DSN → không init.

### Tests for User Story 3 (viết trước, phải FAIL trước khi impl)

- [X] T022 [P] [US3] Test scrub trong `core/tests/test_observability.py`: `_scrub(event)` xóa Authorization header/password/token/id_token/client_id khỏi `request`+`extra`; xác nhận `init_sentry` không gọi khi DSN rỗng (mock `sentry_sdk.init`)

### Implementation for User Story 3

- [X] T023 [US3] Tạo `core/observability.py`: `init_sentry(dsn)` gọi `sentry_sdk.init(dsn, integrations=[DjangoIntegration()], send_default_pii=False, before_send=_scrub)`; `_scrub(event, hint)` che key nhạy cảm (tái dùng danh sách từ pattern `core/logging.py`)
- [X] T024 [US3] Sửa `config/settings/production.py`: thay `sentry_sdk.init(...)` trực tiếp bằng `from core.observability import init_sentry; init_sentry(SENTRY_DSN)` khi có DSN (staging kế thừa)
- [X] T034 [US3] Đảm bảo FR-014 — verify/bổ sung log ngữ cảnh sự cố upstream trong `apps/catalog/services/jamendo.py` (+ `catalog.py`): khi Jamendo timeout/5xx/429 → `logger.warning/error` kèm endpoint upstream, status, latency, KHÔNG dump toàn bộ response; thêm test khẳng định trong `apps/catalog/tests/test_cache_load.py` hoặc test client riêng *(task sinh sau /speckit-analyze — vá coverage gap FR-014)*

**Checkpoint**: US3 độc lập — Sentry an toàn, không lộ secret; sự cố upstream có ngữ cảnh chẩn đoán.

---

## Phase 6: User Story 4 — Audit & Load Validation (Priority: P4)

**Goal**: CORS thực thi, IDOR sweep toàn `/me/*`, cache-hit chống stampede, tài liệu OWASP.

**Independent Test**: cross-user toàn `/me/*` → 100% từ chối; gọi catalog N lần cache-hit → upstream call ≈ hằng số; header bảo mật production đúng.

### Tests for User Story 4 (viết trước, phải FAIL trước khi impl)

- [X] T025 [P] [US4] Test IDOR sweep trong `apps/library/tests/test_idor_sweep.py`: user A thử đọc/ghi mọi tài nguyên của B (playlist, playlist track, liked, history) → toàn bộ `FORBIDDEN`/`NOT_FOUND` (FR-016, SC-006)
- [X] T026 [P] [US4] Test cache-hit trong `apps/catalog/tests/test_cache_load.py`: gọi 1 endpoint đọc N lần với JamendoClient mock đếm call → upstream call ≈ hằng số nhỏ, không = N (FR-017, SC-005)

### Implementation for User Story 4

- [X] T027 [US4] Bật CORS: thêm `corsheaders` vào `INSTALLED_APPS` và `corsheaders.middleware.CorsMiddleware` (đúng vị trí, trước CommonMiddleware) trong `config/settings/base.py`; xác nhận `production.py` `CORS_ALLOWED_ORIGINS` được thực thi (không `*`)
- [X] T028 [P] [US4] Soạn `specs/004-security-hardening/owasp-review.md`: checklist OWASP tập trung IDOR `/me/playlists/{id}` + nested, input validation, transport/header, token; mỗi mục ghi trạng thái + khắc phục/lý do chấp nhận (FR-019)
- [X] T029 [P] [US4] Verify transport headers (HTTPS/HSTS/secure cookie) trong `config/settings/production.py` khớp Constitution VIII; bổ sung nếu thiếu

**Checkpoint**: US4 độc lập — audit + load validated.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Đồng bộ tài liệu, ADR, verify tổng.

- [X] T030 [P] Cập nhật `.claude/changelog.md`: mục BE-004 (rate limit, token hardening, Sentry, CORS, IDOR/load) + contract `v0.2.0→v0.3.0`
- [X] T031 [P] Cập nhật `.claude/project-context.md` + `.claude/sdd-roadmap.md`: BE-004 status → triển khai xong (chờ review)
- [X] T032 [P] Tạo ADR trong `.claude/decisions/` cho refinement định danh throttle catalog (X-App-Key dùng chung → per-IP; research R1) + hành vi fail-open/closed
- [X] T033 Chạy pre-commit checklist đầy đủ (`black --check .` · `ruff check .` · `mypy .` · `pytest` · `makemigrations --check --dry-run`) và kịch bản verify trong `quickstart.md`; kỳ vọng ≥104 baseline + test mới đều pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**: không phụ thuộc — bắt đầu ngay.
- **Foundational (P2)**: sau Setup — BLOCKS mọi user story (contract + mã lỗi).
- **US1 (P3)**: sau Foundational. **MVP**.
- **US2 (P4)**, **US3 (P5)**, **US4 (P6)**: sau Foundational; **độc lập với US1** và với nhau — có thể làm song song. (US4 test IDOR/cache không phụ thuộc US1..US3.)
- **Polish (P7)**: sau các story mong muốn.

### Chi tiết phụ thuộc trong story

- T003 (contract) trước T004 và trước mọi code emit RATE_LIMITED.
- T009 (settings rates) trước T010 (throttle classes) trước T012-T014 (áp view).
- T011 (exception mapping) phụ thuộc T004 (mã lỗi).
- Tests (T005-T008, T016-T017, T022, T025-T026) viết trước impl của story tương ứng, phải FAIL trước.

### Parallel Opportunities

- **Setup**: T001 rồi T002 (tuần tự — install sau khi sửa file).
- **US1 tests**: T005, T006, T007, T008 song song (khác file).
- **US1 áp view**: T012, T013, T014 song song sau khi T010/T011 xong.
- **Cross-story**: sau Foundational, US1/US2/US3/US4 có thể chạy song song bởi nhiều người.
- **Polish**: T030, T031, T032 song song.

---

## Parallel Example: User Story 1

```bash
# Viết trước toàn bộ test US1 (song song):
Task: "test_rate_limit_envelope.py — RATE_LIMITED + Retry-After"
Task: "test_throttle_auth.py — auth per-IP + fail-closed"
Task: "test_throttle_me.py — history/write per-user + isolation + fail-open"
Task: "test_throttle_catalog.py — catalog per-IP + fail-open"

# Sau khi throttle classes + exception mapping xong, áp view (song song):
Task: "Áp AuthRateThrottle cho apps/accounts/views.py"
Task: "Áp CatalogRateThrottle cho apps/catalog/views.py"
Task: "Áp History/UserWrite throttle cho apps/library/views.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (contract-first!) → 3. Phase 3 US1 → **STOP & VALIDATE** throttle + 429 → demo.

### Incremental Delivery

Setup+Foundational → US1 (MVP: rate limiting) → US2 (token hardening) → US3 (Sentry) → US4 (audit+load) → Polish. Mỗi story test độc lập, không phá story trước.

---

## Notes

- Không migration (không model mới) — `makemigrations --check` phải "no changes".
- Contract-first bắt buộc: T003 trước mọi code (Constitution II).
- Test phải FAIL trước khi impl (Constitution XI); không giảm baseline 104 (SC-007).
- Commit theo nhóm task logic; không hardcode tunable (Constitution VI).
