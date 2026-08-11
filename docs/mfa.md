# Multi-Factor Authentication (MFA)

`apps.accounts.mfa` — TOTP-based MFA, **required for every role, no
exceptions** (an explicit platform decision — see the master security
enhancement priorities this phase implements). Login by email+password
alone is no longer sufficient for anyone, including Super Admin.

## Why two intermediate token types, not a session flag

The obvious-looking alternative — issue a real access token at login,
just flip a `mfa_verified=False` flag somewhere and check it on every
view — doesn't hold up: nearly every view in this codebase sets its own
explicit `permission_classes`, so a check living only in a permission
class would need to be added to every single view individually, and one
missed view is a full MFA bypass. Instead:

- `POST /api/v1/auth/login/` (password correct) mints a short-lived
  (10 min), narrowly-scoped JWT carrying a `purpose` claim — `"mfa_setup"`
  if the user has never enrolled, `"mfa_challenge"` if they have — and
  returns *that*, never a real access/refresh pair.
- `core.authentication.FullAccessJWTAuthentication` — the platform-wide
  default (`REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`) — refuses
  to authenticate *any* token carrying a `purpose` claim, full stop. This
  is enforced at the authentication layer, which every request passes
  through regardless of a view's permission classes — the one place a
  blanket rule actually reaches every endpoint in this codebase.
- The three MFA endpoints (`mfa/setup/`, `mfa/setup/confirm/`,
  `mfa/verify/`) explicitly opt back into plain
  `rest_framework_simplejwt.authentication.JWTAuthentication` (which
  doesn't care about `purpose`) and layer `core.permissions.IsMFAPending`
  on top, which checks the token's `purpose` claim matches exactly what
  that specific endpoint expects (`view.mfa_purpose`) — a setup token
  can't call verify, a challenge token can't call setup, and a real
  access token (no `purpose` claim at all) can't call either.

Proven, not just asserted: `tests/test_mfa.py::TestMFATokenPurposeIsolation`
covers all four directions, including a purpose-tagged token attempted
against an ordinary endpoint (`/api/v1/customers/`) — live-verified too,
see below.

## The two flows

```text
POST /api/v1/auth/login/  {email, password}
   |  password correct
   v
user.mfa_enabled?
   |                                    |
   NO                                   YES
   v                                    v
{mfa_setup_required, setup_token}    {mfa_required, challenge_token}
   |                                    |
   v                                    v
POST /api/v1/auth/mfa/setup/          POST /api/v1/auth/mfa/verify/
  -> {secret, provisioning_uri}         {code} or {backup_code}
   |                                    |
   v                                    v
POST /api/v1/auth/mfa/setup/confirm/  code/backup_code valid?
  {code}                                |
   |                                    v
   v                              {access, refresh}  <- real tokens
code valid?
   |
   v
mfa_enabled=True, 10 backup codes
generated (shown ONCE), {access,
refresh, backup_codes}  <- real tokens
```

Wrong code at either `setup/confirm/` or `verify/` increments the same
`User.failed_login_attempts`/`locked_until` counter a wrong password
does (`User.increment_failed_login`) — five wrong attempts of *any*
authentication factor locks the account for 30 minutes, same as before
MFA existed. Paired with tight rate limiting
(`THROTTLE_RATE_MFA_VERIFY`, default `10/hour`, see `docs/security.md`)
— a 6-digit TOTP code has only 1,000,000 possibilities, repeating every
30 seconds, so both defenses matter independently.

## QR codes: the API returns a URI, not an image

`POST /api/v1/auth/mfa/setup/` returns `provisioning_uri` (an
`otpauth://totp/...` URI, RFC-standard, what every authenticator app
scans) and the raw `secret` (for manual entry when scanning isn't
convenient). Rendering that URI as an actual QR code image is left to
the frontend (e.g. `qrcode.react` or similar) — this API has no image-
generation dependency for it, keeping the backend surface simple; the
URI is everything a QR-rendering library needs.

## Backup codes

10 single-use recovery codes, generated once `POST
/api/v1/auth/mfa/setup/confirm/` succeeds, returned in that one response
— **never retrievable again** afterward, only their SHA-256 hash is
stored (`accounts.MFABackupCode.code_hash`; a fast hash is the right
tool here, these are high-entropy random single-use codes, not
low-entropy passwords someone needs to remember). Each one is consumed
(`used_at` stamped) the moment it's used at `mfa/verify/`, and a used
code is rejected if resubmitted (`tests/test_mfa.py::TestMFAChallengeFlow
::test_verify_with_backup_code_issues_tokens_and_consumes_it` proves
both halves — first use succeeds, second use of the same code fails).

## Recovery when it goes wrong

Three tiers, matching how bad the situation actually is:

1. **Lost the device, still have backup codes** — self-service via
   `POST /api/v1/auth/mfa/verify/ {"backup_code": "..."}` instead of
   `{"code": "..."}`. No admin involved.
2. **Lost the device AND the backup codes** —
   `POST /api/v1/staff/{id}/mfa-reset/`: a Business Owner can reset a
   Manager/Staff member's MFA within their own tenant; a Super Admin can
   reset *any* user's (including a Business Owner's) for cross-tenant
   support. Clears `mfa_enabled`/the secret/all backup codes — the
   target fully re-enrolls (new secret, new QR, new backup codes) on
   their next login. A Business Owner still cannot reset another
   tenant's owner or a Super Admin this way (`ValidationError`, tested).
