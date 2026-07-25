<!--
================================================================================
SYNC IMPACT REPORT
================================================================================
Version Change: (template) → 1.0.0 (MAJOR — initial ratification; replaces the
unfilled Spec Kit template with the SoundWave Backend constitution)

Modified Sections:
- Filled entire template. Established 14 Core Principles tailored to a
  Django + DRF backend that proxies/caches the Jamendo API and manages real
  user accounts (JWT), playlists, liked tracks, and listening history.
- Added Technical Standards (stack, domains, conventions), Development
  Workflow (pre-commit gates, testing gates, review, quality checks), and
  Governance (amendment process + compliance).

Principles established:
  I.    Two-Tier Auth & Access Control (X-App-Key + JWT, IDOR protection)
  II.   Contract-First API (openapi.yaml + api-context.md as source of truth)
  III.  Layered App Architecture (domain apps, thin views, service layer)
  IV.   Catalog Proxy & Cache Discipline (Jamendo wrapper, Redis TTL policy)
  V.    Consistent Error Handling (error-code catalog, uniform envelope)
  VI.   Configuration & Secrets Hygiene (no hardcoded values, env-driven)
  VII.  Data Integrity & Migrations (non-destructive, cursor pagination)
  VIII. Security Hardening (rate limit, token rotation, OWASP/IDOR)
  IX.   Observability (structured logging, no secrets in logs, Sentry)
  X.    Code Quality & Typing (black, ruff, mypy, type hints)
  XI.   Testing Discipline (pytest, mocked upstream, contract tests)
  XII.  Simplicity & YAGNI
  XIII. Legal & Licensing Compliance (Jamendo non-commercial)
  XIV.  Dependency Hygiene (latest-version + official-docs sourcing)

Templates Requiring Updates:
- .specify/templates/plan-template.md ✅ (generic Constitution Check section
  remains accurate; no inline reference to specific principles)
- .specify/templates/spec-template.md ✅ (no principle-specific sections)
- .specify/templates/tasks-template.md ✅ (no principle-specific sections)
- .claude/project-context.md ⚠ pending — "Repo Layout" mentions
  dev-workflow.md / changelog.md / decisions/ that do not yet exist; create or
  remove those references so runtime docs match reality.

Follow-up TODOs:
- Freeze API contract #000 (openapi.yaml v0.1.0) jointly with soundwave-mobile
  before BE-001 implementation begins.
================================================================================
-->

# SoundWave Backend Constitution

> Repo: `soundwave-backend` — Django + DRF backend for the SoundWave music app.
> Acts as a **proxy + cache in front of the Jamendo API** (Creative Commons,
> non-commercial) and owns real user accounts (email/social login), playlists,
> liked tracks, and listening history. Companion repo: `soundwave-mobile`
> (Flutter), synced through `contracts/openapi.yaml` + `.claude/api-context.md`.
> The backend NEVER stores or transcodes audio — tracks stream directly from
> Jamendo URLs.

## Core Principles

### I. Two-Tier Auth & Access Control

The API MUST enforce two independent auth layers, and endpoint access control
MUST be derived from the authenticated identity — NEVER from client-supplied
identifiers.

- **Layer 1 — `X-App-Key`**: Every endpoint (including anonymous ones) MUST
  validate `X-App-Key` via middleware. A missing/invalid key MUST return
  `401 INVALID_APP_KEY` before any further processing.
- **Layer 2 — `Authorization: Bearer <access_token>`**: All `/me/*` endpoints
  and `POST /auth/logout` MUST additionally require a valid user JWT. Missing
  auth → `401 UNAUTHORIZED_USER`; expired → `401 TOKEN_EXPIRED`; invalid/
  revoked → `401 TOKEN_INVALID`.
