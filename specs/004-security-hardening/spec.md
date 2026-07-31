# Feature Specification: Security Hardening & Production Readiness

**Feature Branch**: `BE-004-security-hardening`

**Created**: 2026-07-25

**Status**: Draft

**Input**: User description: "BE-004 Security Hardening & Production Readiness — làm cứng bảo mật và sẵn sàng vận hành production cho SoundWave Backend. Scope: (1) Rate limit theo user chống spam, đặc biệt /me/history và các endpoint ghi /me/*, cân nhắc cả rate limit theo X-App-Key; (2) Refresh token rotation + blacklist khi logout (thu hồi không dùng lại được); (3) Tích hợp Sentry giám sát lỗi, không lộ secret trong log; (4) Load test tầng cache catalog (Redis); (5) OWASP review, đặc biệt IDOR ở /me/playlists/{id} và toàn bộ /me/*. Tuân constitution: auth 2 tầng, contract-first, không hardcode. Tín hiệu đã phát hiện: JWT HMAC signing key hiện chỉ 22 bytes < 32 khuyến nghị cho HS256."

## Clarifications

### Session 2026-07-25

- Q: Endpoint ẩn danh (`/auth/*`, `/catalog/*`) chưa có user token — throttle tính theo định danh nào? → A: **`/auth/*` theo IP** (chống brute-force per-attacker), **`/catalog/*` theo `X-App-Key`** (mọi request đều có, bảo vệ quota theo từng app build) với **IP làm fallback**. Đọc IP an toàn sau reverse proxy: chỉ tin header proxy khi cấu hình tường minh số hop tin cậy.
- Q: Vượt hạn mức trả HTTP 429 — mã lỗi trong error envelope? → A: **Thêm mã catalog `RATE_LIMITED` (429)** vào `api-context.md` + `openapi.yaml`, kèm header **`Retry-After`** báo thời điểm thử lại. Additive, không breaking; cần đồng bộ mobile khi freeze #000.
- Q: Khi Redis (store đếm throttle) sự cố, throttle xử lý ra sao? → A: **fail-open cho endpoint chức năng** (`/me/*`, `/catalog/*` — không chặn user hợp lệ vì store lỗi) + log cảnh báo; **fail-closed cho `/auth/*`** (từ chối) để không mở toang brute-force khi mất phòng thủ.
- Q: `POST /auth/logout` thu hồi phạm vi token nào? → A: **Chỉ thu hồi refresh token được trình** trong request (đăng xuất per-session — thiết bị hiện tại); các thiết bị khác vẫn đăng nhập. "Logout all devices" ngoài phạm vi BE-004.
- Q: (refinement lúc plan) Catalog throttle keyed theo gì, khi `X-App-Key` là secret dùng chung toàn app? → A: **Per-IP (per-device)** — nâng nhánh "IP fallback" thành primary. Key thuần theo `X-App-Key` sẽ tạo bucket toàn cục cho mọi user (chặn nhầm cả userbase / ngưỡng vô nghĩa). Đã xác nhận lại với user ở bước plan. Xem research R1. Cập nhật FR-003.

## User Scenarios & Testing *(mandatory)*

> Ghi chú "người dùng" ở đây gồm hai nhóm: **người nghe** (được bảo vệ khỏi lạm dụng và mất an toàn tài khoản) và **người vận hành** (cần thấy lỗi production và tin rằng hệ thống chịu tải). BE-004 không thêm màn hình mới — nó làm cứng các hành vi đã có ở BE-001..BE-003.

### User Story 1 - Chống lạm dụng endpoint (Rate Limiting) (Priority: P1)

