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
  login. Verified live and by `tests/test_auth.py`. The same counter is
  shared with wrong MFA codes (below) — five wrong attempts of *any*
  authentication factor locks the account.
- Forgot/reset password: single-use, time-limited (1 hour)
  `PasswordResetToken`; `POST /auth/forgot-password/` always returns 200
  regardless of whether the email exists (no account-existence oracle).
- **MFA (TOTP) is required for every role, no exceptions** — see
  `docs/mfa.md` for the full design (why two intermediate "purpose"-
  tagged token types instead of a session flag, the setup/challenge
  flows, backup codes, three-tier recovery). `POST /api/v1/auth/login/`
  never returns a real access/refresh pair by itself anymore.
- Login/device visibility: `User.last_login_ip` and
  `last_login_user_agent` are recorded on every successful MFA challenge
  (`apps.accounts.views.MFAVerifyView`) — enough to notice "this login
  came from an unexpected IP/browser" without building a full session-
  management UI this phase. No concurrent-session limiting or device
  revocation list yet (flagged below).

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

## WhatsApp webhook security

See `docs/whatsapp.md` for the full picture. Summary: every webhook `POST`
requires a valid `X-Hub-Signature-256` (HMAC-SHA256 of the raw body,
`WHATSAPP_APP_SECRET`, constant-time compared) — fails **closed** if the
secret isn't configured, rather than accepting unsigned traffic. Per-tenant
WhatsApp access tokens are encrypted at rest (`core.crypto`, Fernet/AES,
key from `WHATSAPP_TOKEN_ENCRYPTION_KEY`) and never included in any API
response, proven by testing the actual rendered response body.

## Rate limiting

`REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]` (`config/settings/base.py`):
`AnonRateThrottle` + `UserRateThrottle` as a blanket DoS backstop
(`THROTTLE_RATE_ANON`/`THROTTLE_RATE_USER` in `.env`, defaulting to
`100/hour`/`3000/hour`), plus `ScopedRateThrottle` — a no-op on any view
that doesn't set `throttle_scope`, so listing it as a platform-wide
default is safe. Six views set `throttle_scope`, each independently
tunable via `.env` (`THROTTLE_RATE_<SCOPE>`):

| Scope | View | Default rate | Why |
|---|---|---|---|
| `whatsapp_webhook` | `WhatsAppWebhookView` | `120/minute` | Public, unauthenticated — signature verification (below) proves authenticity, but doesn't bound *volume*; a flood of correctly-signed requests or repeated failed-signature probing needs its own cap, separate from the shared `anon` bucket every other anonymous request (e.g. login attempts) draws from. |
| `ai_test` | `AITestView` | `20/hour` | Real provider API cost once `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` is set — see `docs/ai.md`. |
| `knowledge_upload` | `KnowledgeDocumentListCreateView` (`POST` only — `GET` deliberately excluded via `get_throttles()`, see `apps.knowledge.views`) | `30/hour` | Real embedding-provider API cost once configured — see `docs/rag.md`. |
| `campaign_send` | `CampaignSendView` | `10/hour` | Messages real customers — the most consequential action in this API, both in cost and impact. |
| `login` | `LoginView` | `30/hour` | A second, IP-keyed layer against distributed credential-stuffing, independent of the per-account lockout counter above (which only kicks in per *account*, not per source IP). |
| `mfa_verify` | `MFASetupConfirmView`, `MFAVerifyView` | `10/hour` | A 6-digit TOTP code has only 1,000,000 possibilities, repeating every 30s — this is the primary defense against brute-forcing it, on top of the shared account-lockout counter. See `docs/mfa.md`. |

**Live-verified, not just under `pytest`**: 20 real consecutive requests
to `/api/v1/ai/test/` against a running dev server (real Redis-backed
cache, not the in-memory test cache) all returned `200`; the 21st
returned a real `429` with `"Request was throttled. Expected available in
3553 seconds."`, flowing through the same error envelope as every other
exception in this API.

