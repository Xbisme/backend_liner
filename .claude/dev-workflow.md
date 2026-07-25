# Dev Workflow — SoundWave Backend

> Quy trình Spec-Driven Development (Spec Kit) + Contract Sync giữa hai repo.
> Đọc cùng [`sdd-roadmap.md`](sdd-roadmap.md) và
> [`../.specify/memory/constitution.md`](../.specify/memory/constitution.md).
>
> Last updated: 2026-07-25

## 1. Vòng đời một spec (BE-NNN)

Mỗi tính năng đi qua các bước Spec Kit theo đúng thứ tự:

| Bước | Skill | Kết quả |
|---|---|---|
| 1. Chốt nguyên tắc | `/speckit-constitution` | `.specify/memory/constitution.md` (đã có v1.0.0) |
| 2. Viết spec | `/speckit-specify` | `specs/BE-NNN-*/spec.md` |
| 3. Làm rõ | `/speckit-clarify` | cập nhật `spec.md` |
| 4. Lập kế hoạch | `/speckit-plan` | `plan.md` + artifacts thiết kế |
| 5. Chia task | `/speckit-tasks` | `tasks.md` (dependency-ordered) |
| 6. Kiểm tra chéo | `/speckit-analyze` | báo cáo nhất quán spec/plan/tasks |
| 7. Triển khai | `/speckit-implement` | code + test |

Nhánh làm việc: `BE-NNN-<slug>` (xem tên nhánh trong `sdd-roadmap.md`).

## 2. Contract-First (bắt buộc)

Thứ tự sửa đổi API **không được đảo**:

```
docs/screen-inventory.md   →   contracts/openapi.yaml + .claude/api-context.md   →   code
```

- Không đổi shape request/response trong code trước khi cập nhật contract.
- Serializer là tầng thực thi contract — response phải khớp `openapi.yaml`.
- Error code mới → thêm vào catalog trong `api-context.md` (và contract).

## 3. Contract Sync (giữa 2 repo)

`docs/screen-inventory.md`, `contracts/openapi.yaml`, `.claude/api-context.md`
tồn tại ở **cả** `soundwave-backend` và `soundwave-mobile`, đồng bộ **thủ công**.

Khi thay đổi contract:

1. Cập nhật cả 3 file ở repo backend trong **cùng** một change.
2. Nếu là **breaking change** (xóa/đổi tên field, đổi type, thêm field bắt buộc):
   - Bump `Contract version` (semver) trong 3 file.
   - Báo repo mobile và copy 3 file sang trước khi merge.
   - Ghi lại ở `changelog.md` + tạo ADR trong `decisions/` nếu là quyết định lớn.
3. Điểm đồng bộ đã biết (xem `sdd-roadmap.md`):
   - **BE-002 Catalog Proxy** → mobile chuyển từ mock sang API thật (MO-002).
   - **BE-005 Deploy** → báo mobile khi production sẵn sàng (MO-005).

## 4. Pre-commit checklist (bắt buộc)

```bash
black .                        # format, zero diff
ruff check .                   # lint, zero error
mypy .                         # type check, zero error
pytest                         # test pass (Jamendo được mock)
python manage.py makemigrations --check --dry-run   # không thiếu migration
```

## 5. Definition of Done cho một task

- [ ] Code + test (unit/service + API + IDOR nếu chạm `/me/*`).
- [ ] Contract cập nhật nếu shape đổi (3 file + version).
- [ ] Pre-commit checklist xanh.
- [ ] Không hardcode secret/URL/TTL — tất cả qua settings/env.
- [ ] `changelog.md` cập nhật; ADR nếu là quyết định kiến trúc.

## 6. Ghi quyết định (ADR)

Quyết định kiến trúc/contract lớn → thêm file vào [`decisions/`](decisions/)
theo mẫu `NNNN-tieu-de.md`. Xem [`decisions/README.md`](decisions/README.md).
