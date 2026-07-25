# Feature Specification: User Library

**Feature Branch**: `BE-003-user-library`

**Created**: 2026-07-25

**Status**: Draft

**Input**: User description: "BE-003 User Library — app `apps/library`. Toàn bộ endpoint `/me/*` cần user token (Bearer JWT), chống IDOR tuyệt đối. Models: Playlist (CRUD tên), PlaylistTrack (track_id Jamendo + position, thêm/xóa/reorder), LikedTrack (like/unlike/list), ListeningHistory (ghi lượt nghe + list gần đây). Contract-first; track_id chỉ là chuỗi tham chiếu Jamendo, backend không lưu metadata bài hát; phân trang cursor thống nhất; không hardcode."

## Clarifications

### Session 2026-07-25

- Q: Khi một track đã lưu (trong playlist / liked / history) không còn khả dụng từ nguồn nhạc (Jamendo trả rỗng/404 lúc hiển thị danh sách), danh sách phải trả gì? → A: **Tombstone** — vẫn trả item giữ `track_id` kèm cờ `available: false`, các field metadata để `null`. Danh sách KHÔNG âm thầm loại bỏ track; client hiển thị "không còn khả dụng" và cho phép user xóa. ⚠️ Cần thêm field `available` (và cho phép metadata null) vào schema `Track` trong contract → **Contract change**, xác nhận cùng mobile khi freeze #000.
- Q: Ngữ nghĩa "lịch sử nghe" của `GET /me/history` và có giới hạn lưu trữ không? → A: **Distinct "recently played" + cap** — mỗi `track_id` xuất hiện tối đa MỘT lần, theo lượt nghe gần nhất; `POST /me/history` lại cùng track chỉ cập nhật `played_at` (upsert) chứ không tạo dòng mới. Mỗi user giữ tối đa `HISTORY_MAX_ENTRIES` mục gần nhất (mặc định 100, là settings-constant — không hardcode); ghi mới vượt trần thì đẩy mục cũ nhất ra.
- Q: Khi hydrate metadata cho một danh sách mà TOÀN BỘ tầng catalog/Jamendo lỗi/timeout (khác với một track lẻ không tìm thấy)? → A: **`502 CATALOG_UPSTREAM_ERROR`** — sự cố upstream toàn cục là lỗi tạm thời, trả 502 (mã đã có), KHÔNG suy biến thành tombstone-toàn-bộ (vốn nghĩa "chết vĩnh viễn"). Tombstone chỉ dùng cho track lẻ không tra được khi upstream vẫn hoạt động.
- Q: Truy cập tài nguyên của user khác (playlist/track/liked/history người khác) trả 403 hay 404? → A: **`403 FORBIDDEN` nhất quán** cho mọi thao tác cross-user, khớp `api-context.md` hiện có. Bỏ hô-ứng "hoặc NOT_FOUND"; `404 NOT_FOUND` chỉ dành cho tài nguyên thực sự không tồn tại (của chính user).
- Q: Xóa một `track_id` KHÔNG có trong playlist trả gì? → A: **`204` idempotent** — trạng thái cuối (track không còn trong playlist) đã đạt; đồng bộ với unlike idempotent.
- Q: `GET /me/playlists` sắp theo thứ tự nào (khóa con trỏ)? → A: **`updated_at` giảm dần**, khóa con trỏ ổn định `(updated_at, id)`; playlist vừa sửa/thêm-xóa-reorder track nổi lên đầu → `updated_at` MUST được cập nhật khi nội dung/tên playlist đổi.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Quản lý playlist cá nhân (Priority: P1)

Người dùng đã đăng nhập muốn tự tổ chức nhạc: tạo playlist mới, đặt tên, thêm bài hát vào playlist, xóa bài khỏi playlist, sắp xếp lại thứ tự bài, đổi tên và xóa playlist. Mỗi người chỉ thấy và thao tác được trên playlist của chính mình.