Hệ thống giới hạn tần suất gọi tới các endpoint dễ bị lạm dụng để một client (hoặc kẻ tấn công) không thể làm ngập backend hay nguồn upstream. Ưu tiên nhóm ghi dữ liệu `/me/*` (đặc biệt `POST /me/history` được gọi liên tục khi nghe nhạc), các endpoint xác thực (`/auth/login`, `/auth/register`, `/auth/social-login` — chống dò mật khẩu/spam đăng ký), và tìm kiếm catalog (bảo vệ quota Jamendo). Khi vượt hạn mức, client nhận phản hồi từ chối rõ ràng, có mã máy-đọc và tín hiệu thời điểm được thử lại; người dùng hợp lệ không bị ảnh hưởng.

**Why this priority**: Đây là bề mặt tấn công lạm dụng lớn nhất và trực tiếp nhất — spam history, brute-force đăng nhập, và đốt quota Jamendo đều có thể làm sập dịch vụ hoặc mất quyền truy cập API upstream. Là lớp phòng thủ mang lại giá trị bảo vệ cao nhất nếu chỉ làm một hạng mục.

**Independent Test**: Bắn vượt hạn mức tới từng nhóm endpoint (write `/me/*`, auth, catalog search) và xác nhận phản hồi bị từ chối đúng mã sau ngưỡng; đồng thời xác nhận lưu lượng dưới ngưỡng của người dùng hợp lệ luôn thành công. Hạn mức của user A không tiêu tốn hạn mức của user B.

**Acceptance Scenarios**:

1. **Given** một người dùng đã đăng nhập gọi `POST /me/history` vượt hạn mức cho phép trong khung thời gian, **When** vượt ngưỡng, **Then** các request tiếp theo bị từ chối với mã máy-đọc chuyên biệt (429) kèm tín hiệu thời điểm thử lại, và không tạo thêm bản ghi.
2. **Given** một client thử đăng nhập sai liên tục vào `/auth/login`, **When** vượt ngưỡng chống brute-force, **Then** các lần thử tiếp theo bị từ chối (429) trong khoảng thời gian hạ nhiệt, độc lập theo định danh client.
3. **Given** hai người dùng khác nhau, **When** user A đã chạm hạn mức của mình, **Then** user B vẫn gọi bình thường (hạn mức tính riêng theo danh tính, không dùng chung).
4. **Given** một người dùng sử dụng ở mức bình thường (nghe nhạc, ghi history theo nhịp thực tế), **When** dùng trong ngày, **Then** không bao giờ chạm giới hạn (ngưỡng đặt trên mức dùng thật).
5. **Given** hạn mức được cấu hình, **When** người vận hành cần điều chỉnh, **Then** thay đổi ngưỡng chỉ là sửa cấu hình (settings/env), không sửa logic nghiệp vụ.

---

### User Story 2 - Vòng đời token an toàn (Token Lifecycle Hardening) (Priority: P2)

Refresh token phải xoay vòng (rotation) mỗi lần dùng và token cũ bị vô hiệu hóa; đăng xuất phải thu hồi refresh token đang cầm để nó không thể lấy access token mới. Khóa ký JWT phải đủ mạnh (đạt độ dài khuyến nghị cho thuật toán đang dùng). Kết quả: một token đã bị thu hồi/xoay vòng/hết hạn không bao giờ dùng lại được để truy cập tài nguyên người dùng.

**Why this priority**: Sau chống lạm dụng, thay thế/đánh cắp token là con đường tấn công tài khoản trực tiếp nhất. Rotation + revoke biến token rò rỉ thành vô dụng sau lần dùng kế tiếp; khóa ký yếu làm sụp đổ toàn bộ mô hình tin cậy JWT. BE-001 đã bật rotation+blacklist ở mức khung — story này kiểm chứng end-to-end và bịt các lỗ còn lại.

**Independent Test**: Thực hiện chuỗi refresh và xác nhận token cũ bị chặn sau khi xoay vòng; đăng xuất rồi thử refresh bằng token đã logout → bị từ chối; token hết hạn → bị từ chối đúng mã; xác nhận khóa ký đạt độ dài tối thiểu (cấu hình chặn khởi động nếu khóa quá ngắn ở môi trường production).