- **Ownership enforcement (IDOR)**: Any operation on a user-owned resource
  (playlist, playlist track, liked track, history) MUST be scoped by
  `request.user`. Querysets MUST filter on the owner; a resource owned by
  another user MUST return `403 FORBIDDEN` (or `404 NOT_FOUND` where existence
  itself is sensitive). A client-provided `user_id` in a body/query MUST NEVER
  be trusted for authorization.
- **Access tokens** are short-lived (15–30 min). **Refresh tokens** are
  long-lived and MUST be revocable. Refresh MUST rotate the token and blacklist
  the old one; logout MUST revoke the presented refresh token.
- Passwords MUST be hashed with Django's password hashers (Argon2/PBKDF2) —
  never stored or logged in plaintext. Social `id_token`s (Google/Apple) MUST
  be cryptographically verified server-side; failure → `400 SOCIAL_TOKEN_INVALID`.

**Rationale**: The most common and most damaging class of backend bug for a
per-user product is IDOR — returning or mutating another user's data. Deriving
authorization from the token, never from the request payload, makes this
class structurally impossible rather than caught case-by-case.

### II. Contract-First API

`contracts/openapi.yaml` is the machine-readable source of truth for the HTTP
surface. `.claude/api-context.md` is its human/LLM companion, and both are
derived from `docs/screen-inventory.md`. These artifacts exist in BOTH repos
and MUST stay in sync.

- The authoring order is mandatory: **screen-inventory → openapi.yaml +
  api-context.md → code**. Do NOT change request/response shapes in code
  before the contract is updated.
- Every endpoint's request/response schema, status codes, and error codes MUST
  match the contract. Serializers are the enforcement point.
- The contract carries a semantic version (currently `v0.1.0`). Breaking
  changes (removed/renamed fields, changed types, new required fields) MUST bump
  the version and be coordinated with `soundwave-mobile` before merge — this is
  a **Contract Sync** point.
- Cursor pagination is the standard for every list endpoint (`catalog/tracks`,
  `me/liked-tracks`, `me/playlists`, `me/history`): `?cursor=&limit=` →
  `{ items, next_cursor, has_more }`. New list endpoints MUST follow it.
- A change that only the backend can see (internal refactor) needs no contract
  change; anything a client can observe DOES.

**Rationale**: Two independently developed repos can only stay compatible if
there is one authoritative description of the wire format. Deriving the contract
from screens keeps the API grounded in real UI needs instead of speculative
endpoints.

### III. Layered App Architecture

The codebase MUST be organized into domain-scoped Django apps with clear
internal layers. Business logic MUST NOT live in views.

- **Apps by domain**: `apps/accounts` (users, auth, JWT), `apps/catalog`
  (Jamendo proxy + cache), `apps/library` (playlists, liked, history). A new
  domain gets a new app; unrelated concerns MUST NOT be merged into one app.
- **Layer separation within an app**:
  - **Views/ViewSets** — thin: parse request, delegate, shape response. No
    business rules, no direct third-party calls.
  - **Serializers** — validation and (de)serialization only; they are the
    contract enforcement layer.
  - **Services** (`services.py` / `services/`) — business logic, orchestration,
    external calls (Jamendo), cache access. Reusable and independently testable.
  - **Models & selectors** — persistence and query logic.
- **Cross-app rule**: an app MUST NOT import another app's internal modules
  directly. Cross-app needs go through a service or a well-defined public
  interface. `apps/catalog` MUST NOT depend on `apps/library` or vice versa.
- **Shared code** lives in `config/` (settings, urls, middleware) and a `core/`
  or `common/` package (base classes, pagination, exception handler, constants)
  — never duplicated per app.
- Fat models are acceptable for data-level logic; multi-model or external-call
  orchestration MUST live in a service.

**Rationale**: Thin views + a service layer keep endpoints testable and let the
same logic be reused across API, admin, and background jobs. Domain apps with
no cross-imports keep the system extensible — a new feature is a new app, not a
change scattered across the codebase.

### IV. Catalog Proxy & Cache Discipline

