# Development Guide

## Stack & versions actually used

- Python 3.14.5, Django 5.2.5 LTS, DRF 3.15.2, `djangorestframework-simplejwt`
- PostgreSQL 18 (native Windows service)
- Redis 7 (Docker container — hybrid setup, see below)
- Node 22, Next.js 16.3 (App Router, Turbopack — stable by default in v16), TypeScript, Tailwind CSS v4

## Why hybrid (native Postgres + Docker-only Redis) instead of full Docker Compose

This machine has PostgreSQL 18 already installed and running as a native
Windows service, and Docker Desktop has been observed to be slow/unreliable
to start on this machine (in one session, Docker never came up in 25+
minutes of the session). Running Postgres/backend/frontend natively means
fast hot-reload and no dependency on Docker Desktop's mood. Redis has no
first-class native Windows build, so it's the one piece that stays in a
container: `docker compose up -d redis`.

The full containerized stack (`docker-compose.yml` at the project root —
postgres, redis, backend, celery_worker, celery_beat, frontend, nginx) is
still there and fully configured, as the documented alternative / for
production-parity testing. It uses host port `5433` for Postgres
specifically so it doesn't collide with the native instance if you bring
both up at once.

**If Docker Desktop is being slow**: give it a few minutes and retry
`docker info`. If it still won't come up, you can develop everything except
whatever actually needs Redis (Celery tasks — none of this phase's
endpoints touch Celery, so backend/frontend/auth all work with Redis down).

## First-time setup

```powershell
cd E:\WhatsAppBusinessAI
.\scripts\setup.ps1          # venv, deps, .env, redis container, migrate, npm install
.\scripts\create-db.ps1      # only if setup.ps1's migrate step fails with an auth/connection error
.\scripts\seed.ps1           # super admin + 3 sample businesses
.\scripts\start.ps1          # backend + celery worker + frontend, each in its own window
```

`create-db.ps1` prompts for the native `postgres` superuser password
interactively (not stored anywhere) and creates the `waba_user` role +
`whatsapp_business_ai` database from the `POSTGRES_*` values in `.env`.

## Day-to-day scripts (`scripts/`)

| Script | Does |
|---|---|
| `setup.ps1` | First-time environment bring-up (see above). |
| `start.ps1` | Opens 3 windows: Django `runserver`, Celery worker (`--pool=solo`, required on Windows), `next dev`. |
| `stop.ps1` | Kills processes matching this project's `manage.py runserver` / `celery` / `next dev` command lines. |
| `migrate.ps1` | `makemigrations` + `migrate`. |
| `seed.ps1` | `createsuperadmin` + `seed_dev_data` management commands. |
| `test.ps1` | Backend `pytest` + `manage.py check` + frontend `tsc --noEmit` + `next build`. |
| `lint.ps1` | `ruff check`, `black --check`, `isort --check`, `eslint`. |
| `format.ps1` | `isort`, `black`, `eslint --fix`. |
| `backup-db.ps1` | `pg_dump` to `backups/` (gitignored), prunes old backups. See `docs/backup-recovery.md`. |
| `restore-db.ps1` | **Destructive** — restores from a `backup-db.ps1` dump. Requires `-Force` + typed confirmation. |

All of these were run for real against a live database this session — not
just written and assumed to work.

## Backend conventions

- One Django app per domain under `backend/apps/`, `backend/core/` for
  shared base layer — see `docs/architecture.md`.
- New tenant-scoped models inherit `core.models.BaseModel`.
- New views enforce tenant scope by filtering on `request.user.tenant_id`
  directly (see `apps/businesses/views.py:TenantScopedQuerysetMixin`) —
  never by trusting an id from the URL/body/header. See
  `docs/multi-tenancy.md`.
- `ruff`/`black`/`isort` config lives in `backend/pyproject.toml`. isort
  uses `profile = "black"` so the two tools don't fight each other over
  import formatting; ruff's own import-sort rule (`I`) is deliberately
  disabled since isort already owns that job.
- API errors always go through `core.exceptions.custom_exception_handler` —
  don't return ad-hoc error shapes from a view.
- Tests: `pytest` + `pytest-django`, settings module `config.settings.test`
  (locmem cache/email, no Redis dependency, MD5 password hasher for speed).
  `backend/tests/conftest.py` has the shared fixtures
  (`tenant_a`/`tenant_b`/`super_admin`/`auth_client` helper).

## Frontend conventions

- No server-side session — JWTs live in `localStorage`
  (`frontend/lib/auth.ts`). `frontend/lib/api.ts` is the one place that
  calls `fetch()` against the backend; it retries once on 401 after a
  silent token refresh.
- Route guarding is a client-side effect
  (`frontend/lib/useAuth.ts:useRequireAuth`), not Next.js
  middleware/proxy — there's no server-visible session to check, and this
  app has no dynamic route segments yet where the async-`params` change in
  Next.js 16 would matter. If a later phase adds server-rendered
  tenant-specific pages, revisit this.
- Next.js 16 specifics that matter here: Turbopack is the default for both
  `dev` and `build` (no flag needed); `middleware.ts` is renamed to
  `proxy.ts` (not used yet); `params`/`searchParams` in `page.tsx` are
  Promises (not used yet — no dynamic segments this phase).
- ESLint's `react-hooks/set-state-in-effect` rule is stricter than before —
  two call sites in this codebase (`useAuth.ts`, `admin/page.tsx`) have
  justified inline `eslint-disable` comments explaining why (localStorage
  read must happen post-mount; async data-fetch-on-mount is the documented
  effect use case). Read the comment before copying the pattern elsewhere.

## Encoding gotcha (Windows PowerShell 5.1)

Windows PowerShell 5.1 (`powershell.exe`, not PowerShell 7) reads `.ps1`
files without a BOM using the system codepage, not UTF-8. An em-dash or
curly quote written into a script file renders as mojibake and can produce
genuine parse errors depending on where it lands. All scripts in
`scripts/` are kept plain-ASCII for this reason — keep it that way if you
edit them.

## Default local URLs

- Backend API: http://localhost:8000/api/v1/
- API docs: http://localhost:8000/api/docs/
- Django admin: http://localhost:8000/admin/
- Frontend: http://localhost:3000/
