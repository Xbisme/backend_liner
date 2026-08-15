# Contract Requests — MO-003 Library (mobile → backend)

> Gửi từ `flutter_liner` sang `soundwave-backend`, 2026-08-16.
> Đối chiếu với contract **v0.3.0** + code backend `main` @ `755e764` (sau BE-004).
> Quy trình: [`dev-workflow.md`](dev-workflow.md) §2 — screen-inventory → openapi
> → api-context → regenerate client → `AppFailure`.

## 0. Kết luận check conflict

Mobile chuẩn bị vào **MO-003 Library** (playlists CRUD + reorder drag & drop,
Liked Songs với like ghi thật, History). Đã đối chiếu 3 quyết định thiết kế phía
mobile với contract v0.3.0 **và đọc thẳng code backend**:

> **Không có mâu thuẫn thiết kế nào.** Cả 3 quyết định chạy được trên backend
> hiện tại. Có **1 va chạm số hiệu version** (mục 1), **4 hành vi đã xác minh
> nhưng contract không ghi** (mục 2), và **3 yêu cầu thật** (mục 3) + **1 bug**
> (mục 4).

| Quyết định mobile | Đối chiếu code backend | Kết luận |
|---|---|---|
| #1 History có `played_at` | `HistoryView.get` chỉ serialize `TrackSerializer` — **vứt bỏ** `played_at` dù row `ListeningHistory` có sẵn và queryset đã `order_by("-played_at")` | ⚠️ Cần R1 |
| #2 Playlist không phân trang + trần 500 track | `PlaylistDetailView.get` **không** paginate, trả full `ordered_track_ids()`; `LIBRARY_PAGE_SIZE_MAX=50` chỉ áp cho 3 list endpoint | ✅ An toàn — nhưng trần 500 **chưa tồn tại**, xem R2 |
| #3 Empty state khi chưa login | Thuần client | ✅ Không đụng backend |

## 1. Va chạm duy nhất: số hiệu version

Mobile đã chốt (trước khi thấy bản sync v0.3.0) sẽ bump contract lên `v0.3.0` để
thêm `HistoryEntry`. BE-004 đã chiếm `v0.3.0` cho rate limiting → yêu cầu này
chuyển thành **`v0.4.0`**. Không tranh chấp nội dung, chỉ đổi nhãn.

## 2. Bốn hành vi đã xác minh từ code — xin ghi vào contract

Mobile đã tự trả lời bằng cách đọc code, **không cần backend phản hồi**. Nhưng cả
bốn đều **không được ghi ở `openapi.yaml`/`api-context.md`**, nên client thứ hai
(hoặc chính mình sau 3 tháng) sẽ đoán sai. Xin bổ sung vào tài liệu:

**(a) Tombstone NẰM TRONG `PlaylistDetail.tracks`** — `_detail_payload` gọi
`ordered_track_ids()` (toàn bộ rows) → `get_tracks_by_ids()`, mà hàm này "order
matches ids; an id the upstream cannot resolve becomes a tombstone". Nên
`len(tracks)` luôn = số `PlaylistTrack`, tombstone giữ nguyên vị trí, và
`track_count = len(tracks)` **đã bao gồm** tombstone.

**(b) `reorder` BẮT BUỘC gồm cả id tombstone** — `playlists.reorder()` so
`sorted(track_ids)` với `sorted(pt.track_id for pt in rows)`, **không lọc theo
`available`**. Hệ quả trực tiếp lên UI: mobile **không được ẩn** tombstone khỏi
màn Playlist Detail, vì ẩn đi là payload thiếu id → `REORDER_MISMATCH` 400.
Đây là ràng buộc UI quan trọng nhất rút ra từ đợt check này — mobile sẽ render
tombstone thành row "Track không còn khả dụng" (disable play, vẫn kéo-thả được).
Xin ghi rõ vào mô tả `ReorderPlaylistRequest.track_ids`.

**(c) `DELETE .../tracks/{track_id}` xóa được tombstone** — `remove_track` filter
trên `PlaylistTrack`, không đụng catalog; track vắng mặt → no-op 204 (idempotent).
Tốt: người dùng có đường dọn track chết. Xin ghi tính idempotent vào contract.

**(d) `Retry-After` KHÔNG phải lúc nào cũng có** — `core/exceptions.py` chỉ set
header khi `Throttled.wait` khác `None`; có test khẳng định điều ngược lại
(`test_throttled_without_wait_has_no_retry_after`). Mobile sẽ dùng backoff mặc
định khi thiếu header. Xin ghi "optional" vào mục Rate limiting của
`api-context.md` thay vì để client tưởng luôn có.

## 3. Ba yêu cầu thật

### R1 — `GET /me/history` trả `played_at` (bump `v0.4.0`)

**Hiện trạng**: `HistoryView.get` hydrate track rồi trả `TrackCursorPage`, **bỏ
mất `played_at`** — dù `ListeningHistory` đã lưu sẵn và `HistoryCursorPage`
đã `order_by("-played_at", "-id")`. `api-context.md` ghi "sắp theo `played_at`
giảm dần" nhưng field đó không hề tới client.

