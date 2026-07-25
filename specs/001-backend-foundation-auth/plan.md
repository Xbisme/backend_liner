# Implementation Plan: Backend Foundation & Auth

**Branch**: `BE-001-backend-foundation-auth` | **Date**: 2026-07-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-backend-foundation-auth/spec.md`

## Summary

Stand up the Django + DRF service skeleton and the full user-authentication
system for SoundWave: an `X-App-Key` gate on every request, real user accounts
(email/password + Google/Apple social sign-in with account auto-linking and
optional email), a short-lived-access / rotating-revocable-refresh JWT model, and
the account profile + deletion endpoints. Delivers the shared foundation
(settings split, error envelope, cursor pagination base) every later spec builds
on. Catalog/library are out of scope. See [research.md](research.md) for the
technical decisions and pinned dependency versions.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies** (latest stable per PyPI 2026-07-25 — [research.md](research.md)):
Django 5.2.16 (LTS) · djangorestframework 3.17.1 · djangorestframework-simplejwt
5.5.1 (+ `token_blacklist`) · google-auth 2.56.2 · PyJWT 2.13.0 + cryptography
49.0.0 (Apple) · django-environ 0.14.0 · argon2-cffi 25.1.0 · psycopg[binary]
3.3.4 · redis 8.0.1 + django-redis 7.0.0

**Storage**: PostgreSQL (primary) · Redis (cache/foundation; not functionally
required by auth)

**Testing**: pytest 9.1.1 + pytest-django 4.12.0 + factory-boy 3.3.3 +
pytest-cov 7.1.0; Google/Apple verification mocked (no live network)

**Target Platform**: Linux server (containerized), consumed by the Flutter
`soundwave-mobile` app

**Project Type**: Web service (REST API backend)

**Performance Goals**: Standard API latency (auth endpoints p95 < ~300 ms
excluding external provider round-trips); no special throughput target in BE-001
(rate limiting is BE-004)

**Constraints**: Contract-first — responses must match `contracts/openapi.yaml`;
no hardcoded secrets/tunables (all via env); no secrets in logs; authorization
derived from token, never client-supplied ids

**Scale/Scope**: 7 endpoints, 2 new models (User, SocialIdentity) + SimpleJWT
blacklist tables, 1 app (`accounts`) + `core/` + `config/`. Foundation for
BE-002..005.

## Constitution Check

*GATE: evaluated against `.specify/memory/constitution.md` v1.0.0.*

| Principle | Relevance to BE-001 | Compliance in this plan |
|---|---|---|
| I. Two-Tier Auth & Access Control | Core of the feature | `X-App-Key` middleware (constant-time) + SimpleJWT Bearer on `/me`+logout; `GET/DELETE /me` scoped to `request.user`; client `user_id` never trusted (FR-017) ✅ |
| II. Contract-First API | All endpoints | Serializers enforce `openapi.yaml` shapes; contract-test checklist in `contracts/auth-endpoints.md`; email-nullable refined in contract pre-freeze ✅ |
| III. Layered App Architecture | Structure | `accounts` app with views/serializers/services split; auth/social logic in `services/`; shared code in `core/` ✅ |
| IV. Catalog Proxy & Cache | N/A here | No Jamendo in BE-001 (BE-002) — Redis wired as foundation only ✅ |
| V. Consistent Error Handling | All endpoints | Single `core.exceptions.api_exception_handler` + `core.errors.ErrorCode` catalog → `{error:{code,message}}` ✅ |
| VI. Config & Secrets Hygiene | Settings | `django-environ` split settings; token lifetimes/app-key/provider creds/DB/Redis all env-driven; `.env.example` present ✅ |
| VII. Data Integrity & Migrations | Models | Custom `AUTH_USER_MODEL` set in first migration; non-destructive; `DELETE /me` cascades ✅ |
| VIII. Security Hardening | Partial | Argon2id hashing, refresh rotation+blacklist, constant-time app-key, boundary validation. Rate limiting deferred → BE-004 (documented) ✅ |
| IX. Observability | Cross-cutting | Structured logging config in base settings; redaction of secrets/tokens; Sentry via env DSN ✅ |
| X. Code Quality & Typing | All code | black + ruff + mypy (django-stubs/drf-stubs) zero-warning gate ✅ |
| XI. Testing Discipline | All code | pytest APIClient contract tests, auth/IDOR/token-lifecycle tests, providers mocked ✅ |
| XII. Simplicity & YAGNI | Scope | SimpleJWT over hand-rolled JWT / allauth; no password-reset/MFA/avatar in v1 ✅ |
| XIII. Legal & Licensing | N/A here | No Jamendo/monetization surface in BE-001 ✅ |
| XIV. Dependency Hygiene | Deps | All versions looked up on PyPI, pinned; PyJWT-over-python-jose deviation documented with rationale ✅ |

**Result**: PASS — no violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-backend-foundation-auth/
├── plan.md              # This file
├── spec.md              # Feature spec (+ Clarifications)
├── research.md          # Phase 0 — decisions + pinned versions
├── data-model.md        # Phase 1 — User, SocialIdentity, token state
├── quickstart.md        # Phase 1 — run/validate guide
├── contracts/
│   └── auth-endpoints.md # Phase 1 — contract-test checklist (refs openapi.yaml)
└── checklists/
    └── requirements.md   # Spec quality checklist (from /speckit-specify)
```