**Acceptance Scenarios**:

1. **Given** một refresh token hợp lệ, **When** dùng để refresh, **Then** nhận cặp token mới và refresh token cũ bị vô hiệu — dùng lại token cũ trả `TOKEN_INVALID` (401).
2. **Given** một người dùng đã đăng nhập, **When** gọi `POST /auth/logout` với refresh token của mình, **Then** token đó bị thu hồi; mọi lần refresh sau bằng token đó trả `TOKEN_INVALID` (401).
3. **Given** một access token đã hết hạn, **When** gọi endpoint `/me/*`, **Then** nhận `TOKEN_EXPIRED` (401), không lộ dữ liệu.
4. **Given** cấu hình khóa ký JWT ngắn hơn độ dài tối thiểu khuyến nghị, **When** khởi động ứng dụng ở môi trường production, **Then** hệ thống từ chối khởi động (fail-fast) thay vì chạy với khóa yếu.
5. **Given** một refresh token bị đánh cắp và đã được nạn nhân dùng để refresh (xoay vòng), **When** kẻ tấn công dùng bản token cũ, **Then** bị từ chối (token cũ không còn hợp lệ).

---

### User Story 3 - Giám sát lỗi & quan trắc production (Observability) (Priority: P3)

Lỗi phát sinh ở production phải hiện lên hệ thống giám sát (Sentry) đủ nhanh và đủ ngữ cảnh để chẩn đoán, nhưng tuyệt đối không chứa secret hay dữ liệu nhạy cảm (mật khẩu, token, `id_token`, Jamendo `client_id`, full auth header, PII). Người vận hành thấy được sự cố upstream Jamendo (timeout/quota) như một tín hiệu quan trắc thay vì chỉ qua báo lỗi của người dùng.

**Why this priority**: Là điều kiện vận hành, không phải phòng thủ trực tiếp — nhưng thiếu nó thì mọi sự cố ở P1/P2 và lỗi upstream đều vô hình. Xếp sau khi các lớp phòng thủ đã có để giám sát chính chúng.

**Independent Test**: Kích một lỗi có kiểm soát ở môi trường staging và xác nhận nó xuất hiện trong hệ thống giám sát kèm ngữ cảnh (endpoint, mã lỗi, latency) mà không chứa bất kỳ secret/PII nào; xác nhận DSN giám sát nạp từ env (tắt được ở dev/test); xác nhận log của một luồng auth không chứa token/mật khẩu ở dạng thô.

**Acceptance Scenarios**:

1. **Given** giám sát lỗi được bật qua cấu hình env, **When** một lỗi 5xx phát sinh ở staging/production, **Then** sự cố xuất hiện trên hệ thống giám sát trong vòng chưa tới 1 phút kèm ngữ cảnh đủ để chẩn đoán.
2. **Given** một request chứa mật khẩu/token/`id_token`, **When** request được xử lý và (nếu lỗi) được ghi log/gửi giám sát, **Then** các trường nhạy cảm bị che (redact) và không xuất hiện ở dạng thô ở bất kỳ đích nào.
3. **Given** Jamendo timeout hoặc trả 429/5xx, **When** catalog dịch lỗi thành `CATALOG_UPSTREAM_ERROR`, **Then** sự cố upstream được ghi lại với ngữ cảnh (endpoint upstream, status, latency) đủ để chẩn đoán quota/timeout, không dump toàn bộ response.
4. **Given** môi trường dev/test, **When** không cấu hình DSN giám sát, **Then** ứng dụng chạy bình thường không gửi dữ liệu ra ngoài (giám sát chỉ bật khi có DSN).

---

### User Story 4 - Rà soát bảo mật & kiểm chứng chịu tải (Audit & Load Validation) (Priority: P4)

