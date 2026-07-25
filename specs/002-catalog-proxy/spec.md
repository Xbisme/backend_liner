# Feature Specification: Catalog Proxy

**Feature Branch**: `BE-002-catalog-proxy`

**Created**: 2026-07-25

**Status**: Draft

**Input**: User description: "BE-002 Catalog Proxy — apps/catalog. Backend proxy + cache layer cho Jamendo API cho app nghe nhạc SoundWave. Cung cấp các endpoint catalog để mobile lấy nhạc, không lộ Jamendo client_id ra client. File nhạc stream thẳng từ Jamendo. Endpoints: trending, genres, tracks (cursor), tracks/{id}, artists/{id}, albums/{id}. Cache Redis TTL theo loại, map response sang schema Track/Artist/Album, xử lý 502 CATALOG_UPSTREAM_ERROR, auth Layer 1 (X-App-Key)."

## Clarifications

### Session 2026-07-25

- Q: Nguồn danh sách thể loại cho `/catalog/genres`? → A: **Static curated list** trong settings/env (cặp `slug` + tên hiển thị), seed từ bộ genre tag "featured" của Jamendo (electronic, jazz, pop, hiphop, rock, metal, classical, lounge, songwriter, world, relaxation, soundtrack…). `/catalog/genres` trả danh sách này **không gọi Jamendo**; filter `genre` map `slug` → tham số `tags` của Jamendo. (Jamendo v3.0 **không có** endpoint liệt kê genre — genre chỉ là tag.)
- Q: `default`/`max` của `limit` cho `GET /catalog/tracks`? → A: default **20**, max **50** (Jamendo cho tối đa 200 nhưng ta chủ động giới hạn thấp hơn); `limit` nguyên ngoài khoảng bị **clamp về 1–50**, chỉ giá trị không phải số nguyên mới `VALIDATION_ERROR`.
- Q: `search` khớp trường nào? → A: **tên bài + tên nghệ sĩ** — thực thi bằng tham số free-text `search` của Jamendo (bản chất khớp track + artist + album + tag, phủ trọn ý định tìm theo tên ca sĩ/bài hát).
- Q: Số bài `GET /catalog/trending` trả về? → A: **50 bài**, sắp theo độ phổ biến gần đây (Jamendo `order=popularity_month`), một lệnh gọi upstream, cache dài.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Duyệt và tìm nhạc (Priority: P1)

Người dùng mở app SoundWave và muốn khám phá nhạc: xem danh sách nhạc thịnh hành, lọc theo thể loại, hoặc gõ từ khóa để tìm bài hát. App gọi backend để lấy danh sách bài hát đã được chuẩn hóa (tên bài, nghệ sĩ, ảnh bìa, thời lượng, đường dẫn phát) mà không cần biết nguồn nhạc đến từ đâu.

**Why this priority**: Đây là chức năng lõi của một app nghe nhạc — nếu không duyệt/tìm được nhạc thì mọi màn hình khác (playlist, lịch sử) đều vô nghĩa. Là điểm đồng bộ với mobile (MO-002) để chuyển từ dữ liệu giả sang dữ liệu thật.

**Independent Test**: Gọi endpoint danh sách nhạc thịnh hành và endpoint duyệt nhạc (có/không từ khóa, có/không lọc thể loại) với app-key hợp lệ; xác nhận trả về danh sách bài hát đúng cấu trúc chuẩn, phân trang được, và không chứa bất kỳ thông tin nội bộ nào của nguồn nhạc.

**Acceptance Scenarios**:

1. **Given** người dùng có app-key hợp lệ, **When** yêu cầu danh sách nhạc thịnh hành, **Then** nhận được danh sách bài hát chuẩn hóa (tên, nghệ sĩ, ảnh bìa, thời lượng, đường dẫn phát, loại giấy phép).
2. **Given** người dùng gõ một từ khóa tìm kiếm, **When** yêu cầu duyệt nhạc kèm từ khóa, **Then** nhận được trang kết quả có con trỏ phân trang (`next_cursor`, `has_more`) để tải thêm.
3. **Given** người dùng chọn một thể loại, **When** yêu cầu duyệt nhạc kèm thể loại đó, **Then** kết quả chỉ gồm bài hát thuộc thể loại được chọn.
4. **Given** một trang kết quả có `has_more = true`, **When** người dùng yêu cầu trang tiếp theo bằng `next_cursor`, **Then** nhận được các bài hát kế tiếp không trùng lặp với trang trước.

---

### User Story 2 - Xem chi tiết bài hát, nghệ sĩ, album (Priority: P2)