**Why this priority**: Playlist là chức năng thư viện cốt lõi và có nhiều thao tác nhất (CRUD + track + reorder). Nó là lý do người dùng cần tài khoản thật đồng bộ đa thiết bị. Nếu chỉ làm một user story cho MVP thì đây là user story mang lại giá trị lớn nhất.

**Independent Test**: Với hai người dùng khác nhau, tạo playlist cho từng người, thêm/xóa/đổi thứ tự track, xác nhận mỗi người chỉ truy cập được playlist của mình (người khác → `FORBIDDEN`/`NOT_FOUND`), và thứ tự track được giữ đúng qua các lần đọc lại.

**Acceptance Scenarios**:

1. **Given** người dùng đã đăng nhập, **When** tạo playlist với một tên, **Then** nhận về playlist rỗng (`track_count = 0`) thuộc về mình.
2. **Given** người dùng có một playlist, **When** thêm một track (bằng định danh track của nguồn nhạc), **Then** track được thêm vào cuối danh sách và lần xem chi tiết sau phản ánh đúng.
3. **Given** một track đã có trong playlist, **When** thêm lại chính track đó, **Then** nhận lỗi `TRACK_ALREADY_IN_PLAYLIST` (409), playlist không đổi.
4. **Given** một playlist có nhiều track, **When** gửi danh sách track theo thứ tự mới, **Then** thứ tự được cập nhật; nếu danh sách gửi lên không khớp đúng tập track hiện có, nhận lỗi `REORDER_MISMATCH` (400).
5. **Given** người dùng A và playlist của người dùng B, **When** A cố xem/sửa/xóa playlist của B, **Then** A nhận `FORBIDDEN` (403), không dữ liệu nào của B bị lộ hay thay đổi.
6. **Given** người dùng có một playlist, **When** đổi tên rồi xóa playlist, **Then** đổi tên trả về playlist cập nhật (200) và xóa trả về `204`, playlist biến mất khỏi danh sách.

---

### User Story 2 - Bài hát yêu thích (Liked Songs) (Priority: P2)

Người dùng chạm "thích" trên một bài hát ở bất kỳ màn hình nào (chi tiết, player, trong playlist) để lưu vào danh sách yêu thích, và có thể bỏ thích. Màn "Liked Songs" liệt kê toàn bộ bài đã thích.

**Why this priority**: Là tương tác nhanh và phổ biến nhất của người nghe, nhưng đơn giản hơn playlist (không có thứ tự/CRUD phức tạp). Bổ trợ cho thư viện sau khi playlist đã hoạt động.

**Independent Test**: Like một track, xác nhận nó xuất hiện trong danh sách yêu thích; like lại vẫn thành công không lỗi (idempotent); unlike thì biến mất; danh sách yêu thích của user này không lẫn của user khác.

**Acceptance Scenarios**:

1. **Given** người dùng đã đăng nhập, **When** like một track, **Then** nhận `204`; track xuất hiện trong danh sách yêu thích.
2. **Given** một track đã được like, **When** like lại chính track đó, **Then** vẫn nhận `204` (idempotent, không tạo bản ghi trùng, không lỗi).
3. **Given** một track đã được like, **When** unlike, **Then** nhận `204`; track không còn trong danh sách yêu thích.
4. **Given** người dùng có danh sách yêu thích dài, **When** yêu cầu danh sách kèm con trỏ phân trang, **Then** nhận trang bài hát chuẩn hóa với `next_cursor`/`has_more`.

---

### User Story 3 - Lịch sử nghe (Listening History) (Priority: P3)

Khi người dùng nghe một bài (nghe hết hoặc chuyển bài giữa chừng), app ghi lại lượt nghe. Người dùng có thể xem lại các bài đã nghe gần đây.

**Why this priority**: Tăng trải nghiệm (gợi ý "nghe lại", tiếp tục nghe) nhưng không bắt buộc để thư viện hoạt động; ghi/đọc lịch sử độc lập với playlist và liked.