The catalog is a proxy over Jamendo. The Jamendo `client_id` and upstream
response shape MUST NEVER leak to clients, and upstream load MUST be minimized
through caching.

- **Client wrapper**: All Jamendo calls go through a single client class in
  `apps/catalog` (e.g. `JamendoClient`). No other module constructs Jamendo
  URLs or reads its raw JSON. The `client_id` comes from settings/env only.
- **Response mapping**: Jamendo JSON MUST be mapped into the `Track` / `Artist`
  / `Album` schemas defined in `openapi.yaml` before leaving the backend. Raw
  upstream fields MUST NOT be forwarded verbatim.
- **Caching**: Redis caches catalog responses. TTLs MUST be defined as named
  settings constants, not inline literals, and differ by volatility:
  long-lived for `trending`/`genres`, short-lived for `search`. Cache keys MUST
  be namespaced and include all query parameters that affect the result.
- **Upstream failure**: Jamendo timeout / rate-limit / 5xx MUST be caught and
  translated to `502 CATALOG_UPSTREAM_ERROR` — the raw upstream error MUST NOT
  propagate. Requests to Jamendo MUST use an explicit timeout.
- **Source swappability**: Because clients only see the mapped schema, replacing
  or supplementing the music source later MUST NOT require any client change.

**Rationale**: The proxy exists for three reasons — hide the credential, cut
quota via caching, and decouple the app from Jamendo. Each rule above protects
one of those; centralizing all upstream access in one wrapper is what makes the
source swappable without touching mobile.

### V. Consistent Error Handling

Every error response MUST use one uniform envelope and a code from the
canonical catalog. Ad-hoc error shapes are FORBIDDEN.

- **Envelope**: `{ "error": { "code": "<CODE>", "message": "<human text>" } }`,
  produced by a single custom DRF exception handler — not hand-built per view.
- **Error codes** MUST come from the catalog in `api-context.md`
  (`INVALID_APP_KEY`, `UNAUTHORIZED_USER`, `TOKEN_EXPIRED`, `TOKEN_INVALID`,
  `FORBIDDEN`, `EMAIL_ALREADY_EXISTS`, `INVALID_CREDENTIALS`,
  `SOCIAL_TOKEN_INVALID`, `VALIDATION_ERROR`, `NOT_FOUND`,
  `TRACK_ALREADY_IN_PLAYLIST`, `REORDER_MISMATCH`, `CATALOG_UPSTREAM_ERROR`).
  Codes MUST be defined as constants/enums, never as string literals scattered
  across views.
- Adding a new error condition MUST add a new code to the catalog (and the
  contract) — reusing a loosely-related existing code is FORBIDDEN.
- HTTP status MUST match the code's documented status. `message` is for humans/
  debugging; clients branch on `code`, never on `message` text.
- Validation errors from serializers MUST be surfaced as `400 VALIDATION_ERROR`
  through the same handler.

**Rationale**: The mobile client branches on stable machine codes. A single
envelope + a single handler means every endpoint — including future ones —
reports failures the client already knows how to handle, with zero per-view
boilerplate.

### VI. Configuration & Secrets Hygiene

No configuration value, secret, URL, or tunable MUST be hardcoded in
application code. All of them come from settings, which read the environment.

- **Secrets** (Django `SECRET_KEY`, DB creds, Redis URL, Jamendo `client_id`,
  Google/Apple OAuth credentials, Sentry DSN) MUST come from environment
  variables via a settings loader (e.g. `django-environ`). They MUST NOT appear
  in source, fixtures, or logs. `.env` MUST be git-ignored; a committed
  `.env.example` documents required keys.
- **Settings split**: `config/settings/{base,dev,staging,production}.py` (or
  equivalent). Environment-specific behavior is selected by env var, not by
  editing code.