Trước khi coi là sẵn sàng production, toàn bộ bề mặt `/me/*` được rà soát theo checklist OWASP với trọng tâm IDOR (đặc biệt `/me/playlists/{id}` và tài nguyên lồng nhau), và tầng cache catalog được kiểm chứng chịu tải để xác nhận đường cache-hit phục vụ được lưu lượng cao mà không gọi thừa upstream.

**Why this priority**: Là bước "cổng nghiệm thu" tổng hợp — xác nhận ba story trước và các quyết định của BE-001..BE-003 thực sự vững dưới góc nhìn tấn công và tải. Xếp cuối vì phụ thuộc kết quả của các story trước.

**Independent Test**: Chạy bộ kiểm thử ủy quyền (cross-user) phủ mọi thao tác `/me/*` và xác nhận không có đường nào cho phép truy cập chéo; chạy kịch bản tải lên endpoint catalog đọc nhiều và đo tỷ lệ phục vụ từ cache cùng số lần gọi upstream thực tế; ghi lại kết quả rà soát OWASP thành tài liệu.

**Acceptance Scenarios**:

1. **Given** hai người dùng và đầy đủ loại tài nguyên (playlist, playlist track, liked, history), **When** user A thử mọi thao tác đọc/ghi lên tài nguyên của user B, **Then** 100% bị từ chối (`FORBIDDEN`/`NOT_FOUND` theo quy ước), không rò rỉ tồn tại hay nội dung.
2. **Given** một endpoint catalog đọc nhiều dưới tải đồng thời cao, **When** dữ liệu đã có trong cache, **Then** phần lớn request được phục vụ từ cache và số lần gọi Jamendo thực tế không tăng tuyến tính theo số request (cache chống được "thundering herd").
3. **Given** rà soát OWASP hoàn tất, **When** phát hiện bất kỳ lỗ hổng nào (IDOR, thiếu validate, header thiếu an toàn), **Then** mỗi phát hiện được ghi lại và hoặc khắc phục hoặc có lý do chấp nhận rõ ràng.
4. **Given** cấu hình production, **When** kiểm tra header bảo mật (HTTPS/HSTS, CORS allowlist thay vì `*`), **Then** các thiết lập an toàn được bật đúng theo môi trường.

---

### Edge Cases

- **Rate limit cho endpoint ẩn danh** (đã chốt, FR-002/FR-003): `/auth/*` theo IP, `/catalog/*` theo `X-App-Key` (IP fallback). Cần xử lý đúng khi ở sau reverse proxy — chỉ tin `X-Forwarded-For` khi cấu hình tường minh số hop tin cậy.
- **Vượt hạn mức nhưng request vẫn hợp lệ về nghiệp vụ**: phản hồi 429 phải theo đúng envelope lỗi chuẩn với mã `RATE_LIMITED` + header `Retry-After`, không phá vỡ định dạng lỗi mà client đã biết.
- **Đồng hồ/khung thời gian throttle**: hạn mức phải xác định trên nguồn thời gian ổn định; không được reset sai do lệch tiến trình/worker.
- **Bộ đếm throttle khi store (Redis) sự cố** (đã chốt, FR-006a): fail-open cho `/me/*` và `/catalog/*` (kèm log cảnh báo), fail-closed cho `/auth/*`.
- **Logout với refresh token đã hết hạn/không hợp lệ**: phải trả kết quả nhất quán (không lỗi 500), coi như đã ở trạng thái thu hồi.
- **Đổi khóa ký JWT (key rotation)**: token đã phát trước khi đổi khóa sẽ thành không hợp lệ — hành vi chấp nhận được nhưng phải nêu rõ khi vận hành đổi khóa.
- **Giám sát khi DSN cấu hình sai**: DSN sai không được làm sập request path của người dùng.
- **Load test không được chạm Jamendo thật**: kịch bản tải phải mock/đặt cấu hình để không đốt quota upstream thật.

## Requirements *(mandatory)*

### Functional Requirements

