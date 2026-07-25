# Feature Specification: Backend Foundation & Auth

**Feature Branch**: `BE-001-backend-foundation-auth`

**Created**: 2026-07-25

**Status**: Draft

**Input**: User description: "BE-001 Backend Foundation & Auth — Dựng skeleton Django + DRF cho SoundWave backend và toàn bộ hệ thống xác thực người dùng."

## Overview

This is the foundational feature of the SoundWave backend. It establishes the
running service and the complete user authentication system: an app-level access
gate, real user accounts (email/password + Google/Apple social sign-in), a
short-lived-access / revocable-refresh token model, and the account profile
endpoints. Every later feature (catalog, library) depends on the identity and
error-handling foundation delivered here.

Content catalog (`/catalog/*`) and user library (`/me/playlists`,
`/me/liked-tracks`, `/me/history`) are explicitly **out of scope** and belong to
BE-002 / BE-003. Only `GET /me` and `DELETE /me` from the `/me/*` group are in
scope, because they are part of the account lifecycle.

## Clarifications

### Session 2026-07-25

- Q: When social sign-in carries an email that already belongs to an existing
  email/password account, how should it be handled? → A: Auto-link — treat the
  Google/Apple-verified email as authoritative and sign into / attach the social
  identity to the existing account (one account per email). Residual risk: v1 has
  no email verification for email/password registration, so a pre-registered
  email could be "squatted"; this is accepted for v1 and mitigated later by an
  email-verification hardening spec.
- Q: If a social provider yields no usable email (e.g. Apple "Hide My Email" or
  the user declines sharing), how is the account modeled? → A: Email is optional
  (nullable) on the account; a social account is identified primarily by
  `(provider, provider subject id)`. Any relay/real email is stored when present
  but is not required.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create account and sign in with email (Priority: P1)

A new listener opens the app, registers with an email, password, and display
name, and is immediately signed in. On later visits they sign in with the same
email and password. Once signed in they can view their own profile.

**Why this priority**: Without account creation and sign-in there is no
authenticated identity, and nothing else in the product (playlists, likes,
history) can exist. This is the minimum viable slice of the whole backend.

**Independent Test**: Register a fresh email → receive access + refresh tokens
and a user object → call the profile endpoint with the access token → the
returned profile matches the registered account. Sign out of the flow, then
sign in again with the same credentials and confirm tokens are issued.

**Acceptance Scenarios**:

1. **Given** a valid app key and an unused email, **When** the user registers
   with email + password (≥ 8 chars) + display name, **Then** the system creates
   the account and returns `201` with access token, refresh token, token
   expiry, and the user object.
2. **Given** an email that already has an account, **When** the user tries to
   register with it, **Then** the system returns `409 EMAIL_ALREADY_EXISTS` and
   creates no second account.
3. **Given** an existing account, **When** the user signs in with the correct
   email and password, **Then** the system returns `200` with a fresh token set
   and user object.
4. **Given** an existing account, **When** the user signs in with a wrong
   password (or unknown email), **Then** the system returns
   `401 INVALID_CREDENTIALS` and reveals nothing about which field was wrong.
5. **Given** a valid access token, **When** the user requests their profile,
   **Then** the system returns `200` with that user's data.
6. **Given** a request with a missing or invalid app key, **When** any auth
   endpoint is called, **Then** the system returns `401 INVALID_APP_KEY` before
   processing credentials.

---

### User Story 2 - Stay signed in and sign out securely (Priority: P2)

A signed-in listener keeps using the app across days without re-entering a
password: the app silently exchanges the refresh token for a new access token
when the old one expires. When the listener signs out, that session can no
longer be used.

**Why this priority**: Real apps cannot force a password prompt every 30
minutes, and a sign-out that leaves the session usable is a security defect. This
completes the session model but depends on US1 existing first.

**Independent Test**: Sign in, wait for (or simulate) access-token expiry,
exchange the refresh token for a new access token, and confirm the new access
token works. Then sign out and confirm the same refresh token can no longer
obtain new access tokens.

