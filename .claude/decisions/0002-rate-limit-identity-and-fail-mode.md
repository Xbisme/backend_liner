# 0002. Định danh rate-limit + hành vi fail khi store lỗi

- **Status**: Accepted
- **Date**: 2026-07-25
- **Liên quan**: spec BE-004 · contract v0.3.0 · research R1/R3

## Context

BE-004 thêm rate limiting. Hai câu hỏi thiết kế có hệ quả dài hạn:

1. **Định danh cho endpoint ẩn danh.** `/auth/*` và `/catalog/*` không có user
   token. Clarify ban đầu chốt: catalog throttle theo `X-App-Key` (IP fallback).
   Nhưng khi khảo sát code phát hiện **`X-App-Key` là một secret dùng chung cho
   toàn bộ app build** (mọi cài đặt gửi cùng một key). Key throttle thuần theo
   `X-App-Key` → một bucket toàn cục cho tất cả người dùng → hoặc ngưỡng vô nghĩa
   hoặc chặn nhầm cả userbase.

2. **Hành vi khi store đếm (Redis) sự cố.** Fail-open (cho qua) hay fail-closed
   (chặn)?

## Decision

1. **Định danh throttle**:
   - `/auth/*` → **per-IP** (chống brute-force per-attacker).
   - `/catalog/*` → **per-IP** (per-device) — nâng nhánh "IP fallback" của clarify
     thành primary, vì `X-App-Key` không phân biệt được caller. `X-App-Key` vẫn là
     cổng Layer-1. Cache Redis đã chặn phần lớn tải tới Jamendo. Đã xác nhận lại
     với người dùng ở bước plan.
   - ghi `/me/*` → **per-user**; `POST /me/history` scope riêng, ngưỡng cao hơn.
   - Client IP đọc an toàn sau proxy qua DRF `NUM_PROXIES` (không tin
     `X-Forwarded-For` mù quáng).

2. **Fail mode khi Redis lỗi** (FR-006a):
   - **fail-open** cho endpoint chức năng (`/me/*`, `/catalog/*`) — không chặn
     nhầm người dùng hợp lệ vì store lỗi; ghi `log.warning`.
   - **fail-closed** cho `/auth/*` — không mở toang brute-force khi mất phòng thủ.

Vượt hạn mức → `429 RATE_LIMITED` + header `Retry-After` (contract v0.3.0,
additive). Ngưỡng là settings-driven (`THROTTLE_*` env), không hardcode.

## Consequences

- (+) Throttle nhắm đúng nguồn lạm dụng thật (per-device/per-user/per-attacker),
  không chặn nhầm toàn app.
- (+) Availability được ưu tiên cho luồng chức năng khi Redis chập chờn, nhưng
  auth vẫn được bảo vệ.
- (−) Không có circuit-breaker toàn cục theo `X-App-Key` cho catalog; nếu quota
  Jamendo bị đe dọa ở tầng tổng (tấn công phân tán), cần bổ sung throttle thứ hai
  theo `X-App-Key` với ngưỡng cao — để ngỏ, dễ thêm.
- (−) Sau reverse proxy phải cấu hình `NUM_PROXIES` đúng, nếu không client IP sai
  → throttle nhầm.
- Được ràng buộc bởi Constitution VIII (Security Hardening) + VI (config env-driven).
