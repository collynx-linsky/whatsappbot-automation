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

## Done (this session — "Customer CRM + Conversations/Messages")

Corresponds to spec Phase 5 + Phase 6, bundled:

- Models: `customers.Customer` (lead status, tags, source), 
  `conversations.Conversation` + `ConversationAssignment` (assignment
  history log), `messaging.Message` + `MessageAttachment` (app label
  `messaging`, not `messages` — collides with `django.contrib.messages`
  otherwise).
- `core/mixins.py`: extracted `TenantScopedQuerysetMixin` /
  `TenantScopedCreateMixin` from `apps.businesses.views` so every new
  tenant-scoped app reuses the same pattern instead of copy-pasting it.
- Cross-tenant foreign key protection: every serializer with a
  client-writable FK to another tenant-scoped model
  (`Conversation.customer`, `Message.conversation`,
  `Conversation.assigned_to`) validates that FK's tenant explicitly —
  proven live, see `docs/multi-tenancy.md`.
- API: `/api/v1/customers/`, `/api/v1/conversations/` (+ `assign/`,
  `assignments/`), `/api/v1/messages/` — all tenant-isolated, staff+ gated.
- `seed_dev_data` now creates 2 sample customers per business + one open
  conversation with an inbound/outbound message pair for the first.
- 38 passing `pytest` tests (15 new). **3 real bugs caught by the tests,
  not by review, and fixed**: (1) `IntegrityError` on a duplicate
  `(tenant, phone)` crashed with a 500 instead of a clean 400 — added
  `validate_phone`; (2) a super admin `POST`ing to a tenant-scoped
  create endpoint would have hit a `NOT NULL` constraint on `tenant`
  (they have none) — `TenantScopedCreateMixin` now rejects this with a
  clear 400; (3) two test assertions compared a UUID object to a string
  (`resp.data["tenant"]` is a UUID, not a str, before JSON rendering).

## Not built yet — placeholder app directories only

`backend/apps/{whatsapp,ai,knowledge,products,orders,campaigns,analytics,
notifications,billing,audit}/` exist as empty Python packages (just
`__init__.py`), not registered in `INSTALLED_APPS`, no models/views. They
map to the spec's remaining phases:

| Phase | Spec # | Builds |
|---|---|---|
| 4 | Business management | Staff invites/roles-within-tenant, business settings UI |
| 7 | WhatsApp integration | `apps.whatsapp` — WhatsAppAccount (encrypted credentials), webhook receiver, idempotent event processing, `MessagingProvider` interface. Writes into the `customers`/`conversations`/`messaging` models built this session. |
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
- `Conversation` is simplified to one customer + one assigned staff member
  — no `ConversationParticipant` model for multi-party/group conversations.
  Fine for 1:1 WhatsApp chat; revisit if internal multi-staff escalation on
  a single conversation is ever needed.
- Tags (`Customer.tags`, `Conversation.tags`) are a plain JSON list of
  strings, not a normalized `Tag` model — no cross-tenant tag taxonomy,
  autocomplete, or tag-based analytics yet.
- `POST /api/v1/messages/` only accepts `sender_type=staff` — there's no
  way to simulate an inbound customer message via the API (only via
  `seed_dev_data` writing directly to the ORM). That's intentional until
  Phase 7's webhook is the real source of inbound messages.