**Vấn đề**: màn History (#10) không hiện được thời điểm nghe, không group được
"Hôm nay / Hôm qua / Tuần này" — kỳ vọng mặc định ở màn lịch sử nghe.

**Chi phí thấp**: dữ liệu đã có trong DB và đã được sort đúng; chỉ là tầng
serializer không expose. Không cần đổi model, không cần đổi logic ghi.

```yaml
HistoryEntry:
  type: object
  required: [track, played_at]
  properties:
    track: { $ref: '#/components/schemas/Track' }
    played_at: { type: string, format: date-time }
    completed: { type: boolean, default: false }

HistoryCursorPage:
  type: object
  properties:
    items:
      type: array
      items: { $ref: '#/components/schemas/HistoryEntry' }
    next_cursor: { type: string, nullable: true }
    has_more: { type: boolean }
```

`GET /me/history` đổi response `TrackCursorPage` → `HistoryCursorPage`. Breaking
change, nhưng mobile **chưa build màn History** nên chi phí phía client = 0 nếu
làm ngay trong BE-005.

**Thuận lợi**: BE-003 đã đổi `POST /me/history` sang **upsert distinct** (một
`track_id` một dòng). Nhờ vậy mỗi `HistoryEntry` map 1:1 với một dòng DB, không
phát sinh trùng lặp — schema trên khớp tự nhiên với mô hình đã có.

### R2 — Trần số track/playlist (hiện **không có giới hạn nào**)

`playlists.add_track()` chỉ kiểm tra trùng (`TRACK_ALREADY_IN_PLAYLIST`), **không
có cap**. `config/settings/base.py` chỉ có `PLAYLIST_NAME_MAX_LENGTH=200`, không
có `PLAYLIST_MAX_TRACKS`.

Rủi ro cụ thể: `GET /me/playlists/{id}` không phân trang (đúng như mobile muốn),
nên một playlist 5.000 bài sẽ hydrate 5.000 track trong **một** response — và
`reorder` sẽ phải gửi ngần ấy id. Mobile chấp nhận đánh đổi này với điều kiện có
trần rõ ràng.

**Đề xuất**: `PLAYLIST_MAX_TRACKS` (env-driven như các ngưỡng BE-004), **mặc định
500**; `add_track` vượt trần → mã lỗi mới **`PLAYLIST_FULL` (409)** trong Error
Code Catalog. Nếu backend muốn tái dùng `VALIDATION_ERROR` 400 cũng được, nhưng
mobile cần code riêng để hiện đúng "Playlist đã đầy (tối đa 500 bài)".

### R3 — Đưa `HISTORY_MAX_ENTRIES` vào tài liệu

Code đang là **100** (`env.int("HISTORY_MAX_ENTRIES", default=100)`), `_trim()`
cắt sau mỗi lần ghi. Mobile cần con số này để biết màn History hữu hạn (~2–5
trang với page size 20–50) và không dựng infinite scroll vô hạn. Xin ghi vào
`api-context.md` mục `GET /me/history`.

## 4. Một bug phát hiện khi đọc code

**`PATCH /me/playlists/{id}` (rename) luôn trả `cover_url: null`.**

`PlaylistDetailView.patch` gọi `summary_dict(playlist, track_count=track_count,
cover_url=None)` — hardcode `None`, trong khi `GET /me/playlists` tính cover thật
từ 4 track đầu. Contract mô tả `cover_url` là "ghép từ cover 4 track đầu, null
nếu playlist rỗng", nên với playlist **không rỗng** thì response PATCH đang **sai
contract**.

Test hiện có không bắt được: `test_rename_and_delete` chỉ assert `name`, còn
assert `cover_url is None` duy nhất nằm ở playlist vừa tạo (rỗng — đúng kỳ vọng).

Tác động phía mobile: sau khi đổi tên, nếu client cập nhật state danh sách từ
response PATCH thì ảnh bìa sẽ biến mất cho tới lần refetch kế. Mobile sẽ tạm né
bằng cách refetch, nhưng nên sửa ở backend cho đúng contract.

## 5. Ràng buộc mobile tự xử (backend không cần làm gì)

Ghi ra đây để backend khỏi phải nới ngưỡng throttle:

- Ngưỡng ghi `/me/*` 60/min/user áp cho cả **toggle like** lẫn **reorder**
  (`WriteThrottleMixin` chỉ throttle method ghi — đọc không bị chặn, đã xác minh).
  Mobile sẽ debounce/coalesce toggle like, và chỉ gọi `reorder` **một lần khi
  thả**, không gọi theo từng bước kéo.
- Like dùng optimistic update; gặp 429 hoặc lỗi thì **rollback** trạng thái icon
  — không có hàng đợi ghi trễ (constitution mobile cấm offline).
- Tombstone ở Liked Songs / History: hiển thị là mục không khả dụng, **không đưa
  vào queue phát** (`stream_url` null).
- Regenerate Dart client theo v0.3.0; mapper nhận `Track` metadata nullable;
  `User.email` nullable ở Settings; page size ≤50; thêm `RATE_LIMITED` vào
  `AppFailure` + i18n en/vi.

## 6. Cần backend phản hồi

**Không có gì chặn mobile chạy `speckit-plan` MO-003** — Q1/Q2/Q4 của bản nháp
trước đã tự trả lời bằng code. Cụ thể:

- **R2** (`PLAYLIST_FULL`) nên làm sớm nhất: mobile sẽ code trần 500 ở client
  ngay, nhưng nếu backend không validate thì trần chỉ là gợi ý, client khác vượt
  được.
- **R1** (`HistoryEntry`) chặn riêng phần màn History. Nếu backend chưa xếp được
  slot, mobile tách History thành user story **cuối** của MO-003 để phần còn lại
  chạy trước — báo lại sớm để mobile xếp thứ tự task.
- **Mục 2 (a–d)** và **R3** chỉ là cập nhật tài liệu, không đổi code.
- **Mục 4** là bug độc lập, mobile không bị chặn.
