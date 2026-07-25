# Quickstart: Backend Foundation & Auth (BE-001)

Validation/run guide proving BE-001 works end-to-end. Implementation details live
in `tasks.md`; contract details in [`contracts/auth-endpoints.md`](contracts/auth-endpoints.md).

## Prerequisites

- Python 3.12+, PostgreSQL, Redis running locally.
- `cp .env.example .env` and fill: `DJANGO_SECRET_KEY`, `X_APP_KEY`,
  `DATABASE_URL`, `REDIS_URL`, `GOOGLE_OAUTH_CLIENT_ID`, `APPLE_CLIENT_ID`.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py runserver
```

## Automated verification (primary gate)

```bash
black --check . && ruff check . && mypy .
python manage.py makemigrations --check --dry-run
pytest                     # Google/Apple verification mocked; no live network
```

All tests in [`contracts/auth-endpoints.md`](contracts/auth-endpoints.md) and the
spec's acceptance scenarios must pass. This is the source of truth for "done".

## Manual smoke test (happy path)

Set `APP=<your X_APP_KEY>` and `BASE=http://localhost:8000`.

1. **App-key gate** — request without the key is rejected:
   ```bash
   curl -i $BASE/auth/login          # → 401 {"error":{"code":"INVALID_APP_KEY"}}
   ```
2. **Register** → expect `201` with `access_token`, `refresh_token`,
   `expires_in`, `user`:
   ```bash
   curl -s -X POST $BASE/auth/register -H "X-App-Key: $APP" \
     -H 'Content-Type: application/json' \
     -d '{"email":"a@b.com","password":"password8","display_name":"Bao"}'
   ```
3. **Duplicate register** → same body again → `409 EMAIL_ALREADY_EXISTS`.
4. **Login** → `200` `AuthTokenResponse`; wrong password → `401 INVALID_CREDENTIALS`.
5. **Profile** — with `Authorization: Bearer <access_token>`:
   ```bash
   curl -s $BASE/me -H "X-App-Key: $APP" -H "Authorization: Bearer <ACCESS>"
   # → 200 User {id, email, display_name, avatar_url:null, auth_provider:"email", created_at}
   ```
   No token → `401 UNAUTHORIZED_USER`.
6. **Refresh** → `POST /auth/refresh {refresh_token}` → `200` new tokens; reuse the
   **old** refresh token → `401 TOKEN_INVALID` (rotation).
7. **Logout** → `POST /auth/logout` (Bearer) → `204`; then refreshing that token →
   `401 TOKEN_INVALID`.
8. **Delete account** → `DELETE /me` (Bearer) → `204`; old access token now → 401;
   login with old credentials fails.

## Social sign-in verification (mocked in tests, manual = real tokens)

- Provide a valid Google/Apple `id_token` → `200`; first time creates an account,
  repeat reuses it (no duplicate).
- Invalid/expired `id_token` → `400 SOCIAL_TOKEN_INVALID`.
- Apple token with no email → account created, `User.email` is `null`, flow succeeds.

## Expected outcomes (maps to Success Criteria)

- Every endpoint rejects missing app key; every `/me/*`+logout rejects missing
  session (SC-002).
- Revoked/deleted sessions grant no access (SC-003).
- Each documented error code is reproducible (SC-005).
- No password/token/app-key value appears in server logs during the flow (SC-006).
