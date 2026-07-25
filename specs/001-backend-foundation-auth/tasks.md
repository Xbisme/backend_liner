---
description: "Task list for BE-001 Backend Foundation & Auth"
---

# Tasks: Backend Foundation & Auth

**Input**: Design documents from `specs/001-backend-foundation-auth/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/auth-endpoints.md

**Tests**: INCLUDED — the spec explicitly requests tests (auth flows, token
expiry/revocation, X-App-Key, IDOR) and Constitution Principle XI mandates them.

**Organization**: Grouped by user story (US1→US4, priority order) so each story
is an independently testable increment. Paths follow plan.md structure
(`config/`, `core/`, `apps/accounts/`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1..US4 (setup/foundational/polish carry no story label)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton, dependencies, tooling.

- [x] T001 Create source tree per plan.md: `config/`, `config/settings/`, `core/`, `apps/accounts/{services,migrations,tests}/`, `requirements/`, and `manage.py` (empty `__init__.py` in each package)
- [x] T002 Pin dependencies from research.md into `requirements/base.txt` (Django==5.2.16, djangorestframework==3.17.1, djangorestframework-simplejwt==5.5.1, google-auth==2.56.2, PyJWT==2.13.0, cryptography==49.0.0, django-environ==0.14.0, argon2-cffi==25.1.0, "psycopg[binary]"==3.3.4, redis==8.0.1, django-redis==7.0.0), `requirements/dev.txt` (base + pytest==9.1.1, pytest-django==4.12.0, factory-boy==3.3.3, pytest-cov==7.1.0, black==26.5.1, ruff==0.16.0, mypy==2.3.0, django-stubs==6.0.7, djangorestframework-stubs==3.17.0), `requirements/production.txt` (base + gunicorn, sentry-sdk)
- [x] T003 [P] Configure tooling in `pyproject.toml` (black, ruff, mypy + django-stubs/drf-stubs plugin) and `pytest.ini` (DJANGO_SETTINGS_MODULE=config.settings.dev, test paths)
- [x] T004 [P] Django bootstrap: `manage.py`, `config/wsgi.py`, `config/asgi.py` pointing at `config.settings`

**Checkpoint**: `python -c "import django"` works; tooling configured.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Env-driven settings, the `core/` cross-cutting layer, and the custom
User model + first migration. **⚠️ No user story can start until this is done.**

- [x] T005 Implement `config/settings/base.py` (django-environ): `INSTALLED_APPS` (rest_framework, rest_framework_simplejwt.token_blacklist, apps.accounts), `AUTH_USER_MODEL="accounts.User"`, DB via `env.db(DATABASE_URL)` (psycopg3), `CACHES` via `REDIS_URL` (django-redis), `PASSWORD_HASHERS` with Argon2 first, `REST_FRAMEWORK` (DEFAULT_AUTHENTICATION=core JWT class, EXCEPTION_HANDLER=core handler, DEFAULT_PAGINATION=core CursorPage), `SIMPLE_JWT` (ACCESS/REFRESH lifetimes from env, `ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=True`), `MIDDLEWARE` incl. AppKeyMiddleware, structured `LOGGING` with secret/token redaction, `X_APP_KEY`/provider creds/CORS from env
- [x] T006 [P] Implement `config/settings/dev.py`, `staging.py`, `production.py` (import base; env-specific DEBUG, ALLOWED_HOSTS, HTTPS/HSTS/secure cookies in production, Sentry DSN)
- [x] T007 [P] Implement `core/errors.py`: `ErrorCode` constants for the full catalog (INVALID_APP_KEY, UNAUTHORIZED_USER, TOKEN_EXPIRED, TOKEN_INVALID, FORBIDDEN, EMAIL_ALREADY_EXISTS, INVALID_CREDENTIALS, SOCIAL_TOKEN_INVALID, VALIDATION_ERROR, NOT_FOUND, …) + `ERROR_MAP: code → (http_status, default_message)`
- [x] T008 Implement `core/exceptions.py`: `AppError(code)` exception + `api_exception_handler` rendering `{"error":{"code","message"}}`, mapping DRF `ValidationError`→VALIDATION_ERROR, `NotFound`→NOT_FOUND, `PermissionDenied`→FORBIDDEN, `NotAuthenticated`→UNAUTHORIZED_USER (depends on T007)
- [x] T009 [P] Implement `core/middleware.py` `AppKeyMiddleware`: constant-time (`hmac.compare_digest`) compare of `X-App-Key` to `settings.X_APP_KEY`; on fail return 401 error-envelope; settings-driven path allowlist for `/admin/`, health, schema (depends on T007)
- [x] T010 [P] Implement `core/authentication.py`: subclass SimpleJWT `JWTAuthentication` to raise typed errors so the handler emits TOKEN_EXPIRED vs TOKEN_INVALID vs UNAUTHORIZED_USER (depends on T007, T008)
- [x] T011 [P] Implement `core/pagination.py` `CursorPage` base returning `{items,next_cursor,has_more}` (foundation for BE-002/003; not used by auth)
- [x] T012 [P] Implement `apps/accounts/managers.py` `UserManager` (`create_user` allowing `email=None`, `create_superuser`, email normalization)
- [x] T013 Implement `apps/accounts/models.py`: `User(AbstractBaseUser, PermissionsMixin)` (integer pk, email unique+nullable, display_name, USERNAME_FIELD=email, REQUIRED_FIELDS=[display_name]) and `SocialIdentity` (FK user CASCADE, provider choices, subject_id, email_at_provider, UniqueConstraint(provider,subject_id)) (depends on T012)
- [x] T014 Generate initial migration `apps/accounts/migrations/0001_initial.py` via `makemigrations accounts`; verify it creates User + SocialIdentity (depends on T013)
- [x] T015 [P] Implement `config/urls.py`: `/admin/`, a health endpoint, and `include("apps.accounts.urls")`; create empty `apps/accounts/urls.py` urlpatterns list
- [x] T016 [P] Test infra: `apps/accounts/tests/conftest.py` (app-key header fixture, APIClient) and `apps/accounts/tests/factories.py` (UserFactory, SocialIdentityFactory)

**Checkpoint**: `python manage.py migrate` succeeds; app-key gate active; error
envelope + JWT auth wired. User stories can now begin.

---

## Phase 3: User Story 1 — Create account and sign in with email (Priority: P1) 🎯 MVP

**Goal**: Register + login with email/password, receive tokens, view own profile;
every request gated by X-App-Key.

**Independent Test**: Register a fresh email → get tokens+user; GET /me with the
access token returns that profile; login again works; bad password → 401.

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL)

- [x] T017 [P] [US1] `apps/accounts/tests/test_app_key.py`: any endpoint without/with wrong `X-App-Key` → 401 INVALID_APP_KEY (before body processing)
- [x] T018 [P] [US1] `apps/accounts/tests/test_register_login.py`: register 201 shape=AuthTokenResponse; duplicate email (case-insensitive) → 409 EMAIL_ALREADY_EXISTS; short password/bad email → 400 VALIDATION_ERROR; login 200; wrong password AND unknown email → identical 401 INVALID_CREDENTIALS
- [x] T019 [P] [US1] `apps/accounts/tests/test_me.py`: GET /me with valid access → 200 User (no password/is_staff; auth_provider="email", email present); missing token → 401 UNAUTHORIZED_USER

### Implementation for User Story 1

- [x] T020 [P] [US1] `apps/accounts/serializers.py`: `RegisterSerializer` (email, password min 8, display_name; uniqueness→EMAIL_ALREADY_EXISTS), `LoginSerializer`, `UserSerializer` (contract `User` shape incl. derived `auth_provider`, `avatar_url=None`), `AuthTokenResponseSerializer`
- [x] T021 [US1] `apps/accounts/services/tokens.py`: `issue_tokens(user) → {access, refresh, expires_in}` using SimpleJWT (expires_in from ACCESS lifetime)
- [x] T022 [US1] `apps/accounts/views.py`: `RegisterView` (201), `LoginView` (200, INVALID_CREDENTIALS), `MeView.get` (200) — thin, delegate to serializers/services (depends on T020, T021)
- [x] T023 [US1] `apps/accounts/urls.py`: wire `POST /auth/register`, `POST /auth/login`, `GET /me`
- [x] T024 [US1] Ensure all US1 responses/errors use the core envelope + Argon2 hashing path; run T017–T019 green

**Checkpoint**: US1 fully functional and independently testable (MVP).

---

## Phase 4: User Story 2 — Stay signed in and sign out securely (Priority: P2)

**Goal**: Refresh access tokens via rotating refresh token; logout revokes the
session.

**Independent Test**: Refresh returns new tokens; reused old refresh → 401
TOKEN_INVALID; expired access → 401 TOKEN_EXPIRED; after logout refresh → 401.

### Tests for User Story 2 ⚠️

- [x] T025 [P] [US2] `apps/accounts/tests/test_tokens.py`: refresh 200 new set; reuse rotated refresh → 401 TOKEN_INVALID; expired access on /me → 401 TOKEN_EXPIRED; garbage token → 401 TOKEN_INVALID; logout → 204 then that refresh → 401 TOKEN_INVALID

### Implementation for User Story 2

- [x] T026 [P] [US2] `apps/accounts/serializers.py`: add `RefreshSerializer` (refresh_token)
- [x] T027 [US2] `apps/accounts/services/tokens.py`: add `refresh_tokens(refresh)` (rotate, map errors→TOKEN_INVALID) and `revoke(refresh)` (blacklist)
- [x] T028 [US2] `apps/accounts/views.py`: `RefreshView` (200/401 TOKEN_INVALID), `LogoutView` (Bearer, 204, revoke presented refresh) (depends on T027)
- [x] T029 [US2] `apps/accounts/urls.py`: wire `POST /auth/refresh`, `POST /auth/logout`; run T025 green

**Checkpoint**: US1 + US2 both work independently.

---

## Phase 5: User Story 3 — Sign in with Google or Apple (Priority: P3)

**Goal**: Verify Google/Apple identity tokens server-side; create-or-reuse
account keyed by (provider, subject_id); auto-link by verified email; support
no-email accounts.

**Independent Test**: valid Google/Apple token → 200 (first=create, repeat=reuse,
no dup); email match → auto-link; no-email → account with null email; invalid
token → 400 SOCIAL_TOKEN_INVALID.

### Tests for User Story 3 ⚠️

- [x] T030 [P] [US3] `apps/accounts/tests/test_social_login.py` (provider verify mocked, no live network): google new→create; same subject_id→reuse; apple no-email→null email account; verified email matching existing account→auto-link (no dup); invalid/expired token→400 SOCIAL_TOKEN_INVALID; provider outside {google,apple} or missing id_token→400 VALIDATION_ERROR (not SOCIAL_TOKEN_INVALID)

### Implementation for User Story 3

- [x] T031 [P] [US3] `apps/accounts/services/social.py`: `verify_google(id_token)` (google-auth) and `verify_apple(id_token)` (PyJWT + PyJWKClient) → normalized `{provider, subject_id, email?}`; raise AppError(SOCIAL_TOKEN_INVALID) on any token-verification failure (note: malformed `provider`/missing `id_token` is caught earlier by the serializer → VALIDATION_ERROR, not here)
- [x] T032 [US3] `apps/accounts/services/social.py`: `resolve_or_create_account(verified)` implementing the 3-step linking rule from data-model.md (identity → email auto-link → create) (depends on T031, T013)
- [x] T033 [P] [US3] `apps/accounts/serializers.py`: add `SocialLoginSerializer` (provider enum, id_token)
- [x] T034 [US3] `apps/accounts/views.py`: `SocialLoginView` (200, delegate to social service + issue_tokens) (depends on T032, T021)
- [x] T035 [US3] `apps/accounts/urls.py`: wire `POST /auth/social-login`; run T030 green

**Checkpoint**: US1–US3 independently functional.

---

## Phase 6: User Story 4 — Delete my account (Priority: P3)

**Goal**: Authenticated user deletes own account; all owned data cascades; tokens
and credentials stop working.

**Independent Test**: DELETE /me → 204; afterwards old access token → 401 and old
credentials can't log in; SocialIdentity rows removed.

### Tests for User Story 4 ⚠️

- [x] T036 [P] [US4] Extend `apps/accounts/tests/test_me.py`: DELETE /me → 204; old access token → 401; login with old credentials fails; SocialIdentity/related rows gone (cascade)

### Implementation for User Story 4

- [x] T037 [US4] `apps/accounts/views.py`: add `MeView.delete` (204) deleting `request.user` (cascade via FK) — authorization strictly from token (FR-017)
- [x] T038 [US4] Confirm `DELETE /me` route in `apps/accounts/urls.py`; run T036 green

**Checkpoint**: All user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T039 [P] Verify structured logging redacts app-key/passwords/tokens across all flows (Principle IX / SC-006) — add a test asserting no secret in captured logs
- [x] T040 [P] Confirm no IDOR / client-supplied id trust anywhere in `/me` (add explicit cross-account test: user B token cannot read/delete user A) 
- [x] T041 Run full gate: `black --check . && ruff check . && mypy . && pytest` and `python manage.py makemigrations --check --dry-run` — all green
- [x] T042 Execute `quickstart.md` manual smoke test against a running server (real happy path)
- [x] T043 [P] Update `.claude/changelog.md` (BE-001 delivered) and confirm `contracts/openapi.yaml` matches implemented responses (Contract Sync note for #000 freeze)

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)** → no deps.
- **Foundational (P2)** → depends on Setup; **BLOCKS all user stories**.
- **US1 (P3)** → after Foundational. MVP.
- **US2 (P4)** → after Foundational (independent of US1, but shares tokens.py).
- **US3 (P5)** → after Foundational (needs User/SocialIdentity from P2).
- **US4 (P6)** → after Foundational (extends MeView from US1).
- **Polish (P7)** → after desired stories complete.

### Within foundational

- T007 → T008 → (T009, T010). T012 → T013 → T014. Settings T005 references
  core classes by path, so land T007–T011 before finalizing T005 wiring.

### Story dependencies

- US1, US2, US3 are independently testable. US4 extends the MeView/urls created
  in US1 (do US1 first, or stub MeView in foundational). US2/US3 both add to
  `services/tokens.py`/`serializers.py`/`views.py`/`urls.py` — sequence edits to
  those shared files to avoid conflicts (not [P] across stories).

### Parallel opportunities

- Setup: T003, T004 in parallel.
- Foundational: T006, T007, T009, T010, T011, T012, T015, T016 in parallel
  (respecting T007→T008 and T012→T013→T014).
- Within a story: the `[P]` test-file tasks and independent serializer tasks
  run in parallel; views/urls edits are sequential (same files).

---

## Parallel Example: Foundational

```bash
# After T005 skeleton settings + T007 errors land, run in parallel:
Task: "core/middleware.py AppKeyMiddleware (T009)"
Task: "core/authentication.py typed JWT errors (T010)"
Task: "core/pagination.py CursorPage (T011)"
Task: "apps/accounts/managers.py UserManager (T012)"
Task: "apps/accounts/tests/factories.py + conftest.py (T016)"
```

## Implementation Strategy

### MVP first (US1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 →
4. **STOP & VALIDATE** register/login/GET me end-to-end → demo.

### Incremental delivery

Foundation → US1 (MVP) → US2 (sessions) → US3 (social) → US4 (delete) → Polish.
Each story is a testable increment that doesn't break the previous.

---

## Notes

- Tests are written first per phase and must FAIL before implementation (spec +
  Principle XI). External providers mocked at the verify-function boundary.
- Every endpoint asserts status + error `code` + response shape against
  `contracts/auth-endpoints.md`.
- Commit after each task or logical group; keep secrets out of code and logs.
- `[P]` = different files, no incomplete dependency.