Người dùng chạm vào một bài hát, nghệ sĩ hoặc album để xem thông tin chi tiết và bắt đầu phát nhạc. App lấy chi tiết từ backend bằng định danh của mục đó.

**Why this priority**: Cần cho màn hình chi tiết và trình phát, nhưng chỉ có ý nghĩa sau khi người dùng đã duyệt/tìm được nhạc (US1). Đường dẫn phát nhạc nằm trong chi tiết bài hát để trình phát của app dùng trực tiếp.

**Independent Test**: Với một định danh bài hát/nghệ sĩ/album hợp lệ, gọi endpoint chi tiết tương ứng và xác nhận trả về đúng đối tượng chuẩn hóa; với định danh không tồn tại, xác nhận trả về lỗi "không tìm thấy" theo chuẩn.

**Acceptance Scenarios**:

1. **Given** một định danh bài hát hợp lệ, **When** yêu cầu chi tiết bài hát, **Then** nhận được đối tượng bài hát đầy đủ kèm đường dẫn phát dùng được ngay.
2. **Given** một định danh nghệ sĩ hợp lệ, **When** yêu cầu chi tiết nghệ sĩ, **Then** nhận được thông tin nghệ sĩ chuẩn hóa.
3. **Given** một định danh album hợp lệ, **When** yêu cầu chi tiết album, **Then** nhận được thông tin album chuẩn hóa.
4. **Given** một định danh không tồn tại, **When** yêu cầu chi tiết, **Then** nhận được lỗi `NOT_FOUND` (404) theo envelope chuẩn.

---

### User Story 3 - Danh sách thể loại để lọc (Priority: P3)

Người dùng muốn lọc nhạc theo thể loại; app cần lấy danh sách thể loại có sẵn để hiển thị bộ lọc.

**Why this priority**: Bổ trợ cho trải nghiệm duyệt nhạc (US1) nhưng không bắt buộc để MVP hoạt động — app có thể duyệt nhạc mà chưa có bộ lọc thể loại.

**Independent Test**: Gọi endpoint danh sách thể loại với app-key hợp lệ và xác nhận nhận được danh sách cặp (mã, tên) thể loại.

**Acceptance Scenarios**:

1. **Given** người dùng có app-key hợp lệ, **When** yêu cầu danh sách thể loại, **Then** nhận được danh sách thể loại dạng `{ slug, name }`.

---

### Edge Cases

- **Nguồn nhạc lỗi/timeout/bị giới hạn tần suất**: khi nguồn nhạc thượng nguồn (Jamendo) không phản hồi kịp, trả lỗi hoặc chặn tần suất, hệ thống MUST trả về `CATALOG_UPSTREAM_ERROR` (502) theo envelope chuẩn; lỗi thô của thượng nguồn KHÔNG được lộ ra client.
- **Kết quả rỗng**: từ khóa/thể loại không khớp bài nào MUST trả về danh sách rỗng với `has_more = false` (không phải lỗi).
- **Con trỏ phân trang sai/hỏng**: `cursor` không giải mã được MUST trả về `VALIDATION_ERROR` (400), không phải lỗi 500.
- **`limit` ngoài phạm vi**: giá trị nguyên âm/0/vượt trần MUST được **kẹp (clamp) về khoảng hợp lệ 1–50** (mặc định 20 khi thiếu) — không gửi giá trị vô lý sang thượng nguồn. Chỉ `limit` **không phải số nguyên** mới trả `VALIDATION_ERROR` (400).
- **`genre` không thuộc danh mục**: `slug` không có trong danh sách curated MUST trả `VALIDATION_ERROR` (400), không im lặng bỏ qua bộ lọc.
- **Thiếu/sai app-key**: mọi endpoint catalog thiếu hoặc sai `X-App-Key` MUST trả `INVALID_APP_KEY` (401) trước khi chạm tới nguồn nhạc.
- **Cache nóng vs nguội**: yêu cầu lặp lại cùng tham số trong thời gian TTL MUST được phục vụ từ cache, không gọi lại thượng nguồn.
- **Trạng thái "đã thích" (`is_liked`)**: trong phạm vi BE-002 (chưa có thư viện người dùng — BE-003), trường `is_liked` MUST luôn là `false`/`null`; không endpoint catalog nào yêu cầu user token.
- **Trường thượng nguồn thiếu**: khi một bài hát từ nguồn thiếu ảnh bìa/album/thể loại, hệ thống MUST map an toàn (giá trị rỗng/null theo contract) thay vì lỗi.

## Requirements *(mandatory)*