### Source Code (repository root)

```text
config/
├── __init__.py
├── settings/
│   ├── __init__.py
│   ├── base.py           # env-driven: apps, DRF, SimpleJWT, DB, cache, logging, PASSWORD_HASHERS
│   ├── dev.py
│   ├── staging.py
│   └── production.py
├── urls.py               # /auth/* + /me routes; admin; health
├── wsgi.py
└── asgi.py

core/
├── __init__.py
├── errors.py             # ErrorCode constants + code→(status,message) map
├── exceptions.py         # AppError + api_exception_handler (DRF EXCEPTION_HANDLER)
├── middleware.py         # AppKeyMiddleware (X-App-Key gate)
├── authentication.py     # JWTAuthentication subclass → typed expired/invalid errors
├── pagination.py         # CursorPage base (foundation for BE-002/003 lists)
└── renderers.py          # (optional) ensure error envelope consistency

apps/
└── accounts/
    ├── __init__.py
    ├── apps.py
    ├── models.py         # User, SocialIdentity
    ├── managers.py       # UserManager (email normalize, social create)
    ├── serializers.py    # Register/Login/SocialLogin/Refresh + User, AuthTokenResponse
    ├── services/
    │   ├── __init__.py
    │   ├── tokens.py     # issue/refresh/rotate/revoke via SimpleJWT
    │   └── social.py     # verify_google() / verify_apple() + resolve/link account
    ├── views.py          # auth endpoints + /me (thin)
    ├── urls.py
    ├── migrations/
    └── tests/
        ├── conftest.py / factories.py
        ├── test_app_key.py
        ├── test_register_login.py
        ├── test_tokens.py        # refresh rotation, expiry, logout
        ├── test_social_login.py  # google/apple mocked, link, no-email
        └── test_me.py            # profile, delete, IDOR

requirements/
├── base.txt
├── dev.txt               # base + black/ruff/mypy/pytest/stubs
└── production.txt         # base + gunicorn/sentry

manage.py
pytest.ini / pyproject.toml   # tool config (black, ruff, mypy, pytest-django)
```

**Structure Decision**: Single Django web-service project (constitution's target
layout). Domain logic in the `accounts` app; cross-cutting concerns (error
envelope, app-key gate, JWT auth override, pagination) in `core/` so BE-002/003
reuse them without duplication. `config/settings/` is the env-driven split.

## Complexity Tracking

No constitution violations — section intentionally empty.

## Phase notes / handoff to /speckit-tasks

- Foundation tasks (settings split, `core/` error+middleware+auth, custom User
  model + first migration) are prerequisites and block everything else.
- Then per user story (P1→P3): US1 register/login+`GET /me` → US2 refresh/logout
  → US3 social → US4 delete. Each story is independently testable per spec.
- Every endpoint task pairs with contract/behavior tests from
  `contracts/auth-endpoints.md`.
- Redis/cache config is foundation-only; no auth behavior depends on it.