**Rate limiting (US1)**

- **FR-001**: Hệ thống MUST giới hạn tần suất các endpoint ghi `/me/*` theo từng người dùng, với `POST /me/history` có hạn mức riêng phù hợp nhịp phát nhạc thực tế.
- **FR-002**: Hệ thống MUST giới hạn tần suất các endpoint xác thực (`/auth/login`, `/auth/register`, `/auth/social-login`) để chống brute-force và spam, tính **theo IP** (luồng chưa đăng nhập). IP MUST được xác định an toàn khi ở sau reverse proxy — chỉ tin header proxy (`X-Forwarded-For`) khi cấu hình tường minh số hop tin cậy, KHÔNG tin mù quáng.
- **FR-003**: Hệ thống MUST giới hạn tần suất tìm kiếm/duyệt catalog dễ đốt quota upstream, tính **theo IP client (per-device)**. (`X-App-Key` là secret dùng chung toàn app nên không dùng làm bucket per-caller — xem refinement ở Clarifications & research R1; `X-App-Key` vẫn là cổng Layer-1.)
- **FR-004**: Khi vượt hạn mức, hệ thống MUST trả phản hồi từ chối theo envelope lỗi chuẩn với mã máy-đọc chuyên biệt **`RATE_LIMITED`** (HTTP 429) và header **`Retry-After`** báo thời điểm có thể thử lại. Mã `RATE_LIMITED` MUST được thêm vào catalog lỗi trong `api-context.md` + `openapi.yaml`.
- **FR-005**: Mọi ngưỡng/khung thời gian hạn mức MUST là hằng số cấu hình (settings/env), KHÔNG hardcode ở logic (Constitution VI).
- **FR-006**: Hạn mức MUST tính riêng theo danh tính (user / IP / `X-App-Key` tùy nhóm endpoint) — lưu lượng của một chủ thể MUST NOT tiêu tốn hạn mức của chủ thể khác.
- **FR-006a**: Khi store đếm throttle (Redis) sự cố, hệ thống MUST **fail-open cho endpoint chức năng** (`/me/*`, `/catalog/*` — cho request đi qua để không chặn nhầm user hợp lệ) kèm log cảnh báo, và **fail-closed cho `/auth/*`** (từ chối) để không mất phòng thủ brute-force khi Redis chết.

**Token lifecycle (US2)**

- **FR-007**: Refresh token MUST xoay vòng khi dùng; refresh token cũ sau khi xoay vòng MUST bị vô hiệu (dùng lại → `TOKEN_INVALID` 401).
- **FR-008**: `POST /auth/logout` MUST thu hồi **chỉ refresh token được trình** trong request (đăng xuất per-session — thiết bị hiện tại); sau logout, token đó MUST NOT dùng được để refresh. Refresh token của thiết bị khác của cùng user MUST vẫn hợp lệ ("logout all devices" ngoài phạm vi BE-004).
- **FR-009**: Access/refresh token hết hạn hoặc bị thu hồi MUST bị từ chối đúng mã (`TOKEN_EXPIRED`/`TOKEN_INVALID`) và MUST NOT cấp quyền truy cập tài nguyên người dùng.
- **FR-010**: Khóa ký JWT MUST đạt độ dài tối thiểu khuyến nghị cho thuật toán ký đang dùng; ở môi trường production, cấu hình khóa dưới ngưỡng MUST làm ứng dụng fail-fast khi khởi động thay vì chạy với khóa yếu.
- **FR-011**: Logout với refresh token đã hết hạn/không hợp lệ MUST trả kết quả nhất quán, không gây lỗi máy chủ (500).

**Observability (US3)**

