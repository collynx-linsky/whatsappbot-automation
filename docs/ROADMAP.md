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

## Done (this session — "WhatsApp Integration")

Corresponds to spec Phase 7:

- Models: `whatsapp.WhatsAppAccount` (per-business credentials, access
  token encrypted at rest via `core.crypto`/Fernet), `whatsapp.MessageEvent`
  (webhook idempotency log, deferred from the CRM/Conversations phase).
- `apps.whatsapp.providers`: `MessagingProvider` interface +
  `WhatsAppCloudProvider` concrete implementation (spec section 38) —
  `apps.messages`/`apps.conversations` have zero import of `apps.whatsapp`;
  the connection is one-directional via a `Message.post_save` signal.
- Inbound flow: signed webhook → `parse_webhook_payload` → resolve
  `WhatsAppAccount` by `phone_number_id` → tenant → get-or-create Customer
  → get-or-create open Conversation → create Message, idempotent per
  `(account, wamid)`.
- Outbound flow: staff `POST /api/v1/messages/` → `PENDING` → Celery task
  (`high_priority` queue) → `WhatsAppCloudProvider.send_text_message` →
  `SENT`/`FAILED`. **Fixed a real gap while wiring this**: neither
  `scripts/start.ps1` nor `docker-compose.yml`'s celery_worker command
  listened to non-default queues — tasks routed to `high_priority` would
  have silently never run. Both now pass `-Q default,high_priority,low_priority`.
- Security: `X-Hub-Signature-256` HMAC verification (fails closed if
  `WHATSAPP_APP_SECRET` unset), access tokens never returned by the API
  (checked against the actual rendered response body, not pre-render data).
- API: `/api/v1/whatsapp/accounts/` (manager+), `/api/v1/whatsapp/webhook/`
  (public, signature-protected).
- 17 new passing tests (55 total) against a hand-built payload matching
  WhatsApp Cloud API's real webhook JSON shape — proves the full pipeline
  without needing real Meta credentials (none were available this
  session). **Also verified live** end-to-end against a real Redis broker,
  a real Celery worker process, and a real (rejected) call to Meta's Graph
  API — see the resolved gap below and `docs/whatsapp.md`.
- `docs/whatsapp.md` (new).

## Done (this session — "Staff Management")

Corresponds to spec Phase 4's staff half (business settings UI is not part
of this — see the table below):

- `/api/v1/staff/` (list/create) and `/api/v1/staff/{id}/` (retrieve/update)
  in `apps.accounts` — no new model, just tenant-scoped CRUD on the
  existing `accounts.User` restricted to `manager`/`staff` roles.
- A Business Owner can now actually build a team: previously the *only*
  way any non-super-admin user got created was the platform's onboarding
  flow (one `BUSINESS_OWNER` per tenant) — there was no way for an owner
  to add `MANAGER`/`STAFF` accounts to handle conversations themselves.
- Guardrails enforced server-side: can't create/promote to
  `business_owner`/`super_admin`; `PATCH` can't target the business owner
  record or the caller's own account (no self-lockout); a super admin
  (`tenant=None`) creating staff is rejected with a clean 400 rather than
  hitting a `NOT NULL` on `tenant`.
- Frontend: a "Team" section on `/dashboard` — roster visible to staff+,
  an add-team-member form and activate/deactivate controls visible to the
  business owner only. Extracted the duplicated `Field` form-input
  component (previously copy-pasted between `/admin` and `/dashboard`)
  into `components/Field.tsx`.
- 15 new tests (70 total) — all passed on the first run this time (no new
  bugs caught), likely because the tenant/superadmin guard patterns from
  the two earlier rounds of real bugs were applied proactively instead of
  discovered here.
- `seed_dev_data` now creates a sample Manager (Mambo Fashion) and Staff
  (ABC Electronics) account.

## Done (this session — "Products & Orders")

Corresponds to spec Phase 10:

- `products.Product`: catalog per spec section 13. `image` is a single
  field (matching `Business.logo`), not a gallery. `is_orderable` is
  computed (`is_available and status=active and stock>0`), not stored.
- `orders.Order` / `OrderItem`: spec section 14's status list implemented
  as a real forward-only state machine (`Order.ALLOWED_TRANSITIONS`), not
  a free-text field — this is what actually satisfies "require appropriate
  confirmation before finalizing an order." `OrderItem` snapshots
  `product_name`/`unit_price` at order time so a later price change never
  rewrites history.
