# Research: Backend Foundation & Auth (BE-001)

**Date**: 2026-07-25 · **Feature**: `BE-001-backend-foundation-auth`

All versions below were looked up on PyPI on 2026-07-25 (Constitution
Principle XIV — Dependency Hygiene). Nothing is guessed.

## Decision 1 — Django 5.2 LTS instead of 6.0

- **Decision**: `Django==5.2.16` (latest 5.2 LTS patch).
- **Rationale**: 5.2 is an LTS (security support through ~April 2028) → the right
  choice for a production backend that values maintainability. Critically,
  `djangorestframework-simplejwt` 5.5.1's classifiers list Django up to **5.2**
  only (not 6.0), so pinning 6.0.7 would put a core auth dependency onto an
  unsupported-by-that-package Django. DRF 3.17.1 supports 4.2–6.0, so 5.2 is the
  common, fully-supported baseline.
- **Alternatives considered**: Django 6.0.7 (latest, but non-LTS + simplejwt
  not yet declaring support); Django 4.2 LTS (older, unnecessary).
- **Requires**: Python 3.12+ (matches constitution).

## Decision 2 — Auth: DRF + SimpleJWT with rotation + blacklist

- **Decision**: `djangorestframework==3.17.1`, `djangorestframework-simplejwt==5.5.1`.
  Enable the bundled `rest_framework_simplejwt.token_blacklist` app.
- **Config**: `ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=True`,
  `ACCESS_TOKEN_LIFETIME` and `REFRESH_TOKEN_LIFETIME` read from env
  (`ACCESS_TOKEN_LIFETIME_MINUTES`, `REFRESH_TOKEN_LIFETIME_DAYS`).
- **Rationale**: SimpleJWT gives access+refresh, rotation (single-use refresh),
  and a DB blacklist for revocation — exactly FR-007..FR-011. The `token_blacklist`
  app provides `OutstandingToken`/`BlacklistedToken`; logout = blacklist the
  presented refresh token; rotation auto-blacklists the old one.
- **Error-code mapping**: SimpleJWT raises `InvalidToken`/`TokenError` (→ DRF
  `AuthenticationFailed`). A custom DRF `exception_handler` inspects the failure
  to emit the correct catalog code:
  - access token expired → `401 TOKEN_EXPIRED`
  - invalid/revoked/blacklisted/malformed → `401 TOKEN_INVALID`
  - no credentials on a protected endpoint (`NotAuthenticated`) →
    `401 UNAUTHORIZED_USER`
  Distinguishing expired from invalid is done by checking the token error type
  (SimpleJWT surfaces an `ExpiredSignatureError` cause / `messages` entry) inside
  a thin `JWTAuthentication` subclass that raises typed exceptions.
- **Alternatives considered**: hand-rolled JWT with PyJWT (more code, must
  re-implement rotation/blacklist); django-allauth/dj-rest-auth (heavyweight,
  pulls session/template machinery we don't want for a pure API — violates
  Principle XII Simplicity).

## Decision 3 — Google ID token verification

- **Decision**: `google-auth==2.56.2`. Verify with
  `google.oauth2.id_token.verify_oauth2_token(token, requests.Request(), audience=GOOGLE_OAUTH_CLIENT_ID)`.
- **Rationale**: Official Google library; validates signature against Google
  certs, `aud`, `iss`, and expiry in one call. Extract `sub` (subject id) and
  `email`/`email_verified`.
- **Failure → `400 SOCIAL_TOKEN_INVALID`** (wrap any `ValueError`).
- **Alternatives**: manual JWKS fetch + PyJWT (reinvents what google-auth does
  and is easier to get wrong).

## Decision 4 — Apple Sign-In verification via PyJWT (NOT python-jose)