**Testing note for anyone extending this**: `tests/test_security.py`
overrides rates per-test via `monkeypatch.setitem(SimpleRateThrottle
.THROTTLE_RATES, scope, "1/min")`, **not** the `settings` fixture.
DRF's `SimpleRateThrottle.THROTTLE_RATES` is a plain class attribute
bound once (at Django startup, when `rest_framework.throttling` is first
imported) to the exact dict object `settings.REST_FRAMEWORK
["DEFAULT_THROTTLE_RATES"]` was at that moment — it is never re-read per
request. Reassigning `settings.REST_FRAMEWORK` later (what the `settings`
fixture naturally does) constructs a brand-new dict the already-bound
class attribute never sees, so the override silently does nothing; a
test written that way would still pass, but for the wrong reason (see
`tests/test_security.py`'s module docstring for how this was actually
caught: an early version of these tests appeared to pass while secretly
throttling on the real `20/hour`/`30/hour`/etc. production defaults
instead of the intended `1/min` override — verified by re-running the
same scenario with debug output showing the dict identity mismatch).
Also required a new `tests/conftest.py` autouse fixture
(`_clear_throttle_cache`) clearing Django's cache before every test —
`CACHES` uses `LocMemCache` in tests (persists for the whole `pytest`
process), so without it, request counts would silently accumulate across
the entire 200+-test suite and eventually trip an unrelated test.

- No "test the connection" call when a WhatsApp account is connected — a
  wrong/expired access token isn't caught until the first real send fails.

## Marketing compliance (spec sections 12, 26)

See `docs/campaigns.md` for the full picture. Summary: `Customer.marketing_opt_in`
defaults to `False` (opt-in, not opt-out) and is never set implicitly —
starting a WhatsApp conversation does not opt a customer into marketing.
`apps.campaigns.services.get_segment_customers` filters to
`marketing_opt_in=True` unconditionally (not an optional filter a segment
could omit), and `send_campaign` re-checks it a second time per recipient
at actual send time, since a customer can opt out between when a campaign
was scheduled and when it sends. Proactive sends always use
`WhatsAppCloudProvider.send_template_message` (a pre-approved template),
never `send_text_message` — the two are structurally separate provider
methods so a campaign send can't accidentally take the free-text path.

**Resolved this session**: file upload validation — `apps.knowledge`'s
`POST /api/v1/knowledge/documents/` rejects any file extension outside
`.txt`/`.pdf` with a clean `400` before it's saved to disk
(`apps.knowledge.services.validate_file_extension`), on top of the
existing transport-level `MAX_UPLOAD_SIZE_MB` bound. `MessageAttachment`
(chat media) still has no upload endpoint — that gap is specific to
`apps.messages`, not a general "file upload validation" gap anymore.

## Audit logging

`apps.common.models.AuditLog` + `AuditLog.log(...)` helper. Wired to:
user creation (signal), tenant onboarding, tenant suspend/activate,
product create/update, order creation and status changes, staff added,
every AI→human handoff (`AI_HANDOFF`, metadata records the reason —
keyword match, low confidence, provider error, or missing API key),
`AI_SETTINGS_UPDATED`, `KNOWLEDGE_DOCUMENT_UPLOADED`,
`WHATSAPP_ACCOUNT_CONNECTED`, `CAMPAIGN_SENT`, `INVOICE_GENERATED`, and
— MFA — `MFA_ENABLED` (a user completes enrollment) and `MFA_RESET`
(a Business Owner or Super Admin resets someone's MFA; metadata records
the target's email). Every future administrative action should call
`AuditLog.log(action=..., user=..., tenant=..., obj=...)` from its
service/view layer as new apps land — this is a platform-wide
requirement (spec section 19), not per-app optional.
`tests/test_security.py::TestAuditLoggingCoverage` proves each of this
phase's five new actions actually fires an `AuditLog` row, not just that
the underlying action succeeds.

## What was verified live this session

- Real JWT login/refresh/logout round-trip via `curl` against a running
  server (not just unit tests).
- Cross-tenant isolation proven with two real seeded businesses (see
  `docs/multi-tenancy.md`).
- Account lockout after 5 real failed `curl` login attempts.
- CORS preflight from `http://localhost:3000` to the live API returns the
  correct `access-control-allow-*` headers.
- A simulated WhatsApp webhook payload with a correctly-computed HMAC
  signature processed end-to-end against the live server; wrong/missing
  signatures rejected with `403`; a duplicate delivery of the same event
  proven idempotent (no duplicate message).
- Rate limiting: 20 real consecutive `/api/v1/ai/test/` requests against
  a running dev server all succeeded, the 21st returned a genuine `429`
  (see the Rate limiting section above) — against the real production
  default rate, not a test-only override.
- MFA end-to-end against a real seeded account's real TOTP secret: login
  correctly returned a `challenge_token` (never real tokens directly);
  that token correctly got `401` on a normal endpoint
  (`/api/v1/customers/`) — proving `core.authentication
  .FullAccessJWTAuthentication`'s platform-wide rejection, not just a
  per-view check; a code computed from the real stored secret via
  `pyotp` correctly returned real access/refresh tokens; the real access
  token worked against `/api/v1/auth/me/`; a wrong code correctly
  returned `400`. Full detail in `docs/mfa.md`.
