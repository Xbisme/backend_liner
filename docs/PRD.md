# PRD — SoundWave (Backend scope)

> Tài liệu tóm tắt sản phẩm ở góc nhìn backend. Chi tiết màn hình → data →
> endpoint nằm trong [`screen-inventory.md`](screen-inventory.md) (nguồn chính
> để suy ra contract). File này chỉ nêu bối cảnh, mục tiêu và phạm vi v1.

## Sản phẩm

SoundWave là app nghe nhạc streaming, nội dung lấy từ **Jamendo** (Creative
Commons, phi thương mại). Người dùng nghe trending/theo thể loại, tìm kiếm, tạo
playlist, thích bài hát, và có lịch sử nghe đồng bộ nhiều thiết bị.

## Mục tiêu backend v1

- Proxy + cache Jamendo qua `/catalog/*` (giấu credential, giảm quota).
- Tài khoản người dùng thật: email/password + Google/Apple sign-in, JWT.
- Thư viện người dùng: playlist (CRUD + reorder), liked tracks, listening history.
- Bảo mật: auth 2 tầng (`X-App-Key` + Bearer), chống IDOR, rate limit, refresh
  token rotation.

## Phạm vi & ràng buộc

- **Trong phạm vi v1**: các màn hình trong `screen-inventory.md` (Onboarding/
  Login, Home/Discover, Search, Detail, Player, Library, Profile/Settings).
- **Ngoài phạm vi v1**: lưu trữ/transcode audio, admin content pipeline, tải
  offline, IAP/premium, tính năng chia sẻ/social.
- **Pháp lý**: chỉ dùng Jamendo cho mục đích phi thương mại; muốn monetize phải
  xin giấy phép thương mại trước (Constitution: Principle XIII).

## Tài liệu liên quan

- [`screen-inventory.md`](screen-inventory.md) — màn hình → endpoint
- [`../contracts/openapi.yaml`](../contracts/openapi.yaml) — contract máy-đọc
- [`../.claude/api-context.md`](../.claude/api-context.md) — chi tiết endpoint
- [`../.claude/sdd-roadmap.md`](../.claude/sdd-roadmap.md) — lộ trình spec
