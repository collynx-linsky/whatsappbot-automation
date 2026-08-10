# WABA AI — WhatsApp Business AI Platform

A multi-tenant SaaS platform where a single platform administrator manages
many independent businesses, each connecting its own WhatsApp Business
number and getting a private AI chatbot, customer CRM, conversations,
knowledge base, products, orders, staff, and analytics — fully isolated
from every other business on the platform.

> **Current status**: Foundation + multi-tenancy + authentication/RBAC are
> built and verified live. WhatsApp integration, the AI engine, RAG
> knowledge base, CRM, products/orders, marketing, and analytics are not
> built yet — see [`docs/ROADMAP.md`](docs/ROADMAP.md) for the phase plan.

---

## What's functional right now

- Super admin logs in, onboards a new business (creates a Tenant + Business
  + Business Owner user in one step), views/suspends/activates tenants.
- Business owners log in, see their own business profile, edit it.
- Strict tenant isolation: Business A cannot see or modify Business B's
  data under any circumstance — proven by an automated test suite and by
  hand against a live server (see [`docs/multi-tenancy.md`](docs/multi-tenancy.md)).
- JWT auth with refresh rotation + blacklisting, account lockout after 5
  failed logins, forgot/reset password.
- 4 fixed platform roles: Super Admin, Business Owner, Manager, Staff.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full breakdown.
In short:

```
Next.js (App Router)  <-->  Django REST Framework  <-->  PostgreSQL
     JWT in localStorage         /api/v1/...              Redis (cache, Celery broker)
```

## Technologies

| Layer | Technology |
|---|---|
| Backend | Python 3.14, Django 5.2 LTS, Django REST Framework, `djangorestframework-simplejwt` |
| Database | PostgreSQL 18 |
| Cache / Queue | Redis 7, Celery (wired, not yet used by any endpoint) |
| Frontend | Next.js 16 (App Router, Turbopack), TypeScript, Tailwind CSS v4 |
| Auth | JWT (access + rotating/blacklisted refresh tokens) |
| Containerization | Docker Compose (documented alternative — see below) |

## Project structure

```
WhatsAppBusinessAI/
├── backend/
│   ├── manage.py
│   ├── config/            # settings (base/development/production/test), urls, celery
│   ├── core/               # shared base models, tenant middleware, permissions, exceptions
│   ├── apps/
│   │   ├── accounts/        # User, JWT auth, password reset          <- built
│   │   ├── tenants/         # Tenant, Plan, onboarding                <- built
│   │   ├── businesses/      # Business                                <- built
│   │   ├── common/          # AuditLog                                <- built
│   │   └── {whatsapp,customers,conversations,messages,ai,knowledge,
│   │        products,orders,campaigns,analytics,notifications,
│   │        billing,audit}/                                            <- placeholders, see ROADMAP
│   ├── requirements/{base,development,production}.txt
│   └── tests/
├── frontend/
│   ├── app/{login,dashboard,admin}/
│   ├── components/, lib/, types/
├── infrastructure/{docker/, nginx/, scripts/}
├── docs/
├── scripts/                # PowerShell dev scripts
├── docker-compose.yml
├── .env.example
└── README.md
```

## Installation

### Prerequisites

- Python 3.14 (or 3.13+), Node 22+, PostgreSQL 18 (native service), Docker
  Desktop (for the Redis container).

### First-time setup

```powershell
cd E:\WhatsAppBusinessAI
copy .env.example .env
# edit .env: set POSTGRES_PASSWORD, SUPERADMIN_EMAIL/PASSWORD, etc.

.\scripts\setup.ps1        # venv + pip install, redis container, migrate, npm install
.\scripts\create-db.ps1    # if setup.ps1's migrate step fails on auth — creates the Postgres role/db
.\scripts\seed.ps1         # super admin + 3 sample businesses (ABC Electronics, Mambo Fashion, Kijani Foods)
.\scripts\start.ps1        # backend + celery worker + frontend, each in its own window
```

Full details, script reference, and the hybrid-vs-Docker rationale:
[`docs/development.md`](docs/development.md).

### Environment variables

See [`.env.example`](.env.example) for every key with a placeholder value —
never commit real credentials. Key groups: Django/JWT secrets, PostgreSQL,
Redis/Celery, CORS/CSRF, email, AI provider keys (unused until Phase 8),
WhatsApp Cloud API keys (unused until Phase 7), file storage, super admin
seed credentials.

### Database

Native PostgreSQL 18. `scripts\create-db.ps1` creates the role and
database from `.env`'s `POSTGRES_*` values (prompts for the `postgres`
superuser password — never stored). Migrations: `scripts\migrate.ps1` or
`python manage.py migrate` inside the backend venv. See
[`docs/database.md`](docs/database.md) for the full schema.

### Running the backend

```powershell
cd backend
.venv\Scripts\Activate.ps1
python manage.py runserver
```

### Running the frontend

```powershell
cd frontend
npm run dev
```

### Running Celery

```powershell
cd backend
.venv\Scripts\python.exe -m celery -A config.celery worker --loglevel=info --pool=solo
```

(`--pool=solo` is required on Windows.) No endpoint currently dispatches a
Celery task — this is wired for the phases that need it.

### Running with Docker

```powershell
docker compose up -d          # full stack: postgres, redis, backend, celery, frontend, nginx
docker compose up -d redis    # just Redis, for the hybrid dev setup
```

Note: Docker Desktop was unreliable to start during this build session —
see [`docs/development.md`](docs/development.md) for the hybrid-setup
rationale if you hit the same thing.

### Running tests

```powershell
.\scripts\test.ps1
```

Runs backend `pytest` (23 tests, including the tenant-isolation suite),
`manage.py check`, frontend `tsc --noEmit`, and `next build`.

## Creating a business (as super admin)

1. Log in at `/login` with your `SUPERADMIN_EMAIL`/`SUPERADMIN_PASSWORD`.
2. On `/admin`, fill in the "Onboard a New Business" form (tenant name,
   business name, owner email/name).
3. The response includes a one-time temporary password for the new
   business owner (also emailed via the console backend in dev — check the
   Django server's terminal output).

Or via the API directly:
```bash
curl -X POST http://localhost:8000/api/v1/tenants/onboard/ \
  -H "Authorization: Bearer <super admin access token>" \
  -H "Content-Type: application/json" \
  -d '{"tenant_name":"Acme Co","business_name":"Acme","owner_email":"owner@acme.test","owner_first_name":"Jane"}'
```

## Creating an AI assistant / connecting WhatsApp

Not built yet — these are Phase 7 (WhatsApp integration) and Phase 8 (AI
engine) in [`docs/ROADMAP.md`](docs/ROADMAP.md). The settings layer already
reads `WHATSAPP_*` and `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` from `.env` so
the configuration surface is ready when those phases land.

## Default development credentials

| Role | Email | Password |
|---|---|---|
| Super Admin | value of `SUPERADMIN_EMAIL` in `.env` | value of `SUPERADMIN_PASSWORD` in `.env` |
| Sample business owners (after `seed.ps1`) | `owner@abcelectronics.test`, `owner@mambofashion.test`, `owner@kijanifoods.test` | `DevPassword!2026` |

These are local-development-only, clearly fictional accounts. Never reuse
these values in a deployed environment.

## Documentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/database.md`](docs/database.md)
- [`docs/multi-tenancy.md`](docs/multi-tenancy.md)
- [`docs/security.md`](docs/security.md)
- [`docs/api.md`](docs/api.md)
- [`docs/development.md`](docs/development.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — what's built, what's next

## License

Proprietary — all rights reserved.