**Acceptance Scenarios**:

1. **Given** a valid refresh token, **When** the app requests a refresh, **Then**
   the system returns `200` with a new token set.
2. **Given** an expired access token, **When** a protected endpoint is called,
   **Then** the system returns `401 TOKEN_EXPIRED` so the app knows to refresh.
3. **Given** an invalid, malformed, or already-revoked refresh token, **When** a
   refresh is requested, **Then** the system returns `401 TOKEN_INVALID`.
4. **Given** a signed-in session, **When** the user signs out, **Then** the
   system returns `204` and the session's refresh token is revoked.
5. **Given** a refresh token that was already used to refresh, **When** it is
   presented again, **Then** it is rejected (`401 TOKEN_INVALID`) — refresh
   tokens are single-use (rotated).

---

### User Story 3 - Sign in with Google or Apple (Priority: P3)

A listener chooses "Continue with Google" or "Continue with Apple". The app
obtains a provider token from the device SDK and sends it to the backend, which
verifies it and signs the user in — creating an account automatically on first
use.

**Why this priority**: Social sign-in materially improves conversion but the
product is usable without it; it layers onto the identity model from US1/US2.

**Independent Test**: Send a valid provider token for a first-time user → an
account is created and a token set is returned. Send a valid provider token for
the same provider identity again → the same account is reused (no duplicate).
Send an invalid provider token → rejected.

**Acceptance Scenarios**:

1. **Given** a valid, verifiable Google/Apple identity token for a new user,
   **When** social sign-in is called, **Then** the system creates the account
   and returns `200` with a token set and user object.
2. **Given** a valid identity token for a returning social user, **When** social
   sign-in is called, **Then** the system signs into the existing account
   without creating a duplicate.
3. **Given** an identity token that fails verification (bad signature, wrong
   audience, expired), **When** social sign-in is called, **Then** the system
   returns `400 SOCIAL_TOKEN_INVALID`.
4. **Given** a social identity whose email already belongs to an email/password
   account, **When** social sign-in is called, **Then** the system links to /
   signs into that existing account rather than creating a conflicting duplicate.

---

### User Story 4 - Delete my account (Priority: P3)

A listener decides to leave and deletes their account. All of their data is
removed and their sessions stop working.

**Why this priority**: Required for privacy expectations and app-store
compliance, but not needed to demonstrate core auth value.

**Independent Test**: Sign in, delete the account, then confirm the profile
endpoint and any token for that account no longer work, and the account can no
longer sign in.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** they request account deletion, **Then**
   the system returns `204` and removes the account and all data owned by it.
2. **Given** a deleted account, **When** anyone tries to sign in with its old
   credentials, **Then** sign-in fails as if the account never existed.
3. **Given** a deleted account, **When** a previously issued access token is
   used, **Then** the request is rejected.

---

### Edge Cases

- **Missing app key on every endpoint** (including register/login): rejected with
  `401 INVALID_APP_KEY` before any credential or body processing.
- **Missing user token on a protected endpoint** (`/me`, logout): rejected with
  `401 UNAUTHORIZED_USER` (distinct from `TOKEN_EXPIRED`/`TOKEN_INVALID`).
- **Malformed request body / bad email format / short password**: rejected with
  `400 VALIDATION_ERROR` in the standard error envelope.
- **Malformed request** for social sign-in — a `provider` value outside
  `{google, apple}` or a missing/blank `id_token` — is a request-shape error →
  `400 VALIDATION_ERROR`. `400 SOCIAL_TOKEN_INVALID` is reserved specifically for
  a well-formed request whose `id_token` fails provider verification
  (bad signature, wrong audience, expired).
- **Email case / whitespace**: emails are normalized so `A@B.com` and `a@b.com`
  are the same account and cannot both register.
- **Password never disclosed**: passwords never appear in any response, log,
  or error message.
