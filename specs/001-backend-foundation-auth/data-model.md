# Data Model: Backend Foundation & Auth (BE-001)

**Date**: 2026-07-25 · Derived from [spec.md](spec.md) Key Entities + FRs.

All models live in `apps/accounts/models.py` except refresh-token state, which is
provided by SimpleJWT's `token_blacklist` app (no custom model).

## Entity: User

`accounts.User` — a real person's account. Set `AUTH_USER_MODEL = "accounts.User"`
from the first migration.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | integer | PK, `BigAutoField` | **Contract mandates `integer`** (`openapi.yaml` `User.id`); do not change to UUID without a contract change + Contract Sync |
| `email` | Email | `unique=True, null=True, blank=True` | Optional (social-only may lack it); unique when present (Postgres NULLs distinct); normalized lowercase |
| `display_name` | Char(≤150) | required, non-empty | Shown in UI; comes from register body or provider profile |
| `password` | Char (hash) | nullable (unusable for social-only) | Argon2id hash via `set_password`; never serialized |
| `is_active` | Bool | default True | Deactivate without delete if ever needed |
| `is_staff` | Bool | default False | Django admin access only |
| `date_joined` | DateTime | auto add | |
| `updated_at` | DateTime | auto update | |

- `USERNAME_FIELD = "email"`, `REQUIRED_FIELDS = ["display_name"]`.
- Custom `UserManager.create_user(email, password, display_name, **extra)` and
  `create_superuser(...)`; both normalize email; `create_user` allows
  `email=None` for social-only accounts.
- **Validation**: email format + uniqueness (→ `EMAIL_ALREADY_EXISTS` on
  register conflict); password min length 8 enforced at the serializer
  (→ `VALIDATION_ERROR`).
- **Serialized `User` shape** (must match `contracts/openapi.yaml` `User`):
  exposes public profile fields only (`id`, `email`, `display_name`, and
  created timestamp per contract) — never `password`, `is_staff`, or internal flags.
- **Deletion**: `DELETE /me` removes the row; all owned data
  (`SocialIdentity`, and future library rows) cascade via FK `on_delete=CASCADE`.

## Entity: SocialIdentity

`accounts.SocialIdentity` — links a `User` to a verified external provider
identity. The **primary, stable key** for social accounts.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | integer | PK, `BigAutoField` | Internal model (not in contract); default pk is fine |
| `user` | FK → User | `on_delete=CASCADE`, `related_name="social_identities"` | Owner |
| `provider` | Char (choices) | `{"google","apple"}` | Provider enum |
| `subject_id` | Char | required | Provider `sub` claim (stable across sign-ins) |
| `email_at_provider` | Email | `null=True, blank=True` | Real/relay email if provider supplied one |
| `created_at` | DateTime | auto add | |

- **Uniqueness**: `UniqueConstraint(fields=["provider", "subject_id"])` — one
  account per provider identity (FR-013). A user may have multiple identities
  (e.g. both google and apple) → multiple rows, same `user`.
- **Linking rule (FR-014)**: on social sign-in, resolve in this order:
  1. Existing `SocialIdentity` with `(provider, subject_id)` → use its `user`.
  2. Else, if the verified token has an email matching an existing `User.email`
     → attach a new `SocialIdentity` to that user (auto-link).
  3. Else → create a new `User` (email = provider email if present, else null)
     and a `SocialIdentity`.

## Refresh-token state (SimpleJWT `token_blacklist`)

No custom model. Enable `rest_framework_simplejwt.token_blacklist` in
`INSTALLED_APPS` (adds `OutstandingToken`, `BlacklistedToken` tables).

- **Rotation** (`ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=True`):
  each refresh issues a new refresh token and blacklists the presented one →
  single-use refresh (FR-009).
- **Logout** (FR-011): blacklist the presented refresh token
  (`RefreshToken(token).blacklist()`).
- **Account deletion**: the user FK on outstanding tokens is removed with the
  user; regardless, access tokens fail because the user lookup returns nothing
  (FR-016 / SC-003).

## Relationships

```
User 1 ──── * SocialIdentity        (CASCADE on user delete)
User 1 ──── * OutstandingToken      (SimpleJWT; CASCADE on user delete)
User 1 ──── * [future: Playlist, LikedTrack, ListeningHistory]  (BE-003)
```

## State & lifecycle notes

- A `User` may be: email/password-only (password set, ≥0 identities),
  social-only (password unusable, ≥1 identity, email maybe null), or hybrid
  (password set + ≥1 identity via auto-link).
- Access token: stateless, short-lived; validity ends at expiry or when the
  user row disappears.
- Refresh token: stateful via blacklist; validity ends at expiry, rotation, or
  logout.

## Index summary

- `User.email` unique index (nulls distinct).
- `SocialIdentity (provider, subject_id)` unique composite.
- `SocialIdentity.user` FK index (default).