- **FR-012**: Hệ thống MUST tích hợp giám sát lỗi (Sentry) bật/tắt qua DSN từ env; khi không có DSN (dev/test) MUST chạy bình thường và không gửi dữ liệu ra ngoài.
- **FR-013**: Trước khi ghi log hoặc gửi tới giám sát, hệ thống MUST che (redact) mọi trường nhạy cảm: mật khẩu, access/refresh token, `id_token`, Jamendo `client_id`, full `Authorization` header, và PII người dùng.
- **FR-014**: Sự cố upstream Jamendo MUST được ghi lại với ngữ cảnh đủ chẩn đoán (endpoint upstream, status, latency) mà không dump toàn bộ response.
- **FR-015**: Giám sát MUST bật PII scrubbing; DSN/khóa giám sát MUST đến từ env, KHÔNG hardcode.

**Audit & load validation (US4)**

- **FR-016**: Toàn bộ endpoint `/me/*` MUST có kiểm thử ủy quyền (cross-user) chứng minh user A không đọc/sửa/xóa được tài nguyên của user B (IDOR), gồm cả tài nguyên lồng (playlist track).
- **FR-017**: Tầng cache catalog MUST được kiểm chứng chịu tải: dưới lưu lượng đọc đồng thời cao với dữ liệu đã cache, số lần gọi Jamendo thực tế MUST NOT tăng tuyến tính theo số request (cache chống thundering herd/stampede).
- **FR-018**: Cấu hình production MUST bật các thiết lập bảo mật transport/header theo môi trường: HTTPS/HSTS, cookie an toàn (nếu dùng), và CORS theo allowlist rõ ràng (KHÔNG `*` ở production).
- **FR-019**: Kết quả rà soát OWASP MUST được ghi lại thành tài liệu; mỗi phát hiện MUST hoặc được khắc phục hoặc kèm lý do chấp nhận.

**Ràng buộc xuyên suốt (contract & config)**

- **FR-020**: Mọi thay đổi shape phản hồi/mã lỗi (ví dụ mã 429 mới) MUST cập nhật `docs/screen-inventory.md` → `contracts/openapi.yaml` + `.claude/api-context.md` TRƯỚC khi vào code, và đồng bộ version contract (Constitution II). Mã lỗi mới MUST được thêm vào catalog trong `api-context.md`.
- **FR-021**: Kiểm thử MUST NOT gọi Jamendo thật hay dịch vụ giám sát thật; upstream và giám sát MUST được mock/tắt trong bộ test (Constitution XI).

### Key Entities *(include if feature involves data)*

- **Rate limit counter/quota**: bộ đếm số request theo (định danh chủ thể × nhóm endpoint × khung thời gian), lưu ở store nhanh (Redis đã có); không phải dữ liệu người dùng lâu dài, hết hạn theo cửa sổ thời gian.
- **Refresh token record (outstanding/blacklisted)**: bản ghi vòng đời refresh token cho phép thu hồi/blacklist (đã tồn tại từ BE-001 qua SimpleJWT); story này kiểm chứng và siết chặt, không định nghĩa lại schema trừ khi phát hiện thiếu.
- **Error/monitoring event**: sự kiện lỗi gửi tới giám sát — MUST đã được che dữ liệu nhạy cảm; không lưu trong DB của backend.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Một client lạm dụng gửi vượt hạn mức tới nhóm endpoint bảo vệ nhận phản hồi từ chối (429) ngay sau khi chạm ngưỡng; trong khi đó 100% request của người dùng ở nhịp sử dụng thực tế vẫn thành công (không có false-positive throttle với hành vi bình thường).
- **SC-002**: 100% refresh token đã logout / đã xoay vòng / đã hết hạn bị từ chối khi dùng để lấy access token mới (không có trường hợp token thu hồi vẫn dùng được).
- **SC-003**: Hệ thống không khởi động ở production nếu khóa ký JWT dưới độ dài tối thiểu — kiểm chứng bằng cấu hình khóa ngắn phải làm khởi động thất bại có thông báo rõ.
- **SC-004**: Lỗi 5xx ở staging/production hiện trên hệ thống giám sát trong vòng dưới 1 phút, và 0 sự kiện giám sát/log nào chứa secret hoặc PII ở dạng thô (kiểm bằng test redaction + rà mẫu).
- **SC-005**: Dưới kịch bản tải đọc catalog đồng thời cao với dữ liệu đã cache, số lần gọi Jamendo thực tế giữ ở mức thấp gần như không đổi (không tỉ lệ thuận với số request) — chứng minh cache-hit phục vụ phần lớn tải.
- **SC-006**: Bộ kiểm thử ủy quyền tự động phủ 100% endpoint `/me/*` và tất cả pass — không có đường truy cập chéo người dùng nào tồn tại.
- **SC-007**: Toàn bộ pre-commit checklist (black/ruff/mypy/pytest/makemigrations --check) xanh; không giảm số test đang pass (baseline 104) và bổ sung test cho các hành vi mới (throttle, token revoke, redaction, IDOR sweep).