- **No trust in client-declared identity**: any `user_id` supplied in a request
  body/query is ignored; the acting user is always derived from the token.
- **Concurrent duplicate registration** of the same new email: at most one
  account is created; the loser gets `409 EMAIL_ALREADY_EXISTS`.
- **Social sign-in with no email** (Apple "Hide My Email" / declined sharing):
  account is created/reused by `(provider, subject id)`; email stays null (or the
  relay email is stored if given) — the flow MUST NOT fail for lack of email.
- **Social email matches an existing email/password account**: the social
  identity is auto-linked to that account (no duplicate). Because v1 does not
  verify email/password emails, this carries an accepted "email squatting" risk,
  deferred for mitigation to a later email-verification hardening spec.
- **Same provider identity signing in twice**: reuses the one account keyed by
  `(provider, subject id)`; no second account is ever created.

## Requirements *(mandatory)*

### Functional Requirements

**App-level gate**

- **FR-001**: The system MUST require a valid app key on every endpoint,
  including anonymous auth endpoints, and MUST reject a missing/invalid key with
  `401 INVALID_APP_KEY` before processing the request body.

**Account creation & sign-in (email/password)**

- **FR-002**: The system MUST let a user register with email, password, and
  display name, and MUST return a token set plus the user object on success
  (`201`).
- **FR-003**: The system MUST enforce a minimum password length of 8 characters
  and a valid email format, returning `400 VALIDATION_ERROR` otherwise.
- **FR-004**: The system MUST reject registration with an already-registered
  email using `409 EMAIL_ALREADY_EXISTS`, treating email case-insensitively.
- **FR-005**: The system MUST let a registered user sign in with email and
  password, returning a token set plus user object (`200`), and MUST reject bad
  credentials with `401 INVALID_CREDENTIALS` without revealing which field failed.
- **FR-006**: The system MUST store passwords only in a securely hashed form and
  MUST NEVER return or log the password or its hash.

**Token lifecycle**

- **FR-007**: On successful authentication the system MUST issue a short-lived
  access token and a longer-lived refresh token, and MUST report the access
  token's expiry to the client.
- **FR-008**: The system MUST let a client exchange a valid refresh token for a
  new token set (`200`).
- **FR-009**: The system MUST rotate refresh tokens on each refresh so a refresh
  token is single-use; a reused/old refresh token MUST be rejected
  (`401 TOKEN_INVALID`).
- **FR-010**: The system MUST distinguish, on protected endpoints, between an
  expired access token (`401 TOKEN_EXPIRED`), an invalid/revoked token
  (`401 TOKEN_INVALID`), and a missing token (`401 UNAUTHORIZED_USER`).
- **FR-011**: The system MUST let a signed-in user sign out (`204`), after which
  the session's refresh token is revoked and can no longer obtain access tokens.

**Social sign-in**

- **FR-012**: The system MUST accept a provider (`google` or `apple`) and a
  provider identity token, verify the token's authenticity (signature, audience,
  expiry) server-side, and reject unverifiable tokens with
  `400 SOCIAL_TOKEN_INVALID`.
- **FR-013**: On first successful social sign-in the system MUST create an
  account; on subsequent sign-ins it MUST reuse the same account, identified
  primarily by `(provider, provider subject id)` — never creating a duplicate for
  the same provider identity.
- **FR-014**: When a verified social identity's email matches an existing
  account, the system MUST attach the social identity to / sign into that
  existing account (auto-link on provider-verified email), rather than create a
  conflicting duplicate. One account per normalized email.
- **FR-014a**: The system MUST support social accounts that have no email
  (provider withheld it): account email MAY be null, and identity/reuse is
  driven by `(provider, provider subject id)`. A relay or real email MUST be
  stored when the provider supplies one.

**Profile & deletion**

- **FR-015**: The system MUST return the authenticated user's own profile
  (`200`) and MUST NOT expose any other user's data through this endpoint.
- **FR-016**: The system MUST let the authenticated user delete their own
  account (`204`), removing the account and all data owned by it, after which
  its credentials and tokens no longer work.