- API: `/api/v1/products/`, `/api/v1/orders/` (+ `status/` for validated
  transitions) — tenant-isolated, cross-tenant-FK-checked on `customer`/
  `conversation`/every item's `product`.
- Frontend: a new `/dashboard/products` page (catalog table + add-product
  form for manager+, order list with per-row status-transition buttons,
  order-creation form) and a nav bar added to `DashboardShell` (shared
  between `/dashboard` and this new page).
- `seed_dev_data`: 2–3 products per business + one confirmed sample order
  per business, tied to the already-seeded conversation.
- 17 new tests (87 total). **3 real bugs caught by the tests, not by
  review, and fixed**: (1) `Product.sku`'s conditional `UniqueConstraint`
  confused DRF's auto field generation into `required=True` despite
  `blank=True` on the model — fixed with an explicit serializer field;
  (2) the order-create response was missing `items` entirely because the
  write-only nested input field shadowed the parent serializer's read-only
  `items` field of the same name — fixed by having the view re-serialize
  the created order with the read serializer instead of returning the
  create serializer's own (write-only-blind) `.data`; (3) a test fixture
  passed `price="100.00"` as a plain string instead of `Decimal("100.00")`
  — Django doesn't coerce an assigned `DecimalField` value until it
  round-trips through the DB, so `unit_price * quantity` did Python string
  repetition (`"100.00" * 2 == "100.00100.00"`) instead of arithmetic.
  Also caught and fixed independently: `OrderStatusTransitionView` listed
  `TenantScopedQuerysetMixin` as a base class but then defined its own
  `get_queryset()` on top, silently shadowing the mixin entirely (a plain
  `APIView` doesn't support the mixin's `GenericAPIView`-based
  `super().get_queryset()` chain anyway) — fixed by writing the tenant
  filter directly instead of pretending to use the mixin.
- docs/{database,api}.md updated.

## Done (this session — "AI Engine")

Corresponds to spec Phase 8:

- Model: `ai.AISettings` — one row per `Business`, created lazily on first
  `GET /api/v1/ai/settings/` rather than at business-creation time.
- `apps.ai.providers`: `AIProvider` interface + `OpenAIProvider` +
  `AnthropicProvider` (spec section 38), plain HTTP via `requests` (same
  pattern as `apps.whatsapp.providers`, no vendor SDK). `get_provider()`
  returns `None` (not an exception) when the matching API key is blank in
  `.env` — the exact signal `generate_ai_reply` uses to hand off instead
  of erroring, since **no real OpenAI/Anthropic API key was available this
  session**.
- `apps.ai.services.generate_ai_reply`: the full AI/human decision flow
  (spec section 10) — mode gating, built-in + business-defined handoff
  keyword/phrase detection (checked *before* any provider call, to save
  cost), confidence-threshold handoff, a grounded default system prompt
  built from the business's own profile (explicit "never invent prices"
  instruction), last-10-turn conversation history. Confidence is an
  honestly-labeled heuristic (`apps.ai.providers._estimate_confidence`) —
  neither provider's chat completions API returns a real calibrated score.
- Handoff is transparent to the customer (sends `AISettings.fallback_message`
  as a normal AI-authored reply, not silence) and flips
  `Conversation.ai_enabled = False` so follow-up messages don't keep
  re-triggering AI attempts until a human re-enables it; every handoff is
  also written to `AuditLog` (`action="AI_HANDOFF"`, reason in metadata).
- Wired into the inbound pipeline via `apps.ai.signals.dispatch_ai_reply`
  (`Message.post_save`, Celery task on the `default` queue) — same
  decoupling pattern as WhatsApp's outbound signal; `apps.messages` still
  has zero import of `apps.ai`. Extended
  `apps.whatsapp.signals._SENDABLE_SENDER_TYPES` from `(STAFF,)` to
  `(STAFF, AI)` so an AI-generated reply actually reaches WhatsApp, not
  just a staff-typed one.
- API: `GET/PATCH /api/v1/ai/settings/`, `POST /api/v1/ai/test/`
  (onboarding "test your AI" step) — both manager+, tenant-isolated.