- **Tunables are named constants**: cache TTLs, page-size defaults/limits,
  timeouts, token lifetimes, rate-limit quotas MUST be named settings — never
  magic numbers inline. Changing a TTL or a page size MUST be a one-line
  settings edit.
- **No environment branching in business logic**: code MUST NOT check
  `if DEBUG`/hostname to alter behavior; inject the difference via settings.
- Enumerable domain strings (error codes, provider names, genre slugs mapping)
  MUST live in a constants module, not be retyped at call sites.

**Rationale**: "Không hardcode" is the backbone of maintainability here. When
every secret and tunable is env/settings-driven, the same artifact runs safely
across dev/staging/prod, secrets never leak into git history, and operational
tuning never requires a code change or redeploy of logic.

### VII. Data Integrity & Migrations

User data MUST NOT be lost or corrupted. Schema evolution MUST be safe and
reversible-in-intent.

- Every model change MUST ship with a Django migration; migrations MUST be
  committed and MUST be reviewed like code.
- Migrations MUST be non-destructive by default. Column/table drops or type
  changes that can lose data MUST be staged (add → backfill → switch → remove)
  across releases, never done in a single destructive step on populated tables.
- `PlaylistTrack` MUST persist explicit ordering; reorder MUST be validated so
  the submitted `track_ids` exactly match the playlist's current tracks
  (mismatch → `400 REORDER_MISMATCH`). Ordering MUST be stable and unique per
  playlist.
- Idempotent operations MUST behave as documented: re-liking an already-liked
  track returns `204` (not an error); adding a duplicate track to a playlist
  returns `409 TRACK_ALREADY_IN_PLAYLIST`.
- `DELETE /me` MUST cascade-remove all of the user's playlists, liked tracks,
  and history (no orphaned rows).
- Cursor pagination MUST be based on a stable, ordered key so pages don't skip
  or duplicate rows under concurrent writes.

**Rationale**: Playlists and history are user-generated data with no upstream
backup — unlike catalog data, they cannot be re-fetched from Jamendo. Safe
migrations and correct idempotency/ordering protect the only data the backend
truly owns.

### VIII. Security Hardening

Security is a first-class requirement at every layer, not a final spec.

- **Rate limiting**: Abuse-prone endpoints MUST be throttled per user/IP —
  especially `POST /me/history`, auth endpoints, and catalog search. Quotas are
  settings-driven (Principle VI).
- **Token lifecycle**: Refresh rotation + blacklist on refresh and logout
  (Principle I) MUST be enforced server-side; a revoked token MUST NOT be usable.
- **Input validation at every boundary**: request bodies/queries (serializers),
  Jamendo responses, and social `id_token`s MUST be validated before use.
- **Transport & headers**: production MUST serve over HTTPS with secure cookie/
  HSTS settings; CORS MUST be an explicit allowlist, never `*` in production.
- **OWASP review** for user-facing changes, with explicit attention to IDOR on
  `/me/playlists/{id}` and related nested resources.
- Dependencies MUST be monitored for known vulnerabilities; a flagged CVE in a
  direct dependency MUST be triaged before release.

**Rationale**: This backend holds real credentials and per-user libraries. The
attack surface is authorization (IDOR), token replay, and endpoint abuse —
codifying throttling, token revocation, and boundary validation makes these
review checkpoints instead of afterthoughts.

### IX. Observability

The system MUST be debuggable in production without ever exposing secrets.

- **Structured logging** (key/value or JSON) MUST be used, with a request/
  correlation id where feasible. `print()` for diagnostics is FORBIDDEN.
- Logs MUST NEVER contain passwords, tokens, `id_token`s, the Jamendo
  `client_id`, or full auth headers. Redaction MUST happen before logging.
- **Error tracking** (Sentry) MUST be wired in staging/production via env-driven
  DSN, with PII scrubbing enabled.
- Upstream Jamendo failures MUST be logged with enough context (endpoint,
  status, latency) to diagnose quota/timeout issues, without dumping full
  responses.