- **FR-017**: The system MUST derive the acting user solely from the
  authentication token and MUST ignore any client-supplied identifier for
  authorization purposes.

**Cross-cutting: contract & error handling**

- **FR-018**: All responses MUST conform to the shapes defined in the API
  contract (`AuthTokenResponse`, `User`) for the corresponding endpoints.
- **FR-019**: All error responses MUST use the single error envelope
  `{ "error": { "code", "message" } }` with a code from the canonical catalog
  and the documented HTTP status, so clients branch on `code` rather than
  message text.
- **FR-020**: Secrets and credentials (app key, passwords, provider tokens,
  auth headers) MUST NOT appear in logs or error output.

### Key Entities *(include if feature involves data)*

- **User**: A real person's account. Attributes: normalized email — unique when
  present but **optional/nullable** (a social-only account may have no email),
  display name, securely hashed password (absent for social-only accounts),
  timestamps. Owns all future library data (cascade-deleted with the account).
- **Social Identity**: The link between a User and a verified external provider
  identity, keyed by `(provider = google/apple, provider subject id)` as the
  **primary, stable identifier**. Ensures one account per provider identity and
  enables account reuse across sign-ins even when no email is provided. When a
  verified email is present and matches an existing account, the identity attaches
  to that account (auto-link).
- **Refresh Session**: A long-lived, revocable, single-use-per-rotation token
  representing one signed-in session; can be revoked by sign-out and is
  invalidated by rotation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can go from "no account" to "signed in with a working
  session" in a single registration step (one request), receiving everything the
  client needs to make authenticated calls.
- **SC-002**: 100% of endpoints reject requests that lack a valid app key, and
  100% of protected endpoints reject requests that lack a valid user session.
- **SC-003**: After sign-out or account deletion, 0% of the revoked/removed
  session's tokens can obtain access to protected data.
- **SC-004**: A user can never read or affect another user's account data
  through these endpoints (verified by cross-account tests: 0 successful
  cross-account accesses).
- **SC-005**: Every documented failure condition returns its specified error
  code and HTTP status, verified by automated tests covering each code in the
  catalog used by this feature.
- **SC-006**: No password, provider token, or app key value appears in logs or
  responses across all tested flows.
- **SC-007**: Duplicate registration of the same email (including concurrent
  attempts) never creates more than one account. Concurrency safety is guaranteed
  by the database-level unique constraint on `email` (not by application-level
  timing), so the loser of a race receives `409 EMAIL_ALREADY_EXISTS`.

## Assumptions

- **Contract is authoritative**: `contracts/openapi.yaml` v0.1.0 and
  `.claude/api-context.md` define the exact request/response shapes, status
  codes, and error codes; this spec implements them and does not redefine them.
- **Access token lifetime** defaults to ~30 minutes and **refresh token
  lifetime** to ~30 days, both configurable via environment (not hardcoded).
  Exact values are a settings concern, not a spec-level decision.
- **Provider credentials** (Google OAuth client ID, Apple service/team/key IDs)
  and the app key are supplied via environment configuration and assumed
  available before implementation of the social and gating flows.
- **Email/password + Google + Apple** are the only sign-in methods in scope; no
  password-reset, email-verification, or multi-factor flows in this feature
  (may be added in a later spec). The absence of email verification is the
  accepted basis for the social auto-link risk noted above.
- **Social identity is keyed on `(provider, provider subject id)`**, not on
  email; email is optional on the account and only used for auto-linking to an
  existing account when the provider supplies a verified one.
- **Rate limiting and refresh-token abuse hardening** beyond basic rotation +
  revocation are deferred to BE-004 (Security Hardening).
- **Catalog and library endpoints** are out of scope; only `GET /me` and
  `DELETE /me` from the `/me/*` group are included here.
- **Single device model is not enforced**: a user may hold multiple concurrent
  sessions (multiple refresh tokens); sign-out revokes the current session only.