**Independent Test**: Ghi vài lượt nghe cho một user, xác nhận danh sách lịch sử trả về theo thời điểm nghe giảm dần và chỉ gồm lượt nghe của user đó.

**Acceptance Scenarios**:

1. **Given** người dùng đang nghe nhạc, **When** một bài kết thúc hoặc bị chuyển giữa chừng, **Then** hệ thống ghi nhận lượt nghe (kèm thời điểm và trạng thái nghe-hết/dở) và trả `201`.
2. **Given** người dùng đã nghe một số bài, **When** yêu cầu lịch sử nghe, **Then** nhận danh sách bài hát chuẩn hóa sắp theo thời điểm nghe **giảm dần**, phân trang bằng con trỏ.
3. **Given** hai người dùng khác nhau, **When** mỗi người xem lịch sử, **Then** mỗi người chỉ thấy lượt nghe của chính mình.

---

### Edge Cases

- **IDOR trên mọi tài nguyên `/me/*`**: mọi truy vấn playlist/track-trong-playlist/liked/history MUST được giới hạn theo chủ sở hữu suy ra từ token; `user_id` do client tự khai trong body/query MUST bị bỏ qua hoàn toàn. Thao tác trên tài nguyên của người khác → `FORBIDDEN` (403). `NOT_FOUND` (404) chỉ dành cho tài nguyên thực sự không tồn tại.
- **Track lẻ không còn khả dụng ở nguồn (upstream vẫn sống)**: khi hiển thị danh sách (liked/history/playlist detail), một `track_id` đã lưu không tra được metadata → hệ thống MUST trả **tombstone**: item giữ `track_id`, `available = false`, metadata `null`; KHÔNG loại bỏ khỏi danh sách và KHÔNG gây lỗi toàn danh sách.
- **Hydrate cả cụm thất bại (upstream lỗi/timeout toàn cục)**: khác với track lẻ ở trên — khi cả tầng catalog/Jamendo không phản hồi lúc hydrate một danh sách, hệ thống MUST trả `CATALOG_UPSTREAM_ERROR` (502), KHÔNG suy biến thành tombstone-toàn-bộ.
- **Thêm track vào playlist người khác / playlist không tồn tại**: playlist của người khác → `FORBIDDEN` (403); playlist thực sự không tồn tại → `NOT_FOUND` (404). Không được ghi vào playlist nào khác.
- **Reorder không khớp**: danh sách `track_ids` gửi lên thiếu/thừa/sai so với tập track hiện có của playlist → `REORDER_MISMATCH` (400); thứ tự cũ giữ nguyên.
- **Xóa track không có trong playlist**: xóa một `track_id` không tồn tại trong playlist → `204` (idempotent, không lỗi), đồng bộ với unlike idempotent.
- **Like idempotent / unlike không tồn tại**: like lại → `204`; unlike một track chưa từng like → `204` (không lỗi).
- **`played_at` do client gửi**: nếu thiếu thì lấy thời điểm server; nếu client gửi thời điểm tương lai/không hợp lệ → `VALIDATION_ERROR` (400).
- **Phân trang con trỏ hỏng**: `cursor` không giải mã được → `VALIDATION_ERROR` (400), không phải 500. `limit` tuân theo cùng chuẩn catalog (mặc định 20, tối đa 50, clamp).
- **Xóa tài khoản (`DELETE /me`)**: MUST cascade xóa toàn bộ playlist, playlist-track, liked, history của user; không để lại bản ghi mồ côi.
- **Tên playlist**: rỗng/chỉ khoảng trắng/vượt độ dài tối đa → `VALIDATION_ERROR` (400).
- **Thiếu/hết hạn token**: `/me/*` thiếu token → `UNAUTHORIZED_USER` (401); token hết hạn → `TOKEN_EXPIRED` (401); token bị thu hồi/không hợp lệ → `TOKEN_INVALID` (401). Thiếu/sai `X-App-Key` → `INVALID_APP_KEY` (401) trước cả kiểm tra user token.