### Functional Requirements

**Endpoints & dữ liệu trả về**

- **FR-001**: Hệ thống MUST cung cấp endpoint lấy danh sách nhạc thịnh hành, trả về **50** bài hát chuẩn hóa (mảng thẳng, không phân trang) sắp theo độ phổ biến gần đây; hỗ trợ lọc theo thể loại (tùy chọn).
- **FR-002**: Hệ thống MUST cung cấp endpoint danh sách thể loại, trả về danh sách cặp `{ slug, name }` lấy từ **danh sách curated cấu hình trong settings** (không gọi nguồn thượng nguồn). Mã `slug` là danh mục ổn định dùng cho tham số lọc `genre` ở các endpoint khác.
- **FR-003**: Hệ thống MUST cung cấp endpoint duyệt/tìm bài hát hỗ trợ tham số `search` (khớp tên bài + tên nghệ sĩ), `genre` (theo `slug`), `cursor`, `limit`, trả về trang có con trỏ (`items`, `next_cursor`, `has_more`). `limit` mặc định **20**, kẹp trong **1–50** (giá trị không phải số nguyên → `VALIDATION_ERROR`).
- **FR-004**: Hệ thống MUST cung cấp endpoint chi tiết bài hát theo định danh, trả về một bài hát chuẩn hóa gồm đường dẫn phát dùng được trực tiếp.
- **FR-005**: Hệ thống MUST cung cấp endpoint chi tiết nghệ sĩ theo định danh.
- **FR-006**: Hệ thống MUST cung cấp endpoint chi tiết album theo định danh.
- **FR-007**: Định danh không tồn tại ở bất kỳ endpoint chi tiết nào MUST trả về `NOT_FOUND` (404) theo envelope chuẩn.

**Chuẩn hóa & bảo mật nguồn**

- **FR-008**: Mọi phản hồi bài hát/nghệ sĩ/album MUST được ánh xạ về schema `Track`/`Artist`/`Album`/`Genre` trong `contracts/openapi.yaml` trước khi rời backend; trường thô của nguồn thượng nguồn KHÔNG được chuyển tiếp nguyên trạng.
- **FR-009**: Thông tin định danh/khóa truy cập nguồn nhạc (Jamendo `client_id`) và hình dạng phản hồi thô của nguồn MUST KHÔNG BAO GIỜ xuất hiện trong bất kỳ phản hồi nào gửi tới client.
- **FR-010**: Mọi lệnh gọi tới nguồn nhạc thượng nguồn MUST đi qua một điểm truy cập tập trung duy nhất; không thành phần nào khác được tự dựng lời gọi tới nguồn hoặc đọc JSON thô của nó.
- **FR-011**: Khóa/URL/timeout/TTL cấu hình MUST đọc từ settings/env (không hardcode trong code).

**Cache**

- **FR-012**: Hệ thống MUST cache phản hồi catalog trong Redis với TTL đặt tên theo loại: dài cho `trending`/`genres`, ngắn cho `tracks`/tìm kiếm, trung bình cho các endpoint chi tiết.
- **FR-013**: Khóa cache MUST được đặt namespace và bao gồm mọi tham số truy vấn ảnh hưởng tới kết quả (thể loại, từ khóa, cursor, limit, định danh).
- **FR-014**: Yêu cầu lặp lại trong thời gian TTL MUST được phục vụ từ cache mà không gọi lại nguồn thượng nguồn.

**Lỗi & xác thực**

- **FR-015**: Lỗi/timeout/giới hạn tần suất/5xx từ nguồn thượng nguồn MUST được bắt và chuyển thành `CATALOG_UPSTREAM_ERROR` (502) theo envelope chuẩn; lỗi thô KHÔNG được lan ra client. Lệnh gọi thượng nguồn MUST có timeout tường minh.
- **FR-016**: Mọi endpoint catalog MUST yêu cầu `X-App-Key` (Auth Layer 1); thiếu/sai key trả `INVALID_APP_KEY` (401). Endpoint catalog MUST KHÔNG yêu cầu user token (Layer 2) vì nội dung là công khai.
- **FR-017**: Tham số truy vấn sai định dạng (`limit`/`cursor` không hợp lệ) MUST trả `VALIDATION_ERROR` (400) theo envelope chuẩn, không phải lỗi 500.
- **FR-018**: Mọi phản hồi lỗi MUST dùng envelope thống nhất `{ "error": { "code", "message" } }` với mã lấy từ catalog mã lỗi trong `api-context.md`.

### Key Entities *(include if feature involves data)*

