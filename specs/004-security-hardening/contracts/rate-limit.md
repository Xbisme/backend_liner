# Contract Delta — BE-004 (RATE_LIMITED)

> Thay đổi contract **duy nhất** của BE-004. **Additive → không breaking**. Bump `v0.2.0 → v0.3.0`.
> Áp dụng vào `contracts/openapi.yaml` + `.claude/api-context.md` + `docs/screen-inventory.md` (contract-first, Constitution II) TRƯỚC khi code. Đồng bộ repo mobile khi freeze #000.

## 1. Mã lỗi mới trong Error Code Catalog

| Code | HTTP | Ý nghĩa | Header kèm |
|---|---|---|---|
| `RATE_LIMITED` | `429` | Client vượt hạn mức tần suất; thử lại sau | `Retry-After: <seconds>` |

- Envelope giữ nguyên: `{ "error": { "code": "RATE_LIMITED", "message": "Too many requests, retry later." } }`.
- `Retry-After` (giây) có mặt khi server biết thời điểm cửa sổ mở lại.

## 2. Endpoint bị ảnh hưởng (thêm response 429)

Thêm `429 RATE_LIMITED` vào danh sách response khả dĩ của:
- `POST /auth/login`, `POST /auth/register`, `POST /auth/social-login` (per-IP)
- `GET /catalog/*` (trending, genres, tracks, tracks/{id}, artists/{id}, albums/{id}) (per-IP)
- Ghi `/me/*`: `POST/PUT/PATCH/DELETE /me/playlists*`, `PUT /me/playlists/{id}/tracks` (reorder), `POST/DELETE track`, `POST/DELETE /me/liked-tracks*`, `POST /me/history`, `DELETE /me` (per-user)

> Không thêm 429 cho các GET `/me/*` đọc (không throttle chặt — R2).

## 3. openapi.yaml — mảnh cần thêm

`info.version: "0.3.0"`. Thêm một reusable response:

```yaml
components:
  responses:
    RateLimited:
      description: Too many requests — client exceeded the rate limit.
      headers:
        Retry-After:
          schema: { type: integer }
          description: Seconds until the client may retry.
      content:
        application/json:
          schema: { $ref: '#/components/schemas/Error' }
          example:
            error: { code: RATE_LIMITED, message: "Too many requests, retry later." }
```

Và tham chiếu `429: { $ref: '#/components/responses/RateLimited' }` ở các path mục 2. (Nếu `Error` schema chưa tách reusable, dùng inline khớp envelope hiện có.)

## 4. api-context.md — dòng thêm vào Error Code Catalog

```
| `RATE_LIMITED` | 429 | Vượt hạn mức tần suất — client thử lại sau `Retry-After` giây |
```

Ghi chú thêm mục "Rate limiting" mô tả phạm vi (auth per-IP, catalog per-IP, `/me/*` ghi per-user) để mobile biết chỗ nào có thể gặp 429.

## 5. screen-inventory.md — ghi chú xử lý client

Thêm ghi chú cross-cutting: mọi màn gọi API có thể nhận `429 RATE_LIMITED` → client hiển thị "Bạn thao tác quá nhanh, thử lại sau" và tôn trọng `Retry-After` (đặc biệt màn đăng nhập và tìm kiếm).

## 6. Backward compatibility

- Client cũ chưa biết `RATE_LIMITED` vẫn đọc được envelope chuẩn (`error.code`/`error.message`) và HTTP 429 → xử lý như lỗi chung. Không phá vỡ client hiện tại → **không breaking** (bump minor).