- Health/readiness endpoints MUST reflect real dependency status (DB, Redis)
  where deployment requires it.

**Rationale**: A proxy's failures are often upstream and intermittent. Without
structured logs and error tracking they're invisible; with them, a Jamendo
rate-limit spike is a dashboard line rather than a user-reported mystery. The
redaction rules keep observability from becoming a data-leak vector.

### X. Code Quality & Typing

All code MUST pass automated formatting, linting, and type checks with zero
warnings before merge.

- **Formatting**: `black` (and `isort` or ruff's import sorting) — zero diff.
- **Linting**: `ruff` (or flake8) MUST report zero errors.
- **Typing**: `mypy` in strict-ish mode. Public functions (services,
  selectors, client methods) MUST have explicit parameter and return type hints.
- Naming: modules `snake_case.py`; classes `PascalCase`; DRF classes suffixed by
  role (`TrackSerializer`, `PlaylistViewSet`, `JamendoClient`).
- Code MUST be self-documenting; comments explain non-obvious *why*, not *what*.
- No dead code, no commented-out blocks committed, no unused imports.

**Rationale**: Automated gates make quality objective and reviewable in any PR,
and give the toolchain a clean zero-warning baseline to defend as the codebase
grows.

### XI. Testing Discipline

Business logic and API behavior MUST be verified by automated tests. External
services MUST be mocked — tests MUST NOT hit the live Jamendo API.

- **Framework**: `pytest` + `pytest-django`; API tests via DRF's
  `APIClient`/`APITestCase`. Fixtures/factories (e.g. `factory_boy`) for data.
- **Required coverage by kind**:
  - Services and selectors (unit) — including cache hit/miss and Jamendo
    error → `CATALOG_UPSTREAM_ERROR` mapping.
  - Auth flows — register/login/social/refresh/logout, token expiry & revocation.
  - Authorization — IDOR: user A MUST NOT read/mutate user B's resources.
  - Endpoint contract — status codes, error codes, and response shape match
    `openapi.yaml` for happy and error paths.
  - Data rules — reorder mismatch, like idempotency, duplicate-in-playlist,
    cursor pagination correctness, cascade delete.
- **Jamendo MUST be mocked** at the client boundary; no network in the test
  suite. Tests MUST be deterministic (no reliance on wall-clock/random without
  control).
- Coverage is a signal, not a hard CI gate; reviewers judge adequacy by whether
  critical/security paths are covered.

**Rationale**: The two riskiest areas — authorization and upstream error
handling — are exactly the ones that are silent when broken. Contract tests keep
the code honest against `openapi.yaml`; mocking Jamendo keeps the suite fast,
deterministic, and quota-free.

### XII. Simplicity & YAGNI

The backend MUST stay focused on its purpose: proxy/cache Jamendo and manage
user libraries. Complexity MUST be justified by a concrete, current need.

- Start with the simplest implementation that satisfies the spec; add
  abstraction only when a second real use appears.
- Do NOT add configurability, plugin systems, or generic frameworks unless a
  spec requires them.
- Prefer Django/DRF built-ins over third-party packages when capability is
  equivalent; each new package MUST be justified.
- Out of scope until explicitly specced: audio storage/transcoding, admin
  content pipeline, offline download, IAP/premium, sharing/social features.
- Three straightforward lines beat one premature abstraction.

**Rationale**: The architecture is deliberately thin (no audio storage, no admin
upload). Keeping it that way minimizes surface area to secure and maintain, and
prevents the codebase from drifting toward a general-purpose media platform it
was never meant to be.

### XIII. Legal & Licensing Compliance

Jamendo's free API is licensed for **non-commercial** use only. The product MUST
NOT introduce commercial features while relying on the free tier.

- No ads, paid subscriptions, IAP, or other monetization MUST be added to any
  Jamendo-backed flow without first obtaining a commercial license from Jamendo.
  This constraint MUST be surfaced in any spec that touches monetization.
- Track licensing metadata (e.g. `license_type`, and `license.download` where
  relevant) MUST be preserved through mapping and MUST NOT be stripped.
- Offline download MUST NOT be implemented without first verifying per-track
  download rights from the Jamendo license fields.
- Attribution/license info required by Creative Commons MUST remain available to
  the client.

**Rationale**: Violating Jamendo's terms puts the entire product at legal risk
and could revoke API access. Encoding the non-commercial boundary as a
non-negotiable principle prevents a well-meaning monetization feature from
quietly breaching the license.

### XIV. Dependency Hygiene

When adding or upgrading a third-party package, the version and documentation
MUST come from the official source. Versions MUST NOT be guessed, copied from
training data, or carried over from unrelated projects.

- **Latest version sourcing**: Before pinning a package, look up the latest
  stable release on PyPI (or the upstream repo). New deps are added to the
  appropriate `requirements/*.txt` (or `pyproject.toml`) with an explicit,
  pinned/compatible version — open-ended (`package` with no version) is
  FORBIDDEN.
- **Official documentation** MUST be consulted for public API, breaking-change
  notes, and minimum Python/Django compatibility. Inferring API shape from
  memory is FORBIDDEN.
- **Major upgrades** MUST include a CHANGELOG/migration-guide review before the
  requirement is changed; the PR/spec MUST cite the breaking changes that affect
  this codebase (or state none apply).
- **Lock integrity**: the resolved dependency set (pinned requirements or lock
  file) MUST be committed; unexpected transitive churn in a PR MUST be reviewed.
- **No fictional packages**: every dependency MUST exist on PyPI under the exact
  name written. If a package can't be found, stop and ask — do not guess a
  similar name.
- Security: new deps MUST be checked for known CVEs; abandoned/unmaintained
  packages MUST be avoided when a maintained equivalent exists.

**Rationale**: Guessed versions and phantom packages cause late-binding failures
that surface only at install/deploy time, after code is written. A 30-second
PyPI lookup at plan time prevents rework and avoids pulling in known-vulnerable
or non-existent releases.

## Technical Standards

### Platform & Stack

- **Language/Framework**: Python 3.12+ · Django + Django REST Framework
- **Database**: PostgreSQL
- **Cache / quota store**: Redis (catalog response cache + rate-limit counters)
- **Auth**: JWT via `djangorestframework-simplejwt` (access + rotating refresh
  with blacklist); Google ID token verify via `google-auth`; Apple Sign-In via
  JWS verification (`python-jose`)
- **Upstream**: Jamendo API (via a single `JamendoClient` wrapper)
- **Config**: `django-environ` (or equivalent) with split settings
  `base/dev/staging/production`
- **Error tracking**: Sentry (env-driven DSN, PII scrubbed)
- **Quality**: `black` + `ruff` + `mypy` (zero warnings)
- **Testing**: `pytest` + `pytest-django` + `factory_boy`, Jamendo mocked
- **Background (if needed)**: Celery (e.g. warm/refresh catalog cache) — only if
  a spec requires it (Principle XII)

### Core Domains (Django apps)

- **accounts**: `User` model, email/password + social login, JWT issue/refresh/
  revoke, `X-App-Key` middleware, `/auth/*`, `/me` (profile, delete account)
- **catalog**: `JamendoClient`, Redis cache layer, schema mapping, `/catalog/*`
  (trending, genres, tracks (cursor/search/genre), track/artist/album detail)
- **library**: `Playlist`, `PlaylistTrack` (Jamendo `track_id` + order),
  `LikedTrack`, `ListeningHistory`; all `/me/*` library endpoints

### API Conventions

- Uniform error envelope `{ "error": { "code", "message" } }` via one custom
  exception handler; codes from the canonical catalog (Principle V).
- Cursor pagination `{ items, next_cursor, has_more }` for all lists.
- Two-tier auth headers: `X-App-Key` on everything; `Authorization: Bearer` on
  `/me/*` + `/auth/logout`.
- Serializers are the single validation + shape-enforcement layer against
  `openapi.yaml`.

### Repository Layout (target)

```
config/            # settings/{base,dev,staging,production}, urls, wsgi, middleware, celery
core/ (or common/) # base serializers/views, pagination, exception handler, constants, error codes
apps/
  accounts/        # models, serializers, services, views, migrations, tests
  catalog/         # client (JamendoClient), cache, services, serializers, views, tests
  library/         # models, serializers, services, views, migrations, tests
contracts/
  openapi.yaml     # machine-readable contract (source of truth)
requirements/      # base.txt, dev.txt, production.txt
docs/              # PRD.md, screen-inventory.md
specs/             # BE-NNN-*/ feature specs (Spec Kit)
manage.py
.env.example
```

## Development Workflow

### Pre-Commit Checklist (MANDATORY)

```bash
black .                        # Format (zero diff)
ruff check .                   # Lint (zero errors)
mypy .                         # Type check (zero errors)
pytest                         # All tests pass (Jamendo mocked)
python manage.py makemigrations --check --dry-run   # No missing migrations
```

### Testing Gates

All pull requests MUST pass:

1. All unit + API tests pass, deterministically.
2. Static analysis (`ruff`) with zero errors.
3. Type check (`mypy`) with zero errors.
4. Formatting verified (`black --check`).
5. No un-generated model migrations (`makemigrations --check`).
6. IDOR/authorization tests present for any new `/me/*` behavior.

### Review Requirements

- All changes MUST be reviewed before merge.
- Security-sensitive changes (auth, tokens, `X-App-Key`, `/me/*` ownership,
  rate limiting) MUST receive additional scrutiny.
- Any change to request/response shape MUST update `openapi.yaml` +
  `api-context.md` in the SAME change, and flag a Contract Sync with
  `soundwave-mobile` when the contract version changes.
- New dependencies MUST be justified and version-verified (Principle XIV).
- Model changes MUST include reviewed migrations (Principle VII).

### Quality Checks

- Auth flow MUST be verified under: register, login (correct + wrong password),
  social login (valid + invalid `id_token`), refresh (valid + revoked),
  logout (token revoked).
- Authorization MUST be verified: user A cannot read/mutate user B's playlists,
  liked tracks, or history.
- Catalog MUST be verified: cache hit vs miss, Jamendo timeout →
  `502 CATALOG_UPSTREAM_ERROR`, `client_id` never present in any response.
- Data rules MUST be verified: reorder mismatch, like idempotency, duplicate
  track in playlist, cursor pagination has no gaps/dupes, `DELETE /me` cascades.

## Governance

This constitution establishes non-negotiable principles for SoundWave Backend
development. All implementation decisions MUST align with these principles;
where a spec conflicts, the constitution wins unless it is formally amended.

### Amendment Process

1. Proposed amendments MUST be documented with rationale.
2. Amendments MUST be reviewed for impact on existing code and the contract.
3. Breaking changes require a migration/rollout plan before approval.
4. Version MUST be incremented per semantic versioning:
   - **MAJOR**: principle removal or incompatible redefinition
   - **MINOR**: new principle or material expansion
   - **PATCH**: clarification or wording refinement

### Compliance

- All pull requests MUST verify compliance with the relevant principles.
- Complexity exceeding these standards MUST be explicitly justified in the spec
  or PR.
- Deviations MUST be documented with rationale and approved by the project lead.
- Runtime development guidance lives in `.claude/` (`project-context.md`,
  `sdd-roadmap.md`, `api-context.md`) and MUST stay consistent with this
  constitution.

**Version**: 1.0.0 | **Ratified**: 2026-07-25 | **Last Amended**: 2026-07-25