- **Track (Bài hát)**: đơn vị nhạc chuẩn hóa — định danh, tên, nghệ sĩ, album, danh sách thể loại, thời lượng (giây), ảnh bìa, đường dẫn phát, loại giấy phép, cờ "đã thích". Là dữ liệu tạm (không lưu vào DB backend ở v1) — nguồn sự thật là Jamendo, backend chỉ proxy + cache.
- **Artist (Nghệ sĩ)**: định danh, tên, ảnh đại diện.
- **Album**: định danh, tiêu đề, nghệ sĩ, ảnh bìa.
- **Genre (Thể loại)**: mã (`slug`) và tên hiển thị; dùng cho bộ lọc.
- **TrackCursorPage (Trang bài hát)**: bao đóng phân trang con trỏ — danh sách bài hát, `next_cursor`, `has_more`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Người dùng có thể duyệt nhạc thịnh hành, tìm theo từ khóa và lọc theo thể loại — 100% các endpoint catalog trong contract trả về dữ liệu đúng cấu trúc chuẩn hóa.
- **SC-002**: Không có phản hồi catalog nào (thành công hay lỗi) chứa định danh/khóa nguồn nhạc hay trường thô của nguồn — xác minh được bằng kiểm thử trên toàn bộ endpoint.
- **SC-003**: Khi nguồn nhạc thượng nguồn hỏng/timeout, 100% trường hợp client nhận `CATALOG_UPSTREAM_ERROR` (502) theo envelope chuẩn thay vì lỗi thô hoặc 500.
- **SC-004**: Yêu cầu lặp lại cùng tham số trong thời gian TTL được phục vụ từ cache — số lần gọi nguồn thượng nguồn giảm rõ rệt so với số request (đo bằng kiểm thử với nguồn được giả lập, đếm số lần gọi).
- **SC-005**: Người dùng tải thêm kết quả qua phân trang con trỏ mà không gặp bản ghi trùng hoặc thiếu giữa các trang.
- **SC-006**: Toàn bộ bộ kiểm thử (unit/service + API + giả lập nguồn) xanh, và pre-commit checklist (black/ruff/mypy/pytest/migrations) xanh.

## Assumptions

- **Nguồn nhạc**: Jamendo API là nguồn duy nhất ở v1; `client_id` thật đã có và đọc từ env (`JAMENDO_CLIENT_ID`). Việc dùng Jamendo giới hạn ở mục đích **phi thương mại** (Constitution XIII).
- **Không lưu trữ audio/metadata**: backend không lưu file nhạc, không transcode, và ở v1 không lưu metadata bài hát vào DB — chỉ proxy + cache. Bài hát được nhận diện bằng định danh Jamendo (chuỗi).
- **`is_liked` trong BE-002**: vì thư viện người dùng (liked tracks) thuộc BE-003, trường `is_liked` luôn `false`/`null` ở phạm vi spec này; endpoint catalog không nhận user token. Việc điền `is_liked` theo user sẽ nối dây ở BE-003.
- **Phân trang con trỏ**: tái dùng cơ chế cursor pagination của `core/` từ BE-001; cursor mã hóa vị trí duyệt (`offset` của Jamendo) — client coi là chuỗi mờ. Jamendo cho `limit` tối đa 200; ta chủ động giới hạn 50.
- **Ánh xạ tham số Jamendo** (đã research doc v3.0, xác nhận trước khi code): `search` free-text → khớp tên bài + nghệ sĩ; `genre` slug → tham số `tags`; trending → `order=popularity_month`; `audioformat` mặc định `mp31` (đọc từ settings, không hardcode); không có endpoint liệt kê genre nên `/catalog/genres` dùng danh sách curated trong settings.
- **Contract có sẵn**: shape endpoint/schema đã định nghĩa trong `contracts/openapi.yaml` + `.claude/api-context.md` (v0.1.0). Spec này thực thi theo contract; nếu phát sinh lệch, cập nhật cả 3 file theo Contract Sync trước khi đổi code.
- **Auth Layer 1 đã có**: middleware `X-App-Key` và error envelope/exception handler đã xây ở BE-001, được tái dùng nguyên trạng.
- **Điểm đồng bộ mobile (MO-002)**: khi merge BE-002, báo repo mobile để chuyển từ mock sang API thật.

## Dependencies

- **BE-001** (đã merge): Django+DRF skeleton, `core/` (error envelope, X-App-Key middleware, cursor pagination, log redaction), settings env-driven.
- **Jamendo API** khả dụng với `client_id` hợp lệ.
- **Redis** khả dụng cho tầng cache.
