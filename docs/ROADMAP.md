# Roadmap

The master spec defines 16 phases. This is the authoritative source for
what's built vs. not — read this before starting new work on this project.

## Done (this session — "Foundation + Multi-tenancy + Auth/RBAC")

Corresponds to the spec's Phase 1 (Foundation) + Phase 2 (Database &
multi-tenancy) + Phase 3 (Authentication & RBAC), bundled into one testable
milestone:

- Project scaffolding: `backend/` (Django 5.2 + DRF), `frontend/`
  (Next.js 16 + TS + Tailwind), `infrastructure/`, `docs/`, `scripts/`,
  `docker-compose.yml`, `.env.example`, git repo.
- `core/`: base model layer, tenant-resolution middleware, RBAC permission
  classes, exception handler, pagination.
- Models: `tenants.Tenant`, `tenants.Plan`, `businesses.Business`,
  `accounts.User` (4 fixed roles), `accounts.PasswordResetToken`,
  `common.AuditLog`.
- Auth: JWT login/refresh/logout, `/me/`, forgot/reset password, account
  lockout after 5 failed attempts.
- Super-admin onboarding flow: atomically creates Tenant + Business +
  Business Owner.
- Tenant CRUD (list/retrieve/suspend/activate) + Business retrieve/update,
  all tenant-isolated and role-gated.
- Frontend: `/login`, `/dashboard` (business), `/admin` (super admin, with
  a live onboarding form and tenant suspend/activate).
- 23 passing `pytest` tests including the critical tenant-isolation suite.
- `docs/architecture.md`, `docs/database.md`, `docs/multi-tenancy.md`,
  `docs/security.md`, `docs/api.md`, `docs/development.md`.

## Not built yet — placeholder app directories only

`backend/apps/{whatsapp,customers,conversations,messages,ai,knowledge,
products,orders,campaigns,analytics,notifications,billing,audit}/` exist as
empty Python packages (just `__init__.py`), not registered in
`INSTALLED_APPS`, no models/views. They map to the spec's remaining phases:

| Phase | Spec # | Builds |
|---|---|---|
| 4 | Business management | Staff invites/roles-within-tenant, business settings UI |
| 5 | Customer CRM | `apps.customers` — Customer model, lead status, tags, notes |
| 6 | Conversations/messages | `apps.conversations`, `apps.messages` — Conversation/Message/ConversationAssignment, OPEN/PENDING/RESOLVED/CLOSED |
| 7 | WhatsApp integration | `apps.whatsapp` — WhatsAppAccount (encrypted credentials), webhook receiver, idempotent event processing, `MessagingProvider` interface |
| 8 | AI engine | `apps.ai` — AISettings, `AIProvider` interface (OpenAI/Anthropic), human handoff (AI/HUMAN/HYBRID modes) |
| 9 | RAG knowledge base | `apps.knowledge` — KnowledgeDocument/Chunk/Embedding, upload → chunk → embed → retrieve pipeline, pgvector |
| 10 | Products & orders | `apps.products`, `apps.orders` |
| 11 | Marketing | `apps.campaigns` — segments, templates, opt-in/messaging-window compliance |
| 12 | Analytics | `apps.analytics` — funnel (conversation → lead → qualified → order → revenue), platform-level stats for super admin |
| 13 | Billing/subscriptions | `apps.billing` — actually enforce `Plan` limits, `Subscription`, `UsageRecord`, `Invoice` |
| 14 | Frontend polish | WhatsApp-style inbox, onboarding wizard, full dashboard pages |
| 15 | Testing/security | Broader test coverage, rate limiting, file upload validation |
| 16 | Docker/deployment | Production Dockerfiles, CI, real deployment target |

Also not yet started: `docs/whatsapp.md`, `docs/ai.md`, `docs/rag.md`,
`docs/deployment.md`, `docs/troubleshooting.md` — write these when their
corresponding phase lands, not before (a doc for code that doesn't exist
yet just goes stale).

## Known gaps flagged honestly (not silently deferred)

- **Redis was never verified live this session** — Docker Desktop stayed
  down (cold-start) for the entire session despite being confirmed working
  at the very start. `docker-compose.yml`'s `redis` service and the Celery
  wiring are written and should work, but nobody has actually run
  `docker compose up -d redis` + a live Celery task against this checkout
  yet. Do that before relying on it.
- Rate limiting, per-tenant WhatsApp credential encryption, and file upload
  validation are designed for (settings/env vars exist) but not implemented
  — see `docs/security.md`.
- RBAC is the spec's 4 fixed roles, not a dynamic per-tenant
  role/permission-assignment engine. If a future phase needs
  MANAGER/STAFF to have differently-scoped permissions *within* their
  tenant (not just a flat role check), that's new work, not something
  already stubbed.
