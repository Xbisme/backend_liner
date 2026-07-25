# Changelog — SoundWave Backend

Định dạng theo [Keep a Changelog](https://keepachangelog.com/). Ghi lại thay
đổi đáng chú ý ở tầng repo/contract (không phải mọi commit). Contract version đi
riêng, xem `api-context.md`.

## [Unreleased]

### Added
- `.specify/memory/constitution.md` v1.0.0 — 14 nguyên tắc cốt lõi cho backend
  Django+DRF (auth 2 tầng/IDOR, contract-first, proxy Jamendo, không hardcode…).
- Scaffolding repo: `README.md`, `.gitignore`, `.env.example`.
- `.claude/dev-workflow.md` (Spec Kit + Contract Sync), `.claude/changelog.md`,
  `.claude/decisions/` (ADR).

### Changed
- Chuyển `openapi.yaml` → `contracts/openapi.yaml` và `screen-inventory.md` →
  `docs/screen-inventory.md` cho khớp layout trong `project-context.md`; sửa
  link tương ứng trong `api-context.md`.

### Status
- Chưa có spec BE-NNN nào được triển khai. Contract `v0.1.0` (draft) chờ freeze
  #000 cùng repo mobile.
