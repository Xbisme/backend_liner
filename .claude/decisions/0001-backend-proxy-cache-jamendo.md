# 0001. Backend proxy + cache Jamendo (mobile không gọi thẳng)

- **Status**: Accepted
- **Date**: 2026-07-24
- **Liên quan**: contract v0.1.0 · roadmap BE-002

## Context

App cần nội dung nhạc từ Jamendo API (Creative Commons, phi thương mại). Có hai
lựa chọn: (a) mobile gọi thẳng Jamendo, hoặc (b) mọi request đi qua backend.

Ràng buộc:
- Jamendo `client_id` không được lộ ra client.
- Jamendo có quota; gọi trực tiếp từ mọi thiết bị sẽ đốt quota nhanh.
- Muốn có thể đổi/bổ sung nguồn nhạc sau này mà không phải cập nhật app mobile.

## Decision

Backend đóng vai trò **proxy + cache** trước Jamendo (`/catalog/*`). Mobile
KHÔNG bao giờ gọi thẳng Jamendo. Toàn bộ lời gọi upstream đi qua một wrapper duy
nhất (`JamendoClient`); response Jamendo được map sang schema `Track/Artist/
Album` trong `openapi.yaml` trước khi trả về. Cache bằng Redis với TTL khác nhau
theo độ biến động (trending/genres dài, search ngắn). Lỗi upstream → `502
CATALOG_UPSTREAM_ERROR`.

Audio **không** được backend lưu trữ/transcode — stream thẳng từ URL công khai
của Jamendo.

## Consequences

- (+) Giấu được credential, giảm quota, decouple app khỏi Jamendo.
- (+) Đổi nguồn nhạc sau này không cần đổi mobile (client chỉ thấy schema đã map).
- (−) Backend trở thành điểm phụ thuộc thêm cho luồng nghe nhạc; cần cache tốt +
  xử lý lỗi upstream cẩn thận.
- Được ràng buộc thành nguyên tắc: Constitution Principle IV (Catalog Proxy &
  Cache Discipline).
