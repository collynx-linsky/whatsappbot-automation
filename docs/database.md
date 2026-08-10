# Database

PostgreSQL 18 (native, hybrid dev setup — see `docs/development.md`).
UUID primary keys throughout (not sequential integers, not random strings
used as a substitute for real foreign keys).

## Models built this phase

### `tenants.Plan`
Database-configurable subscription plan (spec section 24 — plans are never
hardcoded in code). Usage limits (`max_users`, `max_whatsapp_accounts`,
`max_ai_messages_per_month`, `max_customers`, `max_campaigns_per_month`,
`max_storage_mb`) are plain integer fields; `0` means unlimited. Only the
shape exists yet — nothing currently *enforces* these limits (that's
`apps.billing`, a later phase).

### `tenants.Tenant`
The multi-tenancy isolation boundary. Fields: `id`, `name`, `slug`
(auto-generated + de-duplicated on save), `status`
(`trial|active|suspended|cancelled`), `plan` (FK, nullable), `trial_ends_at`,
`subscription_ends_at`, timestamps.

### `businesses.Business`
The actual WhatsApp business profile — FK'd to `Tenant` (spec explicitly
lists Tenant and Business as separate models). A tenant can in principle
own more than one business; the onboarding flow currently creates exactly
one per tenant. Fields match spec section 7 exactly: `name`, `legal_name`,
`description`, `category`, `phone`, `email`, `website`, `address`, `city`,
`country`, `timezone`, `currency`, `logo`, `opening_hours` (JSON).

### `accounts.User`
Custom user model (`AUTH_USER_MODEL = "accounts.User"`), email login (no
username field), UUID pk. `role` is one of the 4 fixed platform roles —
`super_admin | business_owner | manager | staff` — not a dynamic
role-assignment table; the spec names exactly these 4 roles with fixed
capabilities. A DB `CheckConstraint` (`super_admin_has_no_tenant`) enforces
that super admins never have a `tenant_id` and non-super-admins always do.
Also carries account-lockout bookkeeping (`failed_login_attempts`,
`locked_until` — 5 failures locks for 30 minutes) and
`accounts.PasswordResetToken` for the forgot/reset-password flow.

### `common.AuditLog`
Platform-wide audit trail (spec section 19): `tenant`, `user`, `action`
(free-text code, e.g. `USER_CREATED`, `BUSINESS_ONBOARDED`,
`TENANT_SUSPENDED`), a generic FK to the affected object, `metadata` (JSON),
`ip_address`, `created_at`. `AuditLog.log(...)` is the write helper —
services in later phases call it rather than writing `AuditLog.objects.create(...)`
directly.

## Base model layer (`backend/core/models.py`)

Every future tenant-scoped domain model (customers, conversations,
products, orders, ...) should inherit `core.models.BaseModel`, which
combines:

- `TimeStampedModel` — `created_at` / `updated_at`
- `SoftDeleteModel` — `is_deleted` / `deleted_at` / `deleted_by`, plus
  `.objects` (excludes soft-deleted) and `.all_objects` managers
- `TenantAwareModel` — a `tenant` FK and a `TenantAwareManager` with a
  `.for_tenant(tenant)` helper (does **not** auto-filter every query — see
  `docs/multi-tenancy.md` for why)
- `AuditedModel` — `created_by` / `updated_by`
- UUID primary key, default ordering `-created_at`

`Tenant`, `Plan`, `Business`, and `User` themselves don't inherit
`BaseModel` (a tenant can't be tenant-scoped to itself, and `User` has its
own auth-specific base classes) — everything built from Phase 4 onward
(customers, conversations, products, ...) should.

## Migrations

Standard Django migrations, one app per domain
(`backend/apps/<app>/migrations/`). Run `scripts\migrate.ps1` (or
`python manage.py makemigrations && python manage.py migrate` inside the
venv). No manual SQL — all schema changes go through migrations.

## Indexes & constraints in place

- `Tenant.slug`, `User.email` — unique
- `User`: composite indexes on `(tenant, is_active)` and `(tenant, role)`
- `Business`: composite index on `(tenant, is_active)`
- `AuditLog`: composite index on `(tenant, action, created_at)`
- `Plan.slug`, `Tenant.slug` — unique, auto-slugified

## Local database credentials (this machine)

Native PostgreSQL 18, database `whatsapp_business_ai`, role `waba_user`
(created via `scripts\create-db.ps1`, which prompts for the `postgres`
superuser password — never stored in any file). Actual credentials for
this checkout live only in the untracked `.env`.
