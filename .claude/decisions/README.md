# Architecture Decision Records (ADR)

Ghi lại các **quyết định kiến trúc/contract** quan trọng và lý do. Mỗi quyết
định là một file `NNNN-tieu-de-ngan.md` (số tăng dần), không sửa file cũ — nếu
đổi ý thì tạo ADR mới và đánh dấu ADR cũ là `Superseded`.

## Khi nào viết ADR

- Chọn/đổi kiến trúc lớn (vd: proxy Jamendo thay vì mobile gọi thẳng).
- Breaking change ở contract (`openapi.yaml`).
- Đánh đổi có hệ quả dài hạn (cache strategy, auth model, DB schema lớn).

## Mẫu

```markdown
# NNNN. <Tiêu đề quyết định>

- **Status**: Proposed | Accepted | Superseded by [NNNN](NNNN-....md)
- **Date**: YYYY-MM-DD
- **Liên quan**: spec BE-NNN / contract vX.Y.Z

## Context
Bối cảnh, ràng buộc dẫn tới quyết định.

## Decision
Quyết định cụ thể.

## Consequences
Hệ quả tích cực/tiêu cực, việc phải làm tiếp.
```

## Danh sách

- [0001. Backend proxy + cache Jamendo](0001-backend-proxy-cache-jamendo.md)
