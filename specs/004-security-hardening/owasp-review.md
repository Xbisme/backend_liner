# OWASP Review — BE-004 Security Hardening

> Deliverable của US4 (FR-019). Rà soát bề mặt tấn công của SoundWave Backend theo
> OWASP API Security Top 10 (2023). Mỗi mục: trạng thái + khắc phục hoặc lý do chấp
> nhận. Ngày: 2026-07-25 · Nhánh: `BE-004-security-hardening`.

## OWASP API Security Top 10 (2023)

| # | Rủi ro | Trạng thái | Ghi chú / Khắc phục |
|---|---|---|---|
| API1 | **Broken Object Level Authorization (BOLA/IDOR)** | ✅ Đã kiểm | Mọi `/me/*` scope theo `request.user` (không tin `user_id` client khai). Playlist + nested (tracks/reorder/delete) → 403 cross-user (`test_playlists_idor.py`); liked-tracks + history user-scoped (`test_idor_sweep.py`, BE-004). `get_owned_playlist_or_error`: 403 khi của người khác, 404 khi thật sự không tồn tại. |
| API2 | **Broken Authentication** | ✅ Đã cứng | JWT access ngắn hạn + refresh rotation + blacklist; logout thu hồi per-session, idempotent (BE-004 US2). Khóa ký HS256 fail-fast nếu <32 bytes ở production (FR-010). Brute-force login/register/social throttled per-IP (BE-004 US1). Password hash Argon2id. Social `id_token` verify server-side. |
| API3 | **Broken Object Property Level Authorization** | ✅ | Serializers là tầng shape duy nhất; không expose field nội bộ (vd Jamendo `client_id`, `tag` genre không serialize). Response khớp `openapi.yaml`. |
| API4 | **Unrestricted Resource Consumption** | ✅ Đã cứng (BE-004) | Rate limit theo nhóm: auth per-IP (10/min), catalog per-IP (120/min), ghi `/me/*` per-user (60/min), history per-user (120/min) — settings-driven. Cache Redis chặn stampede tới Jamendo (`test_cache_load.py`). Pagination cursor giới hạn `limit` max 50. Timeout upstream tường minh. |
| API5 | **Broken Function Level Authorization** | ✅ | `/me/*` + logout yêu cầu Bearer JWT (`IsAuthenticated`); catalog chỉ Layer-1 `X-App-Key`. Không có endpoint admin/privileged ở v1. |
| API6 | **Unrestricted Access to Sensitive Business Flows** | ✅ | Luồng nhạy cảm (auth, ghi history) đã throttle. Không có flow thương mại (Constitution XIII). |
| API7 | **Server Side Request Forgery (SSRF)** | ✅ | Backend chỉ gọi Jamendo qua base URL cấu hình sẵn (`JAMENDO_API_BASE_URL`); không có endpoint nhận URL từ client để fetch. |
| API8 | **Security Misconfiguration** | ✅ Đã cứng | Production: HTTPS redirect, HSTS (1y, preload, subdomains), secure cookies, `SECURE_PROXY_SSL_HEADER`. CORS allowlist tường minh (không `*`) — nay được `django-cors-headers` thực thi (BE-004). `DEBUG=False` prod. Secrets qua env, không hardcode. |
| API9 | **Improper Inventory Management** | ✅ | Contract `openapi.yaml` v0.3.0 là nguồn sự thật; `api-context.md` đồng bộ. Không có endpoint không tài liệu hóa. |
| API10 | **Unsafe Consumption of APIs** | ✅ | Mọi lỗi Jamendo (timeout/5xx/429/non-success) → `502 CATALOG_UPSTREAM_ERROR`, không rò rỉ raw upstream; log ngữ cảnh (endpoint/status/latency) không dump body/URL (FR-014). Response upstream validate qua mapper trước khi dùng. |

## Kiểm tra bổ sung

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Secrets trong log | ✅ | `SensitiveDataFilter` (log) + Sentry `before_send` `_scrub` (BE-004) che password/token/id_token/`client_id`/Authorization/`X-App-Key`. `send_default_pii=False`. |
| Rate-limit fail mode | ✅ | Redis lỗi → fail-open cho chức năng (`/me/*`,`/catalog/*`), fail-closed cho `/auth/*` (không mở toang brute-force). FR-006a. |
| IP spoofing sau proxy | ✅ | Throttle dùng DRF `NUM_PROXIES` (env, default 0 = REMOTE_ADDR, không tin `X-Forwarded-For` mù quáng). |
| Reflected error codes | ✅ | Envelope chuẩn `{error:{code,message}}` qua một handler; client branch trên `code` ổn định. |

## Phát hiện & xử lý

| Phát hiện (khi khảo sát code BE-004) | Mức | Xử lý |
|---|---|---|
| `LogoutView` vô tình `revoke_all` khi thiếu body → all-device logout ngoài ý muốn | Trung bình | ✅ Sửa: chỉ revoke token được trình, idempotent (T018). |
| Khóa ký HS256 (`SECRET_KEY`) dev chỉ 22 bytes | Cao (nếu lên prod) | ✅ Fail-fast prod nếu <32 bytes (T019) + deploy system check (T020). Dev/test miễn (DEBUG). Cần đặt `DJANGO_SECRET_KEY` ≥32 bytes khi deploy. |
| `CORS_ALLOWED_ORIGINS` set nhưng `django-cors-headers` chưa cài → setting vô hiệu | Thấp (client native) | ✅ Cài + wire middleware (T027). |
| `sentry-sdk` init ở production nhưng thiếu trong requirements | Trung bình | ✅ Thêm vào base.txt + wiring scrub đầy đủ (T023/T024). |
| Throttle chưa wire dù env key tồn tại | Cao | ✅ Wire per-view + rates settings-driven (US1). |

## Lưu ý vận hành (không phải lỗ hổng)

- **Đặt `DJANGO_SECRET_KEY` ≥ 32 bytes** ở staging/production (nếu không, boot fail — đúng thiết kế).
- **`NUM_PROXIES`**: đặt đúng số hop khi triển khai sau load balancer/reverse proxy để throttle theo IP chính xác.
- **`CORS_ALLOWED_ORIGINS`**: chỉ cần khi có web client; để trống nếu chỉ mobile native.
- **Ngưỡng rate limit**: mặc định thận trọng; theo dõi và điều chỉnh qua env theo lưu lượng thật.

**Kết luận**: Không còn phát hiện High/Critical chưa xử lý. Tất cả mục OWASP API Top 10 đã rà; các sửa đổi có test tương ứng (BE-004). Sẵn sàng cho BE-005 (deploy).