## Requirements *(mandatory)*

### Functional Requirements

**Chung / bảo mật**

- **FR-001**: Mọi endpoint `/me/*` MUST yêu cầu cả hai tầng auth (`X-App-Key` + user JWT hợp lệ); chủ sở hữu tài nguyên MUST được suy ra từ token, KHÔNG BAO GIỜ từ định danh do client cung cấp.
- **FR-002**: Mọi truy vấn dữ liệu thư viện MUST được lọc theo chủ sở hữu; truy cập/sửa/xóa tài nguyên của người dùng khác MUST trả `FORBIDDEN` (403) nhất quán trên mọi endpoint, không lộ và không thay đổi dữ liệu. `NOT_FOUND` (404) chỉ dùng cho tài nguyên thực sự không tồn tại.
- **FR-003**: Mọi danh sách (`/me/playlists`, `/me/liked-tracks`, `/me/history`) MUST dùng phân trang con trỏ thống nhất `{ items, next_cursor, has_more }` giống chuẩn catalog (mặc định `limit` 20, tối đa 50).
- **FR-004**: Hệ thống MUST KHÔNG lưu metadata bài hát; chỉ lưu `track_id` tham chiếu nguồn nhạc. Khi response cần thông tin bài hát đầy đủ (liked/history/playlist detail), metadata MUST được lấy từ tầng catalog tại thời điểm đọc, không được sao chép/đóng băng vào bảng thư viện.
- **FR-004a**: Khi hydrate một danh sách gặp lỗi upstream toàn cục (catalog/Jamendo timeout/5xx), hệ thống MUST trả `CATALOG_UPSTREAM_ERROR` (502); chỉ khi một `track_id` lẻ không tra được (upstream vẫn sống) mới trả **tombstone** (`available = false`, metadata `null`) cho riêng track đó.
- **FR-005**: Toàn bộ error MUST dùng envelope chuẩn và mã lỗi từ catalog hiện có (`FORBIDDEN`, `NOT_FOUND`, `TRACK_ALREADY_IN_PLAYLIST`, `REORDER_MISMATCH`, `VALIDATION_ERROR`, các mã auth); KHÔNG thêm shape lỗi tùy tiện.

**Playlist**

- **FR-006**: Người dùng MUST tạo được playlist mới với một tên; playlist mới rỗng (`track_count = 0`) và thuộc về người tạo.
- **FR-007**: Người dùng MUST xem được danh sách playlist của mình (phân trang, sắp theo `updated_at` **giảm dần** với khóa con trỏ ổn định `(updated_at, id)`) và chi tiết một playlist kèm danh sách track theo đúng thứ tự. `updated_at` của playlist MUST được cập nhật khi tên hoặc nội dung (thêm/xóa/reorder track) thay đổi.
- **FR-008**: Người dùng MUST đổi được tên playlist của mình và xóa được playlist (xóa kéo theo mọi track-trong-playlist của nó).
- **FR-009**: Người dùng MUST thêm được một track vào playlist (mặc định vào cuối); thêm một track đã có sẵn → `TRACK_ALREADY_IN_PLAYLIST` (409).
- **FR-010**: Người dùng MUST xóa được một track khỏi playlist theo `track_id`; xóa một `track_id` không có trong playlist MUST trả `204` (idempotent, không lỗi).
- **FR-011**: Người dùng MUST sắp xếp lại thứ tự track bằng cách gửi toàn bộ danh sách `track_ids` theo thứ tự mới; danh sách gửi lên MUST khớp đúng tập track hiện có của playlist, nếu không → `REORDER_MISMATCH` (400). Thứ tự MUST ổn định và duy nhất trong một playlist.
- **FR-012**: Tên playlist MUST được validate (không rỗng/khoảng trắng, trong giới hạn độ dài); vi phạm → `VALIDATION_ERROR` (400).

**Liked Tracks**

