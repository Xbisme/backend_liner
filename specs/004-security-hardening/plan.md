# Implementation Plan: Security Hardening & Production Readiness

**Branch**: `BE-004-security-hardening` | **Date**: 2026-07-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-security-hardening/spec.md`

## Summary

BE-004 làm cứng bảo mật và sẵn sàng vận hành cho SoundWave Backend — **không thêm domain app mới**. Toàn bộ thay đổi là cross-cutting, tập trung ở `core/` + `config/settings/` + một sửa nhỏ ở `apps/accounts/views.py`, cộng test và cập nhật contract. Bốn khối:

1. **Rate limiting** (US1): thêm `core/throttling.py` với các throttle class DRF theo phạm vi (auth→IP, catalog→IP, `/me/*`→user, history→user), rates settings-driven, hành vi fail-open (chức năng) / fail-closed (auth) khi Redis lỗi; map `Throttled` → `RATE_LIMITED` (429) + header `Retry-After`.
2. **Token lifecycle** (US2): rotation + blacklist đã bật từ BE-001 (verify E2E); **sửa 2 lỗ**: (a) logout hiện vô tình `revoke_all` khi thiếu body → đổi thành idempotent per-session; (b) thêm fail-fast độ dài khóa ký JWT (≥32 bytes) ở production/staging.
3. **Observability** (US3): thêm dep `sentry-sdk`, wiring `DjangoIntegration` + `before_send` scrubber (bổ sung cho `SensitiveDataFilter` sẵn có); DSN env-driven, tắt ở dev/test; giữ redaction.
4. **Audit & load** (US4): kiện toàn CORS (`django-cors-headers` để setting `CORS_ALLOWED_ORIGINS` hiện có thực sự hoạt động), IDOR sweep phủ toàn `/me/*`, test cache-hit chống stampede (deterministic, không chạm Jamendo), tài liệu `owasp-review.md`.

Contract change duy nhất: thêm mã lỗi `RATE_LIMITED` (429) + header `Retry-After` → bump `v0.2.0 → v0.3.0`, đồng bộ mobile khi freeze #000.

## Technical Context

**Language/Version**: Python 3.12 · Django 5.2.16 · DRF 3.17.1

**Primary Dependencies (mới)**: `sentry-sdk==2.66.1` (PyPI 2026-07-25), `django-cors-headers==4.9.0` (PyPI 2026-07-25). Throttling dùng DRF built-in (không dep mới). Redis/`django-redis` đã có (BE-002).

**Storage**: PostgreSQL (đã có); Redis làm store đếm throttle (dùng lại cache `default`); SimpleJWT `token_blacklist` (đã cài, migration đã có).

**Testing**: pytest + pytest-django + DRF APIClient; Jamendo mock qua `httpx.MockTransport` (đã có); Sentry tắt trong test (không DSN); throttle test override `DEFAULT_THROTTLE_RATES` + fake cache lỗi.

**Target Platform**: Linux server (gunicorn/uvicorn sau reverse proxy).

**Project Type**: web-service (backend đơn, không frontend trong repo này).

**Performance Goals**: rate-limit không tạo false-positive ở nhịp dùng thực; cache-hit phục vụ phần lớn tải đọc catalog (số call Jamendo ~hằng số theo số request, không tuyến tính) — SC-005 đo *hình dạng*, không cam kết RPS tuyệt đối.

**Constraints**: không hardcode tunable (Constitution VI) — mọi ngưỡng/khung/độ dài khóa qua settings/env; contract-first cho mã lỗi 429; không gọi Jamendo/Sentry thật trong test (Constitution XI); YAGNI — không thêm app/abstraction thừa (Constitution XII).

**Scale/Scope**: ~8 file code chạm + ~8 file test mới + 3 file contract/doc + 1 doc OWASP. Không migration mới (không đổi model).

## Constitution Check

*GATE: Must pass before Phase 0. Re-checked after Phase 1.*

| Principle | Ảnh hưởng | Tuân thủ |
|---|---|---|
| I. Two-Tier Auth & IDOR | Token lifecycle + IDOR sweep là trọng tâm | ✅ verify + siết chặt; logout per-session đúng ngữ nghĩa |
| II. Contract-First | Thêm mã `RATE_LIMITED` 429 | ✅ cập nhật `screen-inventory → openapi.yaml + api-context.md` TRƯỚC code; bump v0.3.0; sync mobile |
| V. Consistent Error Handling | Mã lỗi mới | ✅ thêm vào `ErrorCode` + `ERROR_MAP`, render qua handler duy nhất |
| VI. Config & Secrets Hygiene | Rates, ngưỡng khóa, DSN, CORS | ✅ tất cả env-driven; không hardcode |
| VIII. Security Hardening | Là mục tiêu chính | ✅ rate limit + token revoke + OWASP/IDOR + transport headers |
| IX. Observability | Sentry + redaction | ✅ DSN env-driven, PII scrub, không log secret |
| XI. Testing Discipline | Jamendo/Sentry mock | ✅ deterministic, không network |
| XII. Simplicity/YAGNI | Không app mới | ✅ cross-cutting ở `core/`; throttle dùng DRF built-in |
| XIV. Dependency Hygiene | 2 dep mới | ✅ version tra PyPI 2026-07-25, pinned |

**Kết quả**: PASS — không có vi phạm cần justify. `Complexity Tracking` để trống.

### Phát hiện khi khảo sát code (đưa vào research)

- Throttling **chưa** wire vào `REST_FRAMEWORK` dù env `THROTTLE_ANON/USER/HISTORY` đã tồn tại.
- Exception handler bước 3 hiện render `Throttled` thành code `THROTTLED` (không phải `RATE_LIMITED`) và **mất header `Retry-After`** khi dựng lại envelope → cần xử lý riêng.
- `LogoutView` gọi `revoke_all(request.user)` khi body thiếu `refresh_token` → vô tình "logout mọi thiết bị", **mâu thuẫn** quyết định clarify (per-session) → cần sửa.
- `production.py` đã init `sentry_sdk` nhưng **`sentry-sdk` không có trong requirements** (ImportError khi có DSN) → thêm dep + wiring đầy đủ.
- `CORS_ALLOWED_ORIGINS` được đặt ở production nhưng **`django-cors-headers` chưa cài** → setting hiện vô hiệu.
- SimpleJWT `SIGNING_KEY` mặc định = `SECRET_KEY` (HS256); cần fail-fast khi `SECRET_KEY` < 32 bytes ở production.

## Project Structure

### Documentation (this feature)

```text
specs/004-security-hardening/
├── plan.md              # This file
├── research.md          # Phase 0 — 6 quyết định thiết kế + rates mặc định
├── data-model.md        # Phase 1 — throttle scope map, không model DB mới
├── contracts/
│   └── rate-limit.md    # Phase 1 — delta contract: RATE_LIMITED 429 + Retry-After
├── quickstart.md        # Phase 1 — kịch bản verify E2E (throttle/token/redaction/load)
├── owasp-review.md      # US4 deliverable (điền khi implement)
└── tasks.md             # /speckit-tasks (chưa tạo ở bước này)
```

### Source Code (repository root)

```text
core/
├── throttling.py        # MỚI — throttle classes (Auth/Catalog/UserWrite/History) + fail-open/closed base
├── checks.py            # MỚI — Django system check: JWT signing key length
├── errors.py            # SỬA — thêm ErrorCode.RATE_LIMITED + ERROR_MAP (429)
├── exceptions.py        # SỬA — map drf_exc.Throttled → RATE_LIMITED + set Retry-After
├── observability.py     # MỚI — sentry before_send scrubber (dùng lại pattern SensitiveDataFilter)
├── middleware.py        # (không đổi; IP handling qua DRF NUM_PROXIES)
└── logging.py           # (không đổi — redaction đã có)

config/settings/
├── base.py              # SỬA — DEFAULT_THROTTLE_RATES, NUM_PROXIES, corsheaders app+middleware, THROTTLE_* mới
├── production.py        # SỬA — fail-fast signing-key length; sentry init đầy đủ (integration+before_send); CORS đã thực thi
└── staging.py           # (kế thừa production — Sentry cũng bật ở staging: đúng Constitution IX)

apps/accounts/
└── views.py             # SỬA — LogoutView: idempotent per-session (bỏ revoke_all fallback); áp AuthRateThrottle

apps/{accounts,catalog,library}/  # áp throttle_classes cho view tương ứng (auth/catalog/me)

requirements/
├── base.txt             # SỬA — + django-cors-headers==4.9.0
└── production.txt       # SỬA — + sentry-sdk==2.66.1 (chỉ prod/staging cần)

tests (theo app):
├── apps/accounts/tests/test_throttle_auth.py      # MỚI
├── apps/accounts/tests/test_token_lifecycle.py    # MỚI (rotation reuse, logout revoke, expiry)
├── apps/accounts/tests/test_signing_key_check.py  # MỚI (fail-fast key ngắn)
├── apps/library/tests/test_throttle_me.py         # MỚI (history + write throttle, per-user isolation)
├── apps/library/tests/test_idor_sweep.py          # MỚI (cross-user toàn /me/*)
├── apps/catalog/tests/test_throttle_catalog.py    # MỚI
├── apps/catalog/tests/test_cache_load.py          # MỚI (cache-hit chống stampede, call-count flat)
└── core/tests/test_rate_limit_envelope.py         # MỚI (RATE_LIMITED + Retry-After) + sentry scrub

contracts/openapi.yaml + .claude/api-context.md + docs/screen-inventory.md  # SỬA — RATE_LIMITED 429, bump v0.3.0
```

**Structure Decision**: Không tạo Django app mới (Constitution XII). Rate limiting, error mapping, signing-key check, Sentry scrubbing đều là mối quan tâm cross-cutting → đặt ở `core/`. Throttle được áp per-view qua `throttle_classes` (rõ ràng, không throttle nhầm endpoint đọc). Sentry chỉ chạy ở production/staging (env DSN); dev/test không có DSN nên inert.

## Complexity Tracking

> Không có vi phạm Constitution cần justify — bảng để trống.