- **Decision**: `PyJWT==2.13.0` + `cryptography==49.0.0`. Verify Apple's identity
  token (JWS, ES256) using `jwt.PyJWKClient("https://appleid.apple.com/auth/keys")`
  to fetch Apple's public JWKS, then `jwt.decode(token, key, algorithms=["ES256"],
  audience=APPLE_CLIENT_ID, issuer="https://appleid.apple.com")`.
- **Rationale — deviation from roadmap note**: The roadmap suggested
  `python-jose`. We choose **PyJWT** instead because: (a) PyJWT is actively
  maintained and is already a transitive dependency of SimpleJWT (no new
  ecosystem), (b) `python-jose` has had maintenance gaps and prior CVE history,
  (c) PyJWT ships `PyJWKClient` which handles JWKS fetch + key caching cleanly.
  This is recorded so the deviation is intentional and reviewable
  (Principle XIV: major dependency choices cite their reasoning).
- **Notes**: Apple provides the user's email only on the *first* authorization
  and may use a private-relay address; the stable identity is the `sub` claim.
  This is exactly why the account model keys social identities on
  `(provider, subject id)` and treats email as optional (spec FR-013/014a).
- **Failure → `400 SOCIAL_TOKEN_INVALID`**.
- **Alternatives**: `python-jose` (rejected, see above); manual ES256 verify
  (error-prone).

## Decision 5 — Custom User model with optional email

- **Decision**: Custom `User(AbstractBaseUser, PermissionsMixin)` with an
  **integer `BigAutoField` primary key** (contract mandates `User.id: integer`),
  `email` (`unique=True, null=True, blank=True`), `display_name`,
  `USERNAME_FIELD = "email"`, `REQUIRED_FIELDS = ["display_name"]`, plus a custom
  `UserManager`. Set `AUTH_USER_MODEL = "accounts.User"` from the very first
  migration.
- **Rationale**: Email must be optional for social-only accounts (spec FR-014a).
  PostgreSQL treats multiple `NULL`s as distinct under a UNIQUE constraint, so
  "unique when present, null allowed" works natively without a partial index.
  The pk stays an integer to honor the frozen-ish contract (`openapi.yaml`
  `User.id: integer`); switching to UUID would be a breaking contract change
  requiring Contract Sync with mobile — out of scope here. Setting the custom
  user model up-front avoids the painful mid-project swap.
- **Password hashing**: put `argon2-cffi` first in `PASSWORD_HASHERS` so Argon2id
  is the default hasher (Principle I/II), with Django's PBKDF2 kept as fallback.
- **Email normalization**: lowercase + `BaseUserManager.normalize_email` on save
  and on all lookups (spec edge case).
- **Alternatives**: `AbstractUser` (carries a `username` field we don't want);
  email as a separate unique-required field (breaks social-no-email).

## Decision 6 — X-App-Key gate as middleware

- **Decision**: A `AppKeyMiddleware` (in `core/middleware.py`) that compares the
  `X-App-Key` header to `settings.X_APP_KEY` using `hmac.compare_digest`
  (constant-time). On mismatch/absence it returns a `401` JSON response in the
  standard error envelope with code `INVALID_APP_KEY`, **before** view/auth
  processing. A small settings-driven path allowlist exempts operational paths
  (`/admin/`, health check, schema) as needed.
- **Rationale**: Middleware runs ahead of DRF auth, satisfying FR-001 ("before
  processing the body"). Constant-time compare avoids timing side-channels.
- **Alternatives**: a DRF permission class (runs too late — after body parsing /
  per-view, and misses non-DRF paths).

## Decision 7 — Uniform error envelope via custom exception handler

- **Decision**: `core/errors.py` defines an `ErrorCode` enum/constants and a
  central map `code → (http_status, default_message)`. `core/exceptions.py`
  defines `AppError` (raisable with a code) and `api_exception_handler`, wired via
  `REST_FRAMEWORK["EXCEPTION_HANDLER"]`. It renders every error as
  `{"error": {"code", "message"}}` and maps built-in DRF exceptions
  (`ValidationError`→`VALIDATION_ERROR`, `NotFound`→`NOT_FOUND`,
  `PermissionDenied`→`FORBIDDEN`, auth failures → the token codes above).
- **Rationale**: One handler = every endpoint (incl. future BE-002/003) reports
  errors consistently with zero per-view boilerplate (Principle V).
- **Alternatives**: per-view try/except (drifts, violates Principle V).

## Decision 8 — Config, storage, cache, tooling

- **Config**: `django-environ==0.14.0`; settings split
  `config/settings/{base,dev,staging,production}.py`; all secrets/tunables from
  env (Principle VI). `.env.example` already lists the keys.
- **Database**: PostgreSQL via `psycopg[binary]==3.3.4` (psycopg 3, modern).
  `DATABASE_URL` via `env.db()`.
- **Cache**: `redis==8.0.1` + `django-redis==7.0.0`, `CACHES` from `REDIS_URL`.
  Not functionally required by auth, but part of the foundation (BE-002 cache,
  BE-004 throttle depend on it). Tests use Django's local-memory cache.
- **Testing**: `pytest==9.1.1` + `pytest-django==4.12.0` + `factory-boy==3.3.3`
  + `pytest-cov==7.1.0`; external providers (Google/Apple) mocked with
  `unittest.mock` at the verification-function boundary — **no live network in
  tests** (Principle XI). Google/Apple verification is isolated behind small
  functions/a service precisely so it is trivially mockable.
- **Quality**: `black==26.5.1`, `ruff==0.16.0`, `mypy==2.3.0` +
  `django-stubs==6.0.7` + `djangorestframework-stubs==3.17.0`.

## Resolved unknowns

| Unknown | Resolution |
|---|---|
| Django major version | 5.2.16 LTS (simplejwt support + LTS stability) |
| Apple JWS library | PyJWT (not python-jose) — see Decision 4 |
| Expired vs invalid token distinction | JWTAuthentication subclass + exception handler |
| Optional-email uniqueness | Postgres NULL-distinct UNIQUE on `email` |
| Refresh rotation/revocation | SimpleJWT rotation + `token_blacklist` app |
| Password hasher | Argon2id default via `argon2-cffi` |

No open NEEDS CLARIFICATION items remain.
