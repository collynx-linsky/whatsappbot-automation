# Security

## Authentication

- JWT via `djangorestframework-simplejwt`. Access tokens (60 min default,
  configurable via `JWT_ACCESS_TOKEN_LIFETIME_MINUTES`) carry `role` and
  `tenant_id` claims (`apps.accounts.serializers.LoginSerializer.get_token`)
  — these are set by the server at issuance, never accepted as client input.
- Refresh tokens (7 days default) rotate on use and are blacklisted after
  rotation (`ROTATE_REFRESH_TOKENS` / `BLACKLIST_AFTER_ROTATION`) —
  `token_blacklist` app is installed and migrated.
- `POST /api/v1/auth/logout/` blacklists the given refresh token explicitly.
- Passwords: Django's default PBKDF2 hasher (production), MD5 in the test
  settings only (`config/settings/test.py`, for fast tests — never used in
  dev/prod).
- Account lockout: 5 failed logins locks the account for 30 minutes
  (`User.increment_failed_login` / `is_locked`), reset on a successful
  login. Verified live and by `tests/test_auth.py`.
- Forgot/reset password: single-use, time-limited (1 hour)
  `PasswordResetToken`; `POST /auth/forgot-password/` always returns 200
  regardless of whether the email exists (no account-existence oracle).

## Authorization

- Every non-super-admin endpoint checks the caller's `role` via
  `core.permissions` (`IsStaffOrAbove`, `IsManagerOrAbove`, `IsBusinessOwner`,
  `IsSuperAdmin`, `IsTenantMember`) — see `docs/multi-tenancy.md` for how
  tenant scope itself is resolved (never from client input).
- Super admins bypass role checks (explicit spec requirement — platform
  oversight) but never bypass tenant isolation on data they don't own
  outside that oversight capacity.

## Transport / API hardening

- `django-cors-headers` — `CORS_ALLOWED_ORIGINS` is an explicit allowlist
  from `.env` (defaults to `http://localhost:3000`), `CORS_ALLOW_ALL_ORIGINS`
  is hardcoded `False`.
- `CSRF_TRUSTED_ORIGINS` likewise explicit.
- `django.middleware.security.SecurityMiddleware` on; `production.py` adds
  HSTS, `SECURE_SSL_REDIRECT`, secure cookies, `X_FRAME_OPTIONS = "DENY"`.
- Structured error envelope (`core.exceptions.custom_exception_handler`)
  never leaks a stack trace, DB error text, or internal exception message
  to the client — unhandled exceptions are logged server-side and returned
  as a generic 500.
- `DEBUG=False` is the production default; `DJANGO_SECRET_KEY`,
  `JWT_SIGNING_KEY`, and all credentials come from `.env` only — nothing is
  hardcoded in source, and `.env` is gitignored. `.env.example` documents
  every key with placeholder values.

## Secrets not yet implemented (flagged honestly)

- WhatsApp access tokens and AI provider API keys are read from `.env` into
  settings (`WHATSAPP_ACCESS_TOKEN`, `OPENAI_API_KEY`, etc.) but there's no
  `WhatsAppAccount` model yet to store *per-tenant* credentials — that
  lands in Phase 7 and per the spec must be encrypted at rest / never
  exposed via any API response.
- Rate limiting architecture (DRF throttle classes) is not wired up this
  phase — `REST_FRAMEWORK` has no `DEFAULT_THROTTLE_CLASSES` yet. Flagged
  in `docs/ROADMAP.md`.
- File upload validation (type/size checks beyond `MAX_UPLOAD_SIZE_MB`)
  lands with `apps.knowledge` (document uploads, Phase 9).

## Audit logging

`apps.common.models.AuditLog` + `AuditLog.log(...)` helper. Currently wired
to: user creation (signal), tenant onboarding, tenant suspend/activate.
Every future administrative action (product changes, order creation, AI
settings changes, staff added, campaign created, ...) should call
`AuditLog.log(action=..., user=..., tenant=..., obj=...)` from its service
layer as those apps land — this is a platform-wide requirement (spec
section 19), not per-app optional.

## What was verified live this session

- Real JWT login/refresh/logout round-trip via `curl` against a running
  server (not just unit tests).
- Cross-tenant isolation proven with two real seeded businesses (see
  `docs/multi-tenancy.md`).
- Account lockout after 5 real failed `curl` login attempts.
- CORS preflight from `http://localhost:3000` to the live API returns the
  correct `access-control-allow-*` headers.
