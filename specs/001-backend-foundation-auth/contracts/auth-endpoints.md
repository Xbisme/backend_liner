# Contract: Auth & Account Endpoints (BE-001)

**Authoritative source**: [`contracts/openapi.yaml`](../../../contracts/openapi.yaml)
(v0.1.0 draft) + [`.claude/api-context.md`](../../../.claude/api-context.md).
This file is the **contract-test checklist** for BE-001 — every row below MUST
have an automated test asserting the status code, error `code`, and response
shape. It does not redefine the contract; it enumerates what to verify.

## Common rules (all endpoints)

- **`X-App-Key` required on every endpoint.** Missing/invalid → `401` +
  `{ "error": { "code": "INVALID_APP_KEY" } }` (checked before body parsing).
- All error bodies use the envelope `{ "error": { "code", "message" } }`
  (`ErrorResponse`). Clients branch on `code`.
- `/me` and `/auth/logout` additionally require `Authorization: Bearer <access>`.

## Endpoints in scope

| Method & path | Auth | Success | Request → Response | Error cases (code / HTTP) |
|---|---|---|---|---|
| `POST /auth/register` | AppKey | `201` `AuthTokenResponse` | `RegisterRequest{email,password≥8,display_name}` → tokens+user | `EMAIL_ALREADY_EXISTS`/409 · `VALIDATION_ERROR`/400 · `INVALID_APP_KEY`/401 |
| `POST /auth/login` | AppKey | `200` `AuthTokenResponse` | `LoginRequest{email,password}` → tokens+user | `INVALID_CREDENTIALS`/401 · `VALIDATION_ERROR`/400 |
| `POST /auth/social-login` | AppKey | `200` `AuthTokenResponse` | `SocialLoginRequest{provider,id_token}` → tokens+user (create-if-new) | `SOCIAL_TOKEN_INVALID`/400 · `VALIDATION_ERROR`/400 |
| `POST /auth/refresh` | AppKey | `200` `AuthTokenResponse` | `RefreshTokenRequest{refresh_token}` → new tokens | `TOKEN_INVALID`/401 (invalid/revoked/rotated) |
| `POST /auth/logout` | AppKey + Bearer | `204` (no body) | — → refresh token revoked | `UNAUTHORIZED_USER`/401 · `TOKEN_EXPIRED`/401 · `TOKEN_INVALID`/401 |
| `GET /me` | AppKey + Bearer | `200` `User` | — → own profile | `UNAUTHORIZED_USER`/401 · `TOKEN_EXPIRED`/401 |
| `DELETE /me` | AppKey + Bearer | `204` (no body) | — → account + owned data removed | `UNAUTHORIZED_USER`/401 |

## Response shape assertions

- **`AuthTokenResponse`** = `{ access_token, refresh_token, expires_in, user }`.
  `expires_in` = access-token lifetime in **seconds** (derived from
  `ACCESS_TOKEN_LIFETIME`). `user` = `User`.
- **`User`** = `{ id:int, email:string|null, display_name, avatar_url:null,
  auth_provider: email|google|apple, created_at }`. MUST NOT include `password`,
  `is_staff`, or internal flags.
  - `email` may be `null` for social-only accounts.
  - `auth_provider` derived: `email` if the account has a usable password, else
    the provider of its social identity.
  - `avatar_url` is `null` in BE-001 (no avatar feature yet).

## Behavior assertions beyond shape (map to spec FRs)

- Register with an existing email (case-insensitive) → `409 EMAIL_ALREADY_EXISTS`,
  no second account (FR-004).
- Login wrong password vs unknown email → both `401 INVALID_CREDENTIALS`, message
  identical (no user enumeration) (FR-005).
- Refresh rotates: old refresh token reused → `401 TOKEN_INVALID` (FR-009).
- Expired access token on `/me` → `401 TOKEN_EXPIRED`; missing token →
  `401 UNAUTHORIZED_USER`; garbage token → `401 TOKEN_INVALID` (FR-010).
- Logout → `204`, then that refresh token → `401 TOKEN_INVALID` on refresh (FR-011).
- Social first-time → account created; same `(provider, subject_id)` again →
  same account, no duplicate (FR-013).
- Social email == existing account email → auto-linked, no duplicate (FR-014).
- Social with no email → account created/reused, `email` null, no failure (FR-014a).
- Social with a `provider` outside `{google,apple}` or missing/blank `id_token`
  → `400 VALIDATION_ERROR` (request-shape). `SOCIAL_TOKEN_INVALID` is only for a
  well-formed request whose token fails verification.
- `DELETE /me` → `204`; afterwards old access token → 401 and credentials can't
  sign in (FR-016 / SC-003).
- No password / token / app-key value in any response or log (FR-020 / SC-006).