## Assumptions

- **Store throttle**: Dùng Redis đã có (BE-002) làm store đếm rate limit — không thêm hạ tầng mới (Constitution XII).
- **Định danh throttle** (đã chốt qua clarify): `/auth/*` theo IP, `/catalog/*` theo `X-App-Key` (IP fallback), `/me/*` theo user. Xem FR-002/FR-003/FR-006.
- **Hành vi throttle khi Redis sự cố** (đã chốt qua clarify): fail-open cho chức năng, fail-closed cho auth. Xem FR-006a.
- **Mã lỗi mới** (đã chốt qua clarify): `RATE_LIMITED` (HTTP 429) + header `Retry-After` — thêm vào `api-context.md` + `openapi.yaml`; additive, không breaking, cần đồng bộ contract khi freeze #000.
- **Ngưỡng hạn mức cụ thể** (con số/khung thời gian mỗi nhóm endpoint): để lại làm mặc định settings-driven ở `plan.md` — điều chỉnh chỉ là sửa cấu hình (FR-005), không đổi kiến trúc, nên không cần chốt ở tầng spec.
- **Token lifecycle phần lớn đã có**: BE-001 đã bật SimpleJWT rotation + blacklist; story US2 chủ yếu **kiểm chứng end-to-end + bịt lỗ** (đặc biệt độ dài khóa ký và hành vi logout với token không hợp lệ), không xây lại từ đầu trừ khi phát hiện thiếu.
- **Giám sát = Sentry** theo Technical Standards của constitution; DSN qua env, tắt ở dev/test.
- **Load test là công cụ kiểm chứng**, không phải endpoint sản phẩm — chạy ngoài request path, không chạm Jamendo thật (dùng cache đã nạp / client mock). Không cam kết một con số RPS tuyệt đối vì phụ thuộc phần cứng; tiêu chí là **hình dạng** (cache-hit chặn được stampede), không phải throughput cứng.
- **Không thêm màn hình / thay đổi hợp đồng dữ liệu người dùng** — BE-004 là hardening; thay đổi contract giới hạn ở mã lỗi 429 mới (và, nếu cần, header `Retry-After`).
- **Rào cản pháp lý**: không đưa tính năng thương mại nào; hardening không đụng tới ranh giới non-commercial của Jamendo (Constitution XIII).

## Dependencies

- **BE-003 User Library** (đã merge) — cung cấp toàn bộ `/me/*` là đối tượng rate limit và IDOR audit.
- **BE-002 Catalog Proxy** (đã merge) — cung cấp tầng cache Redis là đối tượng load test và endpoint catalog cần throttle.
- **BE-001 Foundation & Auth** (đã merge) — cung cấp JWT/SimpleJWT rotation+blacklist, middleware `X-App-Key`, log redaction nền tảng là đối tượng kiểm chứng/siết chặt.
- **Contract Freeze #000** — mã lỗi 429 mới là refinement pre-freeze cần xác nhận cùng repo mobile.
