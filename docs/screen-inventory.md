# Screen Inventory — SoundWave

> **Vai trò**: Bước làm TRƯỚC khi chốt API. `contracts/openapi.yaml` và `.claude/api-context.md` được suy ra từ file này.
> File tồn tại độc lập ở CẢ 2 REPO (`soundwave-backend`, `soundwave-mobile`), đồng bộ tay.
>
> Last updated: 2026-07-25 · Contract version tương ứng: `v0.2.0` (MO-002: Album/Artist Detail có track list)

## Bối cảnh khác biệt so với LiveCanvas

- Nội dung nhạc lấy từ **Jamendo API** (Creative Commons, non-commercial) — backend đóng vai trò **proxy + cache**, không lưu trữ/transcode file audio, không có pipeline admin upload nội dung như wallpaper app.
- **Có tài khoản người dùng thật** (email/password + social login Google/Apple) — vì playlist, bài hát yêu thích, lịch sử nghe cần đồng bộ nhiều thiết bị.
- Không có IAP/premium ở v1 (app chỉ phi thương mại theo điều kiện license Jamendo) — nếu sau này muốn monetize, phải xin giấy phép thương mại từ Jamendo trước, ngoài phạm vi v1.

## Danh sách màn hình

| # | Màn hình | Data cần | Action | Endpoint liên quan |
|---|---|---|---|---|
| 1 | **Onboarding/Login** | — | Đăng ký email/password, đăng nhập, đăng nhập Google/Apple | `POST /auth/register`, `POST /auth/login`, `POST /auth/social-login` |
| 2 | **Home/Discover** | Track/playlist thịnh hành, theo thể loại (genre = tag Jamendo) | Tap → Track Detail hoặc Player | `GET /catalog/trending`, `GET /catalog/genres` |
| 3 | **Search** | Kết quả track/artist/album theo từ khóa | Scroll load thêm (cursor), tap → Detail | `GET /catalog/tracks?search=...` |
| 4 | **Track/Album/Artist Detail** | Metadata đầy đủ; Album/Artist Detail kèm **danh sách track** (`AlbumDetail`/`ArtistDetail`) | Play, Play-all, Like (read-only ở MO-002), Thêm vào playlist (MO-003) | `GET /catalog/tracks/{id}` → `Track`, `GET /catalog/albums/{id}` → `AlbumDetail`, `GET /catalog/artists/{id}` → `ArtistDetail` |
| 5 | **Now Playing (Player)** | Track hiện tại, queue, trạng thái play/pause | Play/Pause, Seek, Next/Prev, Shuffle/Repeat, Like, Thêm vào playlist, Log lịch sử nghe | `POST /me/history` |
| 6 | **Mini Player** (persistent bar) | Track hiện tại rút gọn | Play/Pause, tap → mở Now Playing | — (dùng lại state Now Playing) |
| 7 | **Library — Playlists** | Danh sách playlist của user | Tạo playlist mới, tap → Playlist Detail | `GET /me/playlists`, `POST /me/playlists` |
| 8 | **Playlist Detail** | Track trong playlist, thứ tự | Thêm/xóa track, đổi thứ tự, đổi tên/xóa playlist | `GET /me/playlists/{id}`, `POST/DELETE /me/playlists/{id}/tracks`, `PATCH /me/playlists/{id}` |
| 9 | **Library — Liked Songs** | Danh sách track đã like | Bỏ thích, tap → Player | `GET /me/liked-tracks` |
| 10 | **Profile/Settings** | Thông tin tài khoản | Đăng xuất, xóa tài khoản | `GET /me`, `DELETE /me` |

## Quyết định đã chốt (ảnh hưởng response schema)

- **Pagination**: cursor-based (giữ nguyên chuẩn từ LiveCanvas) cho mọi list: `catalog/tracks`, `me/playlists`, `me/liked-tracks`, `me/history`.
- **Backend proxy Jamendo**: mobile KHÔNG gọi thẳng Jamendo API — luôn qua backend (`/catalog/*`), để: (1) giấu Jamendo client_id, (2) cache giảm quota, (3) dễ đổi nguồn nhạc sau này mà không đổi mobile app.
- **Audio streaming**: dùng thẳng URL stream công khai từ Jamendo (backend không tự lưu trữ/transcode file nhạc) — khác hẳn LiveCanvas (không cần S3 storage cho audio, không cần admin upload pipeline).
- **Auth 2 tầng**: `X-App-Key` (mọi request) + `Authorization: Bearer <user_access_token>` (riêng cho `/me/*`, sau khi user đăng nhập) — khác LiveCanvas ở chỗ đây là **user token thật**, không phải admin token.

## Giả định chưa xác nhận

- **Offline download**: Jamendo cho phép download 1 số track theo license CC, nhưng v1 giả định **KHÔNG làm tính năng tải offline** — chỉ streaming trực tiếp. Nếu cần offline, phải xem lại điều khoản license từng track (`license.download` field từ Jamendo) trước khi thêm.
- **Không có admin panel** ở v1 — nội dung hoàn toàn tự động từ Jamendo, không cần màn quản trị nào.