- **FR-013**: Người dùng MUST like được một track theo `track_id`; thao tác like MUST idempotent (like lại → `204`, không tạo bản ghi trùng).
- **FR-014**: Người dùng MUST unlike được một track; unlike một track chưa từng like MUST không gây lỗi (`204`).
- **FR-015**: Người dùng MUST xem được danh sách track đã like (phân trang), trả về bài hát chuẩn hóa.

**Listening History**

- **FR-016**: Người dùng MUST ghi được một lượt nghe với `track_id`, thời điểm nghe (`played_at`, mặc định thời điểm server nếu thiếu), và trạng thái nghe-hết (`completed`); trả `201`. Ghi lại cùng một `track_id` MUST **upsert** — cập nhật `played_at`/`completed` của mục hiện có thay vì tạo dòng mới (mỗi track một mục).
- **FR-017**: Người dùng MUST xem được lịch sử nghe của mình dưới dạng "recently played" **distinct** (mỗi `track_id` một lần), sắp theo `played_at` **giảm dần**, phân trang bằng con trỏ.
- **FR-017a**: Lịch sử mỗi user MUST giới hạn ở `HISTORY_MAX_ENTRIES` mục gần nhất (mặc định 100, định nghĩa như settings-constant); khi vượt trần, mục có `played_at` cũ nhất MUST bị loại bỏ.
- **FR-018**: `played_at` không hợp lệ (ví dụ tương lai/sai định dạng) MUST trả `VALIDATION_ERROR` (400).

**Xóa tài khoản**

- **FR-019**: `DELETE /me` MUST cascade xóa toàn bộ playlist, playlist-track, liked, history của user; không để lại bản ghi mồ côi.

**Contract**

- **FR-020**: Nếu có bất kỳ thay đổi shape request/response so với `contracts/openapi.yaml` + `.claude/api-context.md` hiện tại, contract MUST được cập nhật TRƯỚC (cả 3 file đồng bộ) rồi mới tới code; endpoint `/me/*` mới/đổi MUST khớp contract.
- **FR-021**: Schema `Track` MUST bổ sung cờ `available` (boolean) và cho phép các field metadata `null` khi `available = false` (hỗ trợ tombstone của FR/edge-case track chết). Đây là thay đổi contract → cập nhật `openapi.yaml` + `api-context.md`, bump/ghi chú version, và cờ Contract Sync với mobile khi freeze #000.

### Key Entities *(include if feature involves data)*

- **Playlist**: bộ sưu tập nhạc do một người dùng sở hữu. Thuộc tính: chủ sở hữu (người dùng), tên, số lượng track (dẫn xuất), thời điểm tạo/cập nhật. Quan hệ: sở hữu bởi một User; chứa nhiều PlaylistTrack có thứ tự.
- **PlaylistTrack**: một track trong một playlist. Thuộc tính: `track_id` (chuỗi tham chiếu nguồn nhạc, KHÔNG phải khóa ngoại sang catalog), vị trí/thứ tự trong playlist. Ràng buộc: `track_id` duy nhất trong một playlist; vị trí ổn định & duy nhất theo playlist.
- **LikedTrack**: đánh dấu một người dùng thích một track. Thuộc tính: chủ sở hữu (người dùng), `track_id`, thời điểm like. Ràng buộc: (user, track_id) duy nhất (idempotent).
- **ListeningHistory**: mục "đã nghe gần đây" của một người dùng. Thuộc tính: chủ sở hữu (người dùng), `track_id`, `played_at`, `completed` (nghe hết hay dở). Ràng buộc: **(user, track_id) duy nhất** (upsert theo track); mỗi user giữ tối đa `HISTORY_MAX_ENTRIES` mục, cắt bớt mục cũ nhất.
- **User** (đã có ở BE-001): chủ sở hữu của mọi tài nguyên trên; là gốc cascade khi xóa tài khoản.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% thao tác trên tài nguyên của người dùng khác bị chặn — trong kiểm thử IDOR, không một request nào của user A đọc/sửa/xóa được dữ liệu của user B (luôn `FORBIDDEN`/`NOT_FOUND`, không rò rỉ nội dung).
- **SC-002**: Thứ tự track trong một playlist được giữ đúng 100% qua thêm/xóa/reorder và các lần đọc lại; không có trường hợp thứ tự bị đảo hoặc trùng vị trí.
- **SC-003**: Like/unlike là idempotent — lặp lại thao tác không tạo bản ghi trùng và không trả lỗi; danh sách yêu thích luôn phản ánh đúng trạng thái cuối.
- **SC-004**: Mọi danh sách thư viện phân trang không bỏ sót và không trùng bản ghi khi duyệt hết các trang bằng con trỏ.
- **SC-005**: Xóa tài khoản không để lại bất kỳ bản ghi playlist/track/liked/history mồ côi nào (kiểm chứng bằng truy vấn sau khi xóa).
- **SC-006**: Mọi response `/me/*` khớp đúng shape trong `contracts/openapi.yaml` (kiểm thử contract cho cả happy path và error path).
- **SC-007**: Không có bí mật/`user_id`-client-khai nào ảnh hưởng tới phân quyền; kiểm thử xác nhận thay đổi `user_id` trong payload không đổi được kết quả phân quyền.