3. **The Super Admin themselves is locked out** — nobody above them to
   reset it via the API. `python manage.py reset_mfa <email>` is the
   documented break-glass path: requires shell/server access, which is
   the appropriate bar for resetting the platform's most privileged
   account's second factor.

Every reset (`MFA_RESET`) and every successful enrollment (`MFA_ENABLED`)
writes an `AuditLog` row — see `docs/security.md`.

## Seed data: MFA is real here too

`seed_dev_data` and `createsuperadmin` don't hardcode a shared secret
across every seeded account (that would be a real, if dev-only, security
shortcut) — each seeded user gets a genuine random TOTP secret,
enrolled the same way a real user would be, with the secret,
provisioning URI, and backup codes printed to the console **once** so
you can actually add the account to a real authenticator app (or compute
codes with `pyotp` for scripting/`curl`). Idempotent — re-running either
command never re-enrolls or reprints for a user who's already enrolled.

## Testing without a real authenticator app

TOTP is fully deterministic (HMAC over a shared secret + the current
time step) — no external device or human is needed to test it for real.
`tests/conftest.py`'s `auth_client()` helper (used by essentially every
authenticated test in this suite) transparently completes whichever flow
applies — first-time enrollment or an already-enrolled challenge —
computing valid codes with `pyotp.TOTP(secret).now()`, so all 237 tests
in this suite exercise the *real* MFA-required login path, not a
weakened test-only bypass. `enroll_mfa(user)` pre-enrolls a user directly
(bypassing the API round trip) for tests that want an already-enrolled
user without enrollment itself being part of what's under test.

**Also verified live** against a running dev server with a real seeded
account's real secret: login correctly returned a `challenge_token`
(not real tokens); that token correctly got `401` against a normal
endpoint (`/api/v1/customers/`); a code computed from the real stored
secret via `pyotp` correctly returned real access/refresh tokens; the
real access token worked against `/api/v1/auth/me/`; a wrong code
correctly returned `400`.

## Limitations / not built

- No SMS/email-based MFA option — TOTP only. Reasonable for an MVP (no
  SMS gateway credentials exist this session anyway, consistent with
  every other "no external credentials" constraint), but a future phase
  could add it as an alternative factor.
- No "remember this device for 30 days" — every login requires a fresh
  MFA challenge, no trusted-device cookie/token exists.
- No self-service "regenerate my backup codes" endpoint — only the
  initial batch at enrollment. A lost-codes-but-not-device user currently
  has no way to get a fresh batch without a full MFA reset (tier 2
  above), which also invalidates their existing TOTP enrollment
  unnecessarily. Worth adding if this becomes a real support burden.
- `MFASetupView` regenerating a secret on repeat calls (rather than
  returning the same unconfirmed one) means switching authenticator apps
  mid-setup silently invalidates whatever was scanned first — not
  surfaced as an explicit warning anywhere in the API response.