- `seed_dev_data` now creates default `AISettings` (hybrid mode, handoff
  enabled, the spec's example `handoff_keywords` list) for every seeded
  business — including a backfill path for a dev DB seeded before this
  phase existed, so the command stays genuinely safe to re-run.
- 22 new passing tests (109 total). One real test-design bug caught and
  fixed during writing (not a product bug): `CELERY_TASK_ALWAYS_EAGER=True`
  in test settings meant creating an inbound `Message` via the test helper
  *also* synchronously ran `generate_ai_reply` through the real signal
  before the test's own direct call — double-invoking it and corrupting
  `conversation.ai_enabled` out from under the assertions. Fixed by
  disconnecting `dispatch_ai_reply` for the test class that calls
  `generate_ai_reply()` directly.
- `docs/ai.md` (new); `docs/database.md`, `docs/api.md`, `docs/security.md`
  updated.
- **Also verified live** against a running dev server: settings
  lazily-created and returned correctly, `/ai/test/` correctly reported a
  real (not simulated) "openai API key not configured" handoff, tenant
  isolation and RBAC (`staff` role gets `403` on `PATCH`) both proven with
  two real seeded business owners.

## Not built yet — placeholder app directories only

`backend/apps/{knowledge,campaigns,analytics,notifications,billing,
audit}/` exist as empty Python packages (just `__init__.py`), not
registered in `INSTALLED_APPS`, no models/views. They map to the spec's
remaining phases:

| Phase | Spec # | Builds |
|---|---|---|
| 4 (remainder) | Business management | Business settings UI (opening hours, branding, etc.) — staff invites are done, see above |
| 9 | RAG knowledge base | `apps.knowledge` — KnowledgeDocument/Chunk/Embedding, upload → chunk → embed → retrieve pipeline, pgvector |
| 11 | Marketing | `apps.campaigns` — segments, templates, opt-in/messaging-window compliance |
| 12 | Analytics | `apps.analytics` — funnel (conversation → lead → qualified → order → revenue), platform-level stats for super admin |
| 13 | Billing/subscriptions | `apps.billing` — actually enforce `Plan` limits, `Subscription`, `UsageRecord`, `Invoice` |
| 14 | Frontend polish | WhatsApp-style inbox, onboarding wizard, full dashboard pages |
| 15 | Testing/security | Broader test coverage, rate limiting, file upload validation |
| 16 | Docker/deployment | Production Dockerfiles, CI, real deployment target |

Also not yet started: `docs/rag.md`, `docs/deployment.md`,
`docs/troubleshooting.md` — write these when their corresponding phase
lands, not before (a doc for code that doesn't exist yet just goes stale).

## Known gaps flagged honestly (not silently deferred)

- ~~Redis/Celery never verified against a real broker~~ — **resolved this
  session.** `docker info`/the `docker` CLI stayed broken (stale named-pipe
  context) all session, but a Redis 7.2.12 instance was found genuinely
  listening on `localhost:6379` anyway (almost certainly a container still
  running under Docker Desktop's WSL2 backend, orphaned from the CLI's
  perspective) — confirmed via a raw `PING`, then used for real: started an
  actual `celery worker` process against it (`-Q default,high_priority,low_priority`,
  confirming the queue-routing fix), posted a real staff reply through the
  live API, and watched the worker pick up `send_whatsapp_message_task`
  from the real queue, decrypt the stored token, and **call the real Meta
  Graph API** (`graph.facebook.com`) — which correctly rejected the
  dev-only fake access token ("Invalid OAuth access token"), and the task
  correctly marked the message `FAILED`. This proves the entire pipeline
  except the one thing that requires real Meta credentials: a *valid*
  token. If `docker` CLI commands are needed for something else, the
  context is still broken and probably needs a Docker Desktop restart.
- Rate limiting and file upload validation are designed for (settings/env
  vars exist) but not implemented — see `docs/security.md`.
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
- `POST /api/v1/messages/` still only accepts `sender_type=staff` — inbound
  customer messages now do have a real source (`POST /api/v1/whatsapp/webhook/`,
  see `docs/whatsapp.md`), so this is no longer a placeholder restriction,
  it's the actual intended design: customers don't call the REST API.
- WhatsApp integration limitations (media messages, delivery/read
  receipts, no connection test) are listed in `docs/whatsapp.md` rather
  than duplicated here.
- Creating an order does **not** decrement `Product.stock` — inventory
  management is manual for now. Test-documented on purpose
  (`test_stock_is_independent_of_order_creation`) so implementing real
  stock deduction later fails that test as a reminder to update it, not a
  silent behavior change.
- No image gallery for products (or businesses) — one `ImageField` each,
  no upload endpoint built yet either (same gap as `MessageAttachment`).
- Order creation is single-request/single-transaction (all items validated
  and created atomically) but there's no "reserve stock while the customer
  decides" concept — two concurrent orders can both succeed against the
  same limited stock. Fine for a manually-managed catalog; would need
  addressing before stock deduction becomes real.