## Assumptions

- **Contract gần như đã khóa**: `contracts/openapi.yaml` + `.claude/api-context.md` v0.1.0 đã định nghĩa đầy đủ bề mặt `/me/*` (endpoint, status, error code). BE-003 chủ yếu **triển khai đúng contract hiện có**; chỉ bổ sung schema `Playlist`/`PlaylistDetail`/history nếu contract còn thiếu, và mọi bổ sung tuân thủ Contract-First.
- **Hydrate metadata qua tầng catalog**: vì backend không lưu metadata bài hát (yêu cầu người dùng) nhưng contract trả về đối tượng `Track` đầy đủ trong liked/history/playlist-detail, thư viện MUST lấy metadata từ tầng catalog tại thời điểm đọc — qua một dịch vụ công khai của `apps/catalog` (batch theo nhiều `track_id`, tận dụng cache), KHÔNG import nội bộ chéo app (theo Hiến pháp III). Cách gọi cụ thể chốt ở phase plan.
- **`is_liked` trong response thư viện**: các response có ngữ cảnh người dùng (liked/history/playlist-detail) MUST đặt `is_liked` theo tập LikedTrack của chính user đó (khác với endpoint catalog Layer-1 luôn `false`). Chốt cuối ở plan.
- **Ghi lượt nghe không xác thực track với nguồn**: thao tác ghi (like, thêm vào playlist, ghi history) MUST NOT gọi nguồn nhạc để xác thực `track_id` tồn tại (tránh ghép cứng write→upstream và tăng độ trễ); `track_id` được nhận như chuỗi tham chiếu. Track không hợp lệ chỉ biểu hiện khi hydrate lúc đọc (xem clarify unavailable-track).
- **Không lưu snapshot metadata**: không denormalize tên bài/nghệ sĩ/ảnh vào bảng thư viện — trực tiếp mâu thuẫn ràng buộc "backend không lưu metadata bài hát".
- **Quy mô dữ liệu**: dữ liệu thư viện thuộc quy mô cá nhân (hàng trăm–vài nghìn mục/người); phân trang con trỏ đủ đáp ứng, không cần tối ưu đặc biệt ở v1.
- **Rate limit history**: chống spam `POST /me/history` được xử lý ở BE-004 (Security Hardening), không thuộc phạm vi BE-003 trừ khi phát sinh rủi ro rõ ràng.
- **Tên playlist không cần duy nhất**: một user MAY có nhiều playlist cùng tên (không ràng buộc unique trên tên); phân biệt bằng id. Không hỏi lại — mặc định hợp lý theo thông lệ (Spotify-style).
