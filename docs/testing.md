# Testing

This project has three independent test layers. Each one catches a
different class of bug — none of them is a superset of another.

| Layer | What it runs | What it catches | Needs a live server? |
|---|---|---|---|
| Backend `pytest` | Real Django/DRF code against a real test DB | Business logic, tenant isolation, RBAC, model constraints | No (spins up its own test DB) |
| Frontend Vitest (`npm run test`) | Components/pages in `jsdom`, API calls mocked | Rendering logic, conditional UI (role gating, empty states), prop wiring | No |
| Frontend Playwright (`npm run test:e2e`) | A real Chromium browser against the real running app **and** real running backend | The actual HTTP contract, real navigation, things no mock can catch (a real empty-body response crashing a `.json()` call, a redirect that never fires) | **Yes — both frontend and backend** |

Playwright is the layer that closes the gap every earlier frontend session
in `docs/ROADMAP.md` flagged: "no browser-automation tool available, so
nothing was actually clicked through." It found a real bug on the first
real run — see below.

## Running the tests

**Backend + frontend unit/component tests** (no servers needed):

```powershell
.\scripts\test.ps1
```

Or individually:

```powershell
cd backend && .venv\Scripts\python.exe -m pytest -v
cd frontend && npm run test          # Vitest, one-shot
cd frontend && npm run test:watch    # Vitest, watch mode
```

**End-to-end (Playwright)** — needs both servers running first:

```powershell
# Terminal 1
cd backend
.venv\Scripts\Activate.ps1
python manage.py runserver

# Terminal 2 (only needed once, or after a DB reset — see below)
cd backend
.venv\Scripts\python.exe manage.py provision_e2e_user

# Terminal 3
cd frontend
npm run test:e2e          # headless
npm run test:e2e:ui       # Playwright's interactive UI mode
```

Playwright starts (or reuses) the frontend dev server itself via its
`webServer` config in `playwright.config.ts` — it has no way to start
Django, matching this project's existing hybrid dev-setup convention (see
`docs/development.md`).

## The E2E test accounts

Playwright needs **real, already-MFA-enrolled** accounts to log in as —
this platform has mandatory MFA for every role, no exceptions (see
`docs/mfa.md`), so there's no way to skip that step and still be testing
the real login flow.

`manage.py provision_e2e_user` creates (or resets) two fixed accounts:

- **A Business Owner** ("E2E Test Co", a dedicated tenant/business
  separate from the `seed_dev_data` sample businesses, so e2e runs never
  touch or depend on seeded data that might change) — this is who the
  `authenticated` Playwright project and `global-setup.ts` log in as.
- **A Super Admin** (`e2e-admin@wabaai.local`, deliberately separate from
  the real `SUPERADMIN_EMAIL` account `createsuperadmin` manages) — exists
  so authenticated coverage (Playwright specs, or ad-hoc visual-QA
  screenshots) can reach `/admin`, which the business-owner account
  correctly cannot.

Both have MFA already enrolled against their own **known** TOTP secret.
The emails/passwords/secrets are fixed, non-production, dev-only values —
the same "documented dev-only credential" pattern this project already
uses for `SUPERADMIN_EMAIL`/`SUPERADMIN_PASSWORD` (see the README's
"Default development credentials"). They live in exactly two places, which
must stay in sync:

- `backend/apps/accounts/management/commands/provision_e2e_user.py`
- `frontend/e2e/testUser.ts`

`e2e/global-setup.ts` drives the **real** `/login` → `/login/mfa-verify`
UI flow once per test run (typing the email/password, then computing a
valid 6-digit code from the known secret via the `otpauth` npm package and
typing that too) — not a shortcut through `localStorage` — then saves the
resulting session via Playwright's `storageState` so every test in the
`authenticated` project reuses it instead of logging in per spec. The
`unauthenticated` project (login-page and route-guard specs) deliberately
gets no stored session.

Re-run `provision_e2e_user` any time the dev database is reset or
re-seeded — it's idempotent and safe to run repeatedly.

## A real bug this caught, first run

The very first real Playwright run (not a contrived example — this
happened while building this test suite) caught a genuine bug that
`tsc`/`eslint`/`next build`/Vitest all missed:

`POST /api/v1/auth/logout/` returns `205 Reset Content` with an empty
body. `apiFetch()` in `lib/api.ts` only special-cased `204` before calling
`res.json()` — so logout crashed on `res.json()` with "Unexpected end of
JSON input". There was no `try/catch` around that call in `logout()` or in
`DashboardShell`'s click handler, so the exception surfaced as an
unhandled `pageerror` and `router.push("/login")` never ran. The session
*was* still cleared client-side (it happens in a `finally` block), but the
user was silently stranded on `/dashboard` instead of being redirected —
a real, live UX bug no mocked-API component test could have caught, since
a mock never returns a body-less response unless you think to simulate
one.

Fixed by having `apiFetch` (and `pendingTokenFetch`) read the response as
text first and only `JSON.parse` it if non-empty, instead of assuming
every non-204 response has a JSON body.

## What each layer intentionally does NOT cover

- Vitest tests use mocked API responses — they prove the component logic
  is correct *given* a response shape, not that the backend actually
  returns that shape. Cross-checking against the real backend is done by
  hand each frontend session (see the "Verified live" notes throughout
  `docs/ROADMAP.md`) and, now, by Playwright.
- Playwright's dashboard specs mostly hit **empty states** (the E2E test
  tenant has no seeded conversations/products/customers) — they prove a
  page mounts and fetches without crashing, not that populated data (bar
  proportions, table sorting, pagination) renders correctly. That's
  Vitest's job with deliberately-crafted mock data instead.
- Neither layer does visual regression testing (pixel-diffing a
  screenshot) — Playwright's `screenshot: "only-on-failure"` setting is
  for debugging a failure, not for catching a CSS regression that doesn't
  also break a functional assertion.

## Manual visual QA still finds real bugs neither automated layer catches

During the "premium enterprise transformation" pass (see
`docs/frontend-design-system.md`), a manual round of real screenshots —
every page, light and dark, desktop and mobile, taken with Playwright but
*read*, not just asserted against — caught three real bugs that the full
automated suite (Vitest + Playwright + tsc + eslint, all green) missed
entirely:

1. A pluralization bug (`"replyies"` instead of `"replies"`) — no test
   asserted the exact hint text, so a passing suite said nothing about it.
2. Stale placeholder copy on the dashboard ("the AI settings and
   knowledge base modules land in the next build phases") left over from
   before those modules existed — a test would only catch this if someone
   had first noticed it was wrong and wrote an assertion against it.
3. A real mobile usability bug: the Inbox's two-pane layout didn't adapt
   below `lg`, squeezing the message thread into an unusable ~70px sliver
   on a 390px phone. No page-level horizontal overflow occurred (confirmed
   via `document.body.scrollWidth`), so nothing an automated layout-overflow
   check would catch either — the container's own `overflow-hidden` just
   silently clipped the content instead.

None of these are gaps in the test suite's design — they're the category
of bug that fundamentally requires a human (or a careful visual pass) to
notice something is *wrong*, not just that nothing *crashed*. Automated
tests prove the app doesn't break; they don't prove it reads correctly or
looks right. Both are needed.
