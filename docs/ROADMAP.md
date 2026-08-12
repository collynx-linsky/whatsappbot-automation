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

## Done (this session — "RAG Knowledge Base")

Corresponds to spec Phase 9:

- Models: `knowledge.KnowledgeDocument` (per-business, `upload|text`
  source, status machine `pending → processing → ready|failed`),
  `knowledge.KnowledgeChunk` (`embedding` as a plain `JSONField` float
  list — **no pgvector on this project's native Postgres instance**,
  confirmed via `pg_available_extensions`; documented upgrade path in
  `docs/rag.md` rather than silently faking vector search).
  `apps.knowledge.providers.OpenAIEmbeddingProvider` (spec section 38,
  same plain-`requests` pattern as every other provider in this codebase)
  + `get_embedding_provider()` returning `None` when `OPENAI_API_KEY` is
  blank — **no real API key was available this session**, same posture
  as Phase 8.
- Pipeline (`apps.knowledge.services`): `extract_text` (`.txt` decoded
  directly, `.pdf` via `pypdf` — new lightweight dependency, no compiled
  extensions), `chunk_text` (200-word chunks, 30-word overlap, word-
  boundary safe), `process_document` (idempotent — replaces old chunks on
  re-run), `retrieve_relevant_chunks` (cosine similarity when chunks are
  embedded, keyword-overlap fallback otherwise — a knowledge base is
  never silently unused just because no embedding provider is
  configured), run via `apps.knowledge.tasks.process_knowledge_document_task`
  on the `low_priority` queue.
- Wired into the AI reply pipeline: `apps.ai.services.append_knowledge_context`
  retrieves the top-3 relevant chunks for the customer's message and
  appends them to the system prompt — this is what actually gives
  `build_system_prompt`'s "never invent facts" instruction (Phase 8)
  something true to draw from. `apps.ai` → `apps.knowledge` is a
  one-directional import, same decoupling discipline as every other
  cross-app connection in this codebase.
- API: `GET/POST /api/v1/knowledge/documents/` (GET staff+, POST
  manager+), `GET/DELETE /api/v1/knowledge/documents/{id}/`,
  `GET /api/v1/knowledge/documents/{id}/chunks/` — tenant-isolated,
  cross-tenant `business` rejected, file extension validated
  (`.txt`/`.pdf` only) before anything is saved to disk. This also closes
  the file-upload-validation gap `docs/security.md` had flagged open
  since the WhatsApp phase.
- `seed_dev_data`: 1-2 sample knowledge documents per business, processed
  *synchronously* at seed time (not via Celery) so seeded data is
  immediately usable without a running worker.
- 29 new passing tests (138 total) — chunking, extraction, the full
  process/retrieve pipeline (mocked HTTP for success, real for the
  no-provider degraded path), the documents API, and an integration test
  proving a knowledge-base chunk actually reaches the AI provider's
  system prompt. Same test-design gotcha as Phase 8 recurred and was
  fixed the same way: `CELERY_TASK_ALWAYS_EAGER` meant creating an
  inbound `Message` in the integration test would also synchronously
  fire the real AI signal — disconnected it for that test.
- `docs/rag.md` (new); `docs/database.md`, `docs/api.md`,
  `docs/security.md` updated.
- **Also verified live**: seeded knowledge documents confirmed `ready`
  with `embedded_chunk_count: 0` (correct degraded state) via `curl`
  against a running dev server; created a new document through a real
  authenticated `POST`; directly re-invoked `process_document()` against
  it to confirm the extract → chunk → store pipeline works end-to-end
  against the real Postgres database. **Environment finding, not a code
  bug**: this dev machine's Redis broker (db 1) is shared across several
  of this user's unrelated projects and appears to have a stale worker
  process from earlier in this session still attached — a freshly queued
  task wasn't visibly consumed by a newly started worker. Full detail and
  the recommended fix (kill stale workers / dedicate a Redis db to this
  project) in `docs/rag.md`.

## Done (this session — "Marketing Campaigns")

Corresponds to spec Phases 12 and 26:

- Models: `campaigns.MessageTemplate` (status set manually — no real Meta
  Template API access this session), `campaigns.Segment` (dynamic
  `statuses`/`sources`/`tags` filters, re-evaluated live on every read),
  `campaigns.Campaign`, `campaigns.CampaignRecipient` (per-customer
  outcome, unique per `(campaign, customer)`).
- **Compliance enforced structurally, not by convention** (spec section
  26): added `Customer.marketing_opt_in`/`marketing_opt_in_at` (defaults
  `False` — opt-in, not opt-out; never set implicitly by an inbound
  WhatsApp message). `get_segment_customers` filters to
  `marketing_opt_in=True` unconditionally; `send_campaign` re-checks it a
  second time per recipient at actual send time, since a customer can
  opt out between scheduling and sending. Extended
  `apps.whatsapp.providers.MessagingProvider` with a distinct
  `send_template_message` method (Meta's real "proactive marketing sends
  must use an approved template" rule) — campaign sends are structurally
  incapable of taking the free-text `send_text_message` path a staff/AI
  reply uses.
- New `Message.SenderType.CAMPAIGN` — deliberately **not** added to
  `apps.whatsapp.signals._SENDABLE_SENDER_TYPES`; campaign sends create
  their `Message` row directly (status already resolved from the real
  provider call) rather than going through the generic PENDING→dispatch
  path built for staff/AI replies.
- API: `GET/POST /api/v1/campaigns/templates/`, `GET/PATCH .../templates/{id}/`,
  `GET/POST /api/v1/campaigns/segments/`, `GET/PATCH/DELETE .../segments/{id}/`,
  `GET .../segments/{id}/preview/`, `GET/POST /api/v1/campaigns/`,
  `GET/PATCH /api/v1/campaigns/{id}/`, `POST .../{id}/send/`,
  `GET .../{id}/recipients/` — all tenant-isolated, RBAC-gated
  (manager+ for anything that creates/sends/approves).
- `seed_dev_data`: one opted-in customer, one approved `MessageTemplate`,
  one `Segment`, and one `draft` `Campaign` per business — never
  auto-sent (sending is a deliberate user action via the API, not
  something seed data does on its own).
- 29 new passing tests (167 total) — segment filter evaluation, the full
  send pipeline (mocked HTTP for success/failure, real for every
  structural-failure path: unapproved template, no connected WhatsApp
  account, zero opted-in recipients), the mid-flight-opt-out case, and
  the API surface. **One real bug caught by testing, not by review, and
  fixed**: `CampaignSendView.post` set `status=scheduled` *after* calling
  `.delay()` — under eager Celery execution the task had already resolved
  the campaign to `sent`/`failed` by then, and the stale in-memory object
  overwrote that real outcome back to `scheduled` on save. Fixed by
  saving `scheduled` before enqueueing, then refreshing from the database
  after.
- `docs/campaigns.md` (new); `docs/database.md`, `docs/api.md`,
  `docs/security.md` updated.
- **Also verified live**: seeded segment correctly reported
  `customer_count: 1` against the one real seeded opted-in customer;
  directly re-invoked `send_campaign()` against a live campaign to
  confirm the real "no connected WhatsApp account" structural failure
  end-to-end against the real Postgres database; tenant isolation and
  RBAC both proven with two real seeded business owners.
- **Bug caught and fixed mid-build, before any test ran**: a
  `CampaignRecipient.message` FK string reference used
  `"messages.Message"` instead of the actual registered app label
  `"messaging.Message"` (see the `messaging.Message` note in this file's
  Customer CRM section) — resolved to nothing and crashed
  `manage.py check` with an opaque `AttributeError` inside Django's admin
  inline checks, not a clear "app not found" error. Worth remembering:
  that mislabeling always surfaces this way, not as an immediate error at
  the FK declaration site.

## Done (this session — "Analytics")

Corresponds to spec section 17:

- **No new persisted models** — every metric is computed live from
  existing data (`Customer`, `Conversation`, `Message`, `Order`,
  `AuditLog`), not a materialized snapshot. Documented as a deliberate
  MVP-scale trade-off with a clear upgrade path (a `celery beat`
  snapshot job) once it stops being fast enough — see `docs/analytics.md`.
- `apps.analytics.services`: customer funnel (lead-pipeline stage
  counts), conversation/message counts, order revenue **grouped by
  currency, never summed across currencies** (a tenant's orders aren't
  guaranteed to share one), AI performance (replies sent vs. handoffs,
  reading real `Message`/`AuditLog` data from Phase 8), average response
  time (single ordered pass over a tenant's messages — measures time from
  the *first* unanswered inbound message to the next outbound reply, so a
  burst of consecutive customer messages before a reply counts as one
  wait, not several), top customer questions (normalized-text grouping,
  **only questions asked more than once** — a list of every unique thing
  anyone ever asked isn't a "most common" list).
- `apps.analytics.platform_services` — deliberately a separate module
  (not just a separate function) from the tenant-scoped one, since every
  query here reads across *every* tenant; keeping them apart makes it
  harder to accidentally call platform-wide aggregation from a
  tenant-scoped view. Tenant/user counts by status/role, platform
  totals, platform-wide currency-grouped revenue, 30-day signup trend.
- API: `GET /api/v1/analytics/dashboard/` (staff+, own tenant, optional
  `?start=&end=` ISO 8601 bounds), `GET /api/v1/analytics/platform/`
  (super admin only).
- 18 new passing tests (185 total) — every metric function tested
  directly against real data (no HTTP/provider mocking needed at all,
  the first phase this session that touches zero external services), the
  response-time algorithm's consecutive-inbound edge case specifically,
  top-questions' repeated-only filter, and the API surface (tenant
  isolation, RBAC on both endpoints, invalid-date-bound rejection). All
  passed on the first run — no bugs caught this phase.
- `docs/analytics.md` (new); `docs/api.md`, `docs/ROADMAP.md` updated.
- **Also verified live** against a running dev server: the dashboard for
  the real seeded ABC Electronics tenant returned real, cross-checked
  counts; the platform endpoint (as the real seeded super admin) returned
  accurate totals across all 3 seeded tenants with correctly-separated
  `KES`/`TZS`/`UGX` revenue; RBAC (`403` for a business owner on the
  platform endpoint) and date-bound validation (`400` on an unparseable
  `?start=`, a future `?start=` correctly zeroing every count) both
  proven live, not just under `pytest`.

## Done (this session — "Billing")

Corresponds to spec sections 24, 25:

- **No separate `Subscription` model** — `tenants.Tenant` already carries
  `plan`/`status`/`trial_ends_at`/`subscription_ends_at`; a second model
  duplicating that risked two disagreeing sources of truth for no real
  benefit. Documented as a deliberate decision, not a gap — see
  `docs/billing.md`.
- Models: `billing.UsageRecord` (period-scoped usage — `ai_messages`/
  `campaign_sends`, the two Plan limits that are genuinely "per month"),
  `billing.Invoice` (deterministic idempotent invoice numbers, snapshotted
  plan name/price, `draft→issued→paid/overdue/void` status).
- **Plan limits actually enforced**, not just read: `max_users` (staff
  creation), `max_whatsapp_accounts` (account connection), `max_customers`
  (manual customer creation via the API only — **never** on the WhatsApp
  webhook's real inbound customer creation, a deliberate call: dropping a
  genuine customer inquiry over a quota is worse than a business briefly
  exceeding it), `max_ai_messages_per_month` (checked right before the
  real provider call in `apps.ai.services.generate_ai_reply`, degrading
  to human handoff exactly like "no API key configured" already does —
  it runs from a Celery task with no HTTP request to error out to),
  `max_campaigns_per_month` (checked before a campaign send is even
  queued). `max_storage_mb` is explicitly **not** enforced — no file-size
  tracking exists across every upload type to sum against; flagged
  honestly rather than half-built against just one.
- New `apps.billing.exceptions.PlanLimitExceeded` — a real `402 Payment
  Required` (not 403/400), flowing through the same error envelope as
  every other exception in this API.
- API: `GET /api/v1/billing/usage/`, `GET /api/v1/billing/invoices/` +
  `.../{id}/`, `POST /api/v1/billing/invoices/generate/` (super admin,
  manual per-tenant trigger — no payment gateway exists to trigger this
  automatically).
- New `python manage.py generate_invoices` management command — the
  batch counterpart, one invoice per active/trial tenant with a plan,
  idempotent per period. Not scheduled anywhere (no `celery beat` entry)
  since there's no payment gateway for the resulting invoices to be
  acted on by.
- 25 new passing tests (210 total) — `check_limit`/`is_over_limit` in
  isolation, usage tracking, invoice snapshotting/idempotency, and
  (the part that actually matters) enforcement wired into the real
  views, hitting genuine `402`s against a purpose-built low-limit `Plan`.
  All passed on the first run.
- `docs/billing.md` (new); `docs/database.md`, `docs/api.md` updated.
- **Also verified live**: `GET /api/v1/billing/usage/` against the real
  seeded ABC Electronics tenant returned real counts; `generate_invoices`
  created 3 real invoices (one per seeded tenant) and was confirmed
  idempotent on a second run; connecting a second WhatsApp account past
  the seeded plan's `max_whatsapp_accounts=1` limit returned a genuine
  `HTTP 402` with the expected error envelope.

## Done (this session — "Security Hardening")

Corresponds to spec section 20 / Phase 15's rate-limiting item:

- **Rate limiting**: `DEFAULT_THROTTLE_CLASSES` (Anon/User blanket
  backstop + `ScopedRateThrottle`) wired up platform-wide for the first
  time. Four endpoints scope-throttled at rates tuned to what each
  actually costs/risks: the public WhatsApp webhook (`120/minute`,
  separate from the shared `anon` bucket so it can't be starved by
  unrelated anonymous traffic like login attempts), `/api/v1/ai/test/`
  (`20/hour` — real provider cost), `/api/v1/knowledge/documents/` `POST`
  only (`30/hour` — real embedding-provider cost; `GET` deliberately
  excluded via a per-method `get_throttles()` override so browsing the
  knowledge base isn't rate-limited at upload rates), and
  `/api/v1/campaigns/{id}/send/` (`10/hour` — messages real customers).
  All six rates configurable via `.env` (`THROTTLE_RATE_*`).
- **Real bug caught while writing the tests, not by review**: an
  earlier version of `tests/test_security.py` overrode throttle rates
  via the pytest-django `settings` fixture, and the tests *passed* —
  but for the wrong reason. DRF's `SimpleRateThrottle.THROTTLE_RATES` is
  a plain class attribute bound once at Django startup to a specific
  dict object; reassigning `settings.REST_FRAMEWORK` later builds a new
  dict that attribute never sees, so the "override" silently did
  nothing and the tests were actually exercising the real production
  rates (confirmed by isolating one test with debug prints showing the
  dict identity mismatch). Fixed by using `monkeypatch.setitem()` to
  mutate the actual bound dict in place. Full writeup in
  `docs/security.md`'s Rate limiting section — a genuinely non-obvious
  DRF gotcha worth remembering if this pattern is ever touched again.
  Also required a new `tests/conftest.py` autouse fixture clearing
  Django's cache before every test, since `LocMemCache` in test settings
  persists for the whole `pytest` process and throttle counters would
  otherwise silently accumulate across the entire 200+-test suite.
- **Audit logging coverage**: closed the gap `docs/security.md` had
  flagged open — five previously-silent actions now write an `AuditLog`
  row: `AI_SETTINGS_UPDATED`, `KNOWLEDGE_DOCUMENT_UPLOADED`,
  `WHATSAPP_ACCOUNT_CONNECTED`, `CAMPAIGN_SENT`, `INVOICE_GENERATED`.
- 10 new passing tests (220 total) — each throttle scope proven to
  actually trip (and, for the knowledge endpoint, proven that `GET`
  does *not* share the `POST` budget), plus all five new audit actions
  confirmed to fire a real `AuditLog` row.
- `docs/security.md` updated (Rate limiting section rewritten, Audit
  logging section updated, live-verification section extended).
- **Also verified live**: 20 real consecutive `/api/v1/ai/test/`
  requests against a running dev server (real Redis-backed cache, not
  the in-memory test cache) all succeeded; the 21st returned a genuine
  `429` with the expected error envelope — against the actual production
  default rate, not a lowered test value.

## Done (this session — "Security Enhancement Pass — 10 Priorities")

A dedicated hardening pass across the whole backend, prioritized 1-10 by
the user. Full detail lives in `docs/security.md`, `docs/mfa.md`, and
`docs/backup-recovery.md`; this is the roadmap-level summary.

1. **Multi-tenant isolation** — audited programmatically (not just
   re-read manually): a new `manage.py audit_permissions` command walks
   every registered URL pattern via `django.urls.get_resolver()` and
   confirms every queryset-based view uses `TenantScopedQuerysetMixin`
   (or is on a reviewed manual-scoping allowlist). Made permanent and
   CI-wireable, not a one-off audit.
2. **RBAC / permission engine** — same audit command also confirms every
   view declares explicit `permission_classes`/`get_permissions()`; no
   view relies on DRF's implicit default.
3. **MFA** — mandatory TOTP for every role, no exceptions (explicit user
   decision — "Required for everyone", including Super Admin). Two-stage
   login via purpose-tagged JWTs (`mfa_setup`/`mfa_challenge`), enforced
   at the authentication layer (`core.authentication
   .FullAccessJWTAuthentication`) rather than per-view, since this
   codebase's convention of explicit `permission_classes` everywhere
   would make a permission-layer-only rule silently bypassable. 10
   single-use SHA-256-hashed backup codes per user. Three-tier recovery:
   self-service backup codes → Business Owner/Super Admin reset endpoint
   → break-glass `manage.py reset_mfa` for a locked-out Super Admin. Full
   design writeup in `docs/mfa.md`.
4. **Secure authentication/session management** — `login` and
   `mfa_verify` throttle scopes (brute-force defense on both password and
   6-digit TOTP guessing); `GET /api/v1/auth/sessions/` and
   `POST /api/v1/auth/sessions/{jti}/revoke/` built on
   `rest_framework_simplejwt.token_blacklist`'s existing
   `OutstandingToken`/`BlacklistedToken` models rather than a parallel
   session model.
5. **Audit logging** — `MFA_ENABLED`/`MFA_RESET` actions added to the
   existing `AuditLog` platform-wide pattern.
6. **API security + rate limiting** — the two new throttle scopes above,
   layered on the rate-limiting work already done in the earlier
   "Security Hardening" section (Phase 15).
7. **Database security** — least-privilege DB role verified live against
   real `pg_roles` (`waba_user` is not superuser, cannot create roles);
   `sslmode` made configurable (`prefer` dev / `require` production
   default) via `POSTGRES_SSLMODE`; exhaustive grep across the whole
   codebase confirmed zero raw-SQL/`.extra()`/`RawSQL` usage outside
   migrations.
8. **Security headers + HTTPS** — new `core.middleware
   .SecurityHeadersMiddleware` adds `Content-Security-Policy` and
   `Permissions-Policy` (Django has no built-in setting for either);
   `SECURE_REFERRER_POLICY`/`SECURE_CROSS_ORIGIN_OPENER_POLICY` set
   explicitly in `production.py`.
9. **Backup/disaster recovery** — `scripts/backup-db.ps1`
   (`pg_dump -Fc`, configurable retention) and `scripts/restore-db.ps1`
   (destructive, gated behind `-Force` + typed confirmation — proven to
   fail safe under a non-interactive shell rather than silently
   proceeding). `docs/backup-recovery.md` explicitly calls out that
   `FIELD_ENCRYPTION_KEY` must be backed up separately from the database
   dump (losing it makes every encrypted token/MFA secret unrecoverable
   even with the DB intact).
10. **Automated vulnerability/security testing** — `bandit` (0 findings,
    4 verified false positives suppressed with justification) and
    `pip-audit` (65 real CVEs found and fixed via version-pin upgrades,
    confirmed against the live 246-test suite after each upgrade, now 0
    remaining across both `requirements/base.txt` and
    `requirements/development.txt`) genuinely run against the real
    codebase, not just described. `scripts/security-scan.ps1` bundles
    both plus `audit_permissions`. `.github/workflows/security.yml`
    wires the same chain (plus Django checks, missing-migrations check,
    ruff/black/isort, pytest, and a frontend eslint/typecheck/build job)
    into CI. The repo now has a GitHub remote (`origin`, pushed to
    `main`), but the workflow's `push`/`pull_request` triggers are
    deliberately commented out for now — only manual `workflow_dispatch`
    is live, so it runs on demand rather than on every commit until
    that's wanted. This is the CI piece of the still-open Phase 16
    "Docker/deployment" row below; Dockerfiles and an actual deployment
    target remain unbuilt.

246 tests passing (up from 220 at the end of the Phase 15 rate-limiting
work), 0 bandit findings, 0 pip-audit findings, `audit_permissions`
clean across 62 view classes / 260 URL patterns.

## Done (this session — "Frontend: fix broken MFA login flow + sessions")

The MFA work above changed `POST /api/v1/auth/login/`'s response shape
(never returns real tokens directly anymore — always a purpose-tagged
step-up token). The frontend predates that change and still assumed
tokens came back from login directly: every real login through the UI
was broken. Fixed, plus a session-management page, since the backend
already supported it and nothing exposed it:

- `types/index.ts`: `LoginResponse` is now a discriminated union
  (`mfa_setup_required`/`setup_token` vs `mfa_required`/`challenge_token`);
  added `MFASetupResponse`, `MFASetupConfirmResponse`, `MFAVerifyResponse`,
  `Session`.
- `lib/api.ts`: `login()` no longer assembles a session itself — it
  returns the union and the caller decides. Added `mfaSetup`,
  `mfaSetupConfirm`, `mfaVerify`, `listSessions`, `revokeSession`, and a
  `pendingTokenFetch` helper (separate from `apiFetch`) for the three MFA
  calls that authenticate with a short-lived purpose token, not a normal
  access token — deliberately skips the silent-refresh-retry logic, since
  a 401 there means "start over," not "refresh."
- `lib/auth.ts`: pending step-up tokens live in `sessionStorage` (not
  `localStorage`) — matches their 10-minute, single-tab-scoped lifetime.
  `useRequireAuth()` gained an optional `requireRole` that redirects a
  mismatched role to their own dashboard instead of rendering the page —
  applied to `/admin`, which never checked `role === "super_admin"`
  before (the backend already enforced it server-side on every real call,
  so not a data leak, just a confusing broken-page UX for the wrong role).
- New pages: `/login/mfa-setup` (QR code via `qrcode.react` off the
  backend's `otpauth://` URI, manual-entry secret fallback, 6-digit
  confirm, one-time backup-codes display with a copy button and an
  acknowledgement checkbox before continuing), `/login/mfa-verify`
  (6-digit code, with a "use a backup code instead" toggle), and
  `/dashboard/sessions` (list + revoke — reachable from every role via a
  new persistent "Sessions" link in `DashboardShell`'s header).
- Live contract verification via `curl` against a running server:
  drove both login branches for real (a never-enrolled throwaway user
  hit `mfa_setup_required`; the same user after enrolling hit
  `mfa_required` on a second login), the full setup → confirm chain, the
  verify chain, and a real session list + revoke — confirmed every JSON
  shape the new frontend code assumes actually comes back from the real
  server, byte for byte. `npx tsc --noEmit`, `npm run lint`, and
  `npm run build` all clean against the new code.
- **Known limitation, stated honestly**: no browser-automation tool is
  available in this environment, so an actual interactive click-through
  (QR code rendering, layout, real button clicks) wasn't done by me —
  only the HTTP contract and the build/typecheck/lint were verified.
  Recommended: run `npm run dev` + `manage.py runserver` together and
  click through login → MFA setup → dashboard once in a real browser.

Explicitly out of scope this pass (deferred, backend already complete
for all of these, zero frontend exists yet): WhatsApp inbox
(conversations/messages), AI settings, knowledge base, campaigns,
analytics, billing. Next frontend session picks one of these up.

## Done (this session — "Frontend: WhatsApp-style inbox")

User picked this as the next frontend module (over AI settings/knowledge
base, campaigns/analytics, billing — all still backend-only). The
dashboard's placeholder text previously said the inbox "lands in the next
build phases"; it now exists.

- `types/index.ts`: added `Conversation`, `ConversationAssignment`,
  `Message`, `MessageAttachment`, and their status/type unions. Extended
  `Customer` with `marketing_opt_in`/`marketing_opt_in_at` and gave
  `source` a real union type (both existed on the backend serializer but
  were missed in the earlier products/orders pass).
- `lib/api.ts`: `listConversations`, `createConversation`,
  `updateConversation` (PATCH — status/ai_enabled/tags),
  `assignConversation` (the dedicated `/assign/` endpoint, not a generic
  PATCH — it's the one that writes an audit-log entry and assignment
  history), `listConversationAssignments`, `listMessages`, `sendMessage`
  (hardcodes `sender_type: "staff"` since that's the only value this
  backend phase accepts). Added a small `toQueryString()` helper and
  extended `listCustomers()` to take `{search, status, source, page}`
  params (it previously took none).
- New page `app/dashboard/inbox/page.tsx`: two-pane WhatsApp-style
  layout — conversation list (status filter, unread badge, last-message
  preview) on the left, message thread (bubbles right-aligned for
  staff/AI, left for the customer, centered for system messages) with a
  reply composer on the right. Conversation header exposes status
  (`<select>`, PATCH), assignee (`<select>` from `listStaff()`, the
  dedicated assign endpoint), and the AI-handoff toggle (`ai_enabled`
  checkbox, PATCH) inline — no modal, matching this codebase's existing
  no-modal-library convention.
- **No real-time channel exists on the backend** (confirmed: no
  `channels`/consumers/websocket routing anywhere) — the page polls
  instead: the conversation list every 15s, an open thread's messages
  every 4s, both cleared on unmount via plain `useEffect` + `setInterval`
  (no new dependency, matching the rest of the frontend's `useState`/
  `useEffect`-only data-fetching style).
- **Known limitation, stated honestly**: there's no "mark read" endpoint
  server-side, so `unread_count` is display-only and is never reset from
  the client — opening a conversation doesn't clear its badge. Attachments
  are read-only on the backend serializer (no upload endpoint exists), so
  the composer is text-only, matching what the API can actually accept.
- Live contract verification via `curl` against a running server, using
  a throwaway staff account (kept fully separate from whatever the user
  was doing in their own browser session at the time) and a real seeded
  customer: created a conversation, posted a staff message and confirmed
  `last_message_preview`/`last_message_at` updated automatically, listed
  messages filtered by `?conversation=`, assigned it via the dedicated
  endpoint and confirmed both `assigned_to_name` and a real assignment-
  history row, PATCHed `status` and `ai_enabled` and confirmed both
  round-tripped. All test data deleted afterward. `npx tsc --noEmit`,
  `npm run lint`, `npm run build` all clean.
- Same stated limitation as the MFA pass: no browser-automation tool is
  available in this environment, so the two-pane layout, polling
  behavior, and message-bubble rendering weren't clicked through by me —
  only the HTTP contract and build/typecheck/lint were verified.

Still deferred: AI settings, knowledge base, campaigns, analytics,
billing frontends, and a WhatsApp-account-connection settings page
(conversations/messages work independently of whether an account is
connected — that only affects whether outbound sends actually reach
Meta, which is a separable, smaller follow-up).

## Done (this session — "Frontend: Analytics dashboards")

User picked this as the next frontend module (over AI settings, knowledge
base, campaigns/billing — all still backend-only). Both existing analytics
endpoints (`docs/analytics.md`, Phase "Analytics" above) had zero frontend;
now both do.

- `types/index.ts`: added `FunnelCounts`, `ConversationCounts`,
  `MessageCounts`, `OrderRevenue`, `AIPerformance`, `ResponseTime`,
  `TopQuestion`, `BusinessDashboard` (mirrors `business_dashboard()`
  exactly), and `TenantCounts`, `UserCounts`, `SignupTrendPoint`,
  `PlatformDashboard` (mirrors `platform_dashboard()`).
- `lib/api.ts`: `getAnalyticsDashboard({start?, end?})`,
  `getPlatformAnalytics()`.
- No charting library added (matches this codebase's existing
  no-modal/no-extra-dependency convention) — three small hand-rolled
  components instead: `components/StatTile.tsx` (headline number, no
  comparison), `components/BarList.tsx` (horizontal bar list — single
  emerald hue by default for "one count series across categories," a
  per-item `color` + `BarListLegend` only where categories are genuinely
  different entities, e.g. messages by sender type, so color carries
  identity and never rank), `components/Sparkline.tsx` (minimal SVG
  line+area for the 30-day signup trend — change-over-time is a line's
  job, not a bar chart's).
- New page `app/dashboard/analytics/page.tsx` (staff+, own tenant): date
  range presets (all time / 7d / 30d / this month) driving the existing
  `?start=&end=` API params, stat tiles (conversations, messages, AI
  replies, handoffs, avg response time), the customer funnel, conversations
  by status, messages by sender (color-coded + legend), order status counts,
  revenue-by-currency tiles (never summed across currencies, matching the
  backend's own honesty about multi-currency), and a top-questions table.
  Added to the shared nav array on `/dashboard`, `/dashboard/products`, and
  `/dashboard/inbox` (this codebase duplicates the nav array per page rather
  than centralizing it — followed the existing pattern).
- `app/admin/page.tsx`: added a "Platform Analytics" section (super admin
  only, reuses the same `StatTile`/`BarList`/`Sparkline` components) —
  tenant/business/conversation/message totals, tenants by status, users by
  role, the 30-day signup-trend sparkline, and platform-wide revenue by
  currency. No new page/route — `/admin` was already the single super-admin
  surface.
- **Verified live against the real running dev server and real seeded
  data** (not just typecheck/build): rather than driving the full
  mandatory-MFA login flow over HTTP for a read-only verification, directly
  invoked `apps.analytics.services.business_dashboard()` (against the real
  seeded ABC Electronics tenant) and `apps.analytics.platform_services
  .platform_dashboard()` inside `manage.py shell`, confirmed the printed
  JSON matches the new TypeScript types key-for-key (funnel stage names,
  `by_sender_type` keys, `revenue_by_currency`, `signup_trend` shape, etc.);
  separately confirmed both `GET /api/v1/analytics/dashboard/` and
  `GET /api/v1/analytics/platform/` are live-routed and correctly
  auth-gated (`401` unauthenticated) against the real running server.
  `npx tsc --noEmit`, `npm run lint`, `npm run build` all clean.
- **Known limitation, stated honestly** (same as every frontend session so
  far): no browser-automation tool is available in this environment, so the
  actual rendered layout, bar proportions, dark mode, and date-filter
  click-through weren't visually clicked through by me — only the HTTP/data
  contract and build/typecheck/lint were verified. Recommended: run
  `npm run dev` + `manage.py runserver` and open `/dashboard/analytics` and
  `/admin` in a real browser once.

Still deferred: AI settings, knowledge base, campaigns, billing frontends,
and the WhatsApp-account-connection settings page.

## Done (this session — "Frontend: AI assistant settings")

Continued straight into the next module without re-asking (user said
"proceed") — picked AI assistant settings over knowledge base/campaigns/
billing since it's the most central missing piece (the product's own name)
and pairs directly with the inbox's existing `ai_enabled` toggle.

- `types/index.ts`: `AIMode`, `AITone`, `AIProvider`, `AISettings` (mirrors
  `apps.ai.serializers.AISettingsSerializer` field-for-field),
  `UpdateAISettingsPayload` (every field except the four read-only ones),
  `AITestResult`.
- `lib/api.ts`: `getAISettings()`, `updateAISettings(payload)` — both hit
  the singleton `/api/v1/ai/settings/` (no id in the URL, matches the
  backend's per-tenant-singleton design), `testAI(message)` for the
  onboarding-step-7 "test your AI" endpoint.
- New page `app/dashboard/ai/page.tsx`: gated client-side to
  `business_owner`/`manager` (matches the backend's `IsManagerOrAbove`) —
  staff see a plain notice instead of a failed API call. Sections: Identity
  (assistant name, language, tone, welcome/fallback messages, optional
  system prompt override), Behavior (mode, AI-enabled/human-handoff-enabled
  toggles, confidence threshold, comma-separated handoff keywords), Provider
  (openai/anthropic + optional model override), and a live "Test Your
  Assistant" panel that calls the real `/ai/test/` endpoint and renders
  either a handoff reason (amber) or a reply + confidence (emerald) — no
  simulated response, whatever the backend actually returns. Added to the
  shared nav array on all four other dashboard pages.
- **Verified live against the real running dev server and real seeded
  data**: confirmed `GET /api/v1/ai/settings/` and `POST /api/v1/ai/test/`
  are live-routed and `401` unauthenticated; directly invoked
  `AISettingsSerializer` against the real seeded ABC Electronics
  `AISettings` row and confirmed every field name/shape matches the new
  TypeScript type exactly; directly re-invoked the real `wants_human()` +
  `get_provider()` degraded path (no `OPENAI_API_KEY` configured in this
  dev environment, same as every earlier AI-phase session) and confirmed
  it returns exactly `{"handed_off": true, "reason": "openai API key not
  configured"}` — the literal shape the new Test panel's amber branch
  renders. `npx tsc --noEmit`, `npm run lint`, `npm run build` all clean.
- **Known limitation, stated honestly** (same as every frontend session so
  far): no browser-automation tool available, so the rendered form layout,
  checkbox/select styling, and the Test panel's two visual branches weren't
  clicked through by me. Also: since no real OpenAI/Anthropic key is
  configured in this dev environment, the Test panel's "real reply"
  (emerald) branch has only been verified by reading the code path, not
  seen live — only the handoff branch was exercised against real data.

Still deferred: knowledge base, campaigns, billing frontends, and the
WhatsApp-account-connection settings page.

## Done (this session — "Frontend: Knowledge base (RAG)")

Continued straight into the next module again ("proceed improving the
frontend") — picked knowledge base since it pairs directly with the AI
settings page just built (its "grounds the AI's replies" line links
straight here) and closes out the RAG phase's frontend gap.

- `types/index.ts`: `KnowledgeSourceType`, `KnowledgeDocumentStatus`,
  `KnowledgeDocument`, `CreateKnowledgeDocumentPayload`, `KnowledgeChunk` —
  mirror `apps.knowledge.serializers` exactly. Unlike every other
  tenant-scoped type in this file, `KnowledgeDocument` carries an explicit
  `business` id (the model FKs to `Business` directly, not just `tenant`).
- `lib/api.ts`: **first file upload in this codebase.** Extended `apiFetch`
  to detect a `FormData` body and skip the default
  `Content-Type: application/json` header (the browser sets the multipart
  boundary itself) — every existing JSON caller is unaffected.
  `listKnowledgeDocuments`, `createKnowledgeDocument` (builds the `FormData`
  — `business`/`title`/`source_type`/`file`/`raw_text`), `deleteKnowledgeDocument`,
  `listKnowledgeChunks`.
- New page `app/dashboard/knowledge/page.tsx` (staff+ view, manager+
  upload/delete, matches the backend's per-method permission split):
  documents table (title, source type, a status badge, chunk count —
  explicitly noting "N (M embedded — keyword fallback for the rest)" when
  `embedded_chunk_count < chunk_count`, matching this backend's honesty
  about the no-pgvector degraded state from `docs/rag.md`), an inline
  expandable chunk viewer per row (no modal, matching this codebase's
  convention), and an upload form that switches between a text source
  (textarea) and a file source (`.txt`/`.pdf` file input) — the business
  id is picked up silently via the existing `listBusinesses()` call rather
  than asking the user to choose one, since onboarding creates exactly one
  business per tenant. Polls every 5s (same reasoning and cadence pattern
  as the inbox) since processing runs async via Celery and there's no
  real-time channel on this backend. Added to the shared nav array on all
  five other dashboard pages.
- **Verified live against the real running dev server and real seeded
  data**, including the new mechanism specifically (not just the parts
  that repeat prior sessions' patterns):
  - `GET`/`POST /api/v1/knowledge/documents/` confirmed live-routed and
    `401` unauthenticated.
  - Directly serialized a real seeded `KnowledgeDocument` + its
    `KnowledgeChunk` and confirmed the JSON matches the new TypeScript
    types exactly, including the real degraded state
    (`embedded_chunk_count: 0`, `is_embedded: false` — no embedding
    provider key in this dev environment, same as every earlier
    RAG-touching session).
  - **The multipart path specifically** (the actual new risk — everything
    else here repeats established patterns): rather than fighting through
    the mandatory-MFA HTTP login flow for a authenticated write, used
    DRF's `APIClient` with `force_authenticate` as a real seeded business
    owner and posted the *exact* field set `lib/api.ts`'s
    `createKnowledgeDocument()` sends (`business`/`title`/`source_type`/
    `raw_text`, `format="multipart"`) through the real URL routing → view
    → parser → serializer → Celery-dispatch chain. Got a real `201` with
    `status: "pending", chunk_count: 0` — this dev server's Celery is real
    async (not eager), so the response correctly reflects "not processed
    yet," which is exactly why the page polls. Test document deleted
    immediately after.
- **Known limitation, stated honestly** (same as every frontend session so
  far): no browser-automation tool available, so the actual file-picker
  interaction, status badge colors, and expandable-row layout weren't
  clicked through by me. Also: since processing is real async Celery here,
  actually watching a document transition pending → ready in the browser
  needs a running `celery worker` process alongside `runserver` — not
  verified end-to-end through to `ready` in this session (only the
  synchronous `pending` response and the shape of an already-`ready`
  seeded document were confirmed separately).

Still deferred: campaigns, billing frontends, and the
WhatsApp-account-connection settings page.

## Done (this session — "Frontend: Marketing campaigns")

User said "PROCEED" — continued straight into the next module in the
already-stated order. Campaigns was the largest remaining frontend gap:
three linked entities (templates → segments → campaigns) instead of one.

- `types/index.ts`: `TemplateCategory`, `TemplateStatus`, `MessageTemplate`,
  `CreateMessageTemplatePayload`, `SegmentFilters`, `Segment`,
  `CreateSegmentPayload`, `SegmentPreview`, `CampaignStatus`, `Campaign`,
  `CreateCampaignPayload`, `CampaignRecipientStatus`, `CampaignRecipient` —
  mirror `apps.campaigns.serializers` exactly.
- `lib/api.ts`: full CRUD for templates/segments/campaigns plus
  `previewSegment`, `sendCampaign`, `listCampaignRecipients`.
- New page `app/dashboard/campaigns/page.tsx` (staff+ view, manager+
  create/edit/delete/send — matches the backend's per-method permission
  split) with three stacked sections:
  - **Templates**: table + inline per-row edit (status/WhatsApp template
    name/rejection reason — the exact fields the backend docstring says
    are "deliberately writable here" since real Meta approval happens
    outside this system) + a create form with `{{n}}` placeholder syntax
    called out.
  - **Segments**: table (customer count, a human-readable filter summary)
    with an inline "Preview" expand hitting the real no-side-effect preview
    endpoint, plus checkbox filters for lead status/source and a
    comma-separated tags field on create.
  - **Campaigns**: table (status badge, recipient/sent/failed/skipped
    counts) + Send button (draft/scheduled only) + an inline recipients
    expand (per-customer outcome, skip/error reason). A warning banner
    appears on the create form when no template is `approved` yet — a
    campaign can still be created against a draft template (the backend
    doesn't block that), but sending it will structurally fail until
    approval is recorded, so the UI says so up front rather than letting
    the send fail as a surprise.
  - Polls every 5s (same reasoning as the knowledge base — campaign sends
    run async via Celery, no real-time channel exists).
  - Business id picked up silently via `listBusinesses()`, same pattern as
    every other business-scoped page.
- Added to the shared nav array on all six other dashboard pages.
- **Verified live against the real running dev server and real seeded
  data**, including the send path specifically:
  - All three list endpoints confirmed live-routed and `401`
    unauthenticated.
  - Directly serialized a real seeded `MessageTemplate`, `Segment`, and
    `Campaign` (Kijani Foods' seeded "Weekly Promo"/"Opted-in
    customers"/"Sample Weekly Promo Campaign") and confirmed every field
    matches the new TypeScript types exactly.
  - **The send path**: used DRF's `APIClient` with `force_authenticate` as
    the real seeded Kijani Foods owner and called
    `POST /api/v1/campaigns/{id}/send/` on that real seeded draft
    campaign — the exact call `sendCampaign()` makes. Got a real `200`
    with `status: "scheduled"` (this dev server's Celery is real async,
    not eager, so the response correctly reflects "queued, not yet
    processed" — same shape the UI's poll is built to catch). Also called
    the real recipients endpoint and confirmed the `Paginated<T>` envelope
    matches exactly.
  - **Cleanup, stated honestly**: this mutated real seeded dev data — the
    seeded campaign moved from `draft` to `scheduled`, which breaks
    `seed_dev_data`'s documented invariant ("never auto-sent"). Confirmed
    no Celery worker had consumed the queued task yet (still `scheduled`,
    zero `CampaignRecipient` rows), then reset it back to `draft` directly
    via the ORM to restore the documented seed state. Worth remembering:
    unlike the knowledge-base multipart verification (a throwaway document,
    cleanly deleted), this test ran directly against a real named seed
    fixture because campaign send needs an existing draft campaign with a
    real segment/template already attached — creating a disposable one
    for this check would have been more code for less realism. If a
    Celery worker happens to be running during a similar future check,
    the send will actually complete (and likely fail structurally, no
    real WhatsApp account/valid token) rather than sit resettable in
    `scheduled` — worth checking recipient rows first, as done here,
    before assuming a reset is safe.
  - `npx tsc --noEmit`, `npm run lint`, `npm run build` all clean.
- **Known limitation, stated honestly** (same as every frontend session so
  far): no browser-automation tool available, so the three-section layout,
  status badges, and inline expand/edit rows weren't clicked through by
  me visually.

Still deferred: billing frontend and the WhatsApp-account-connection
settings page.

## Done (this session — "Frontend: Billing + WhatsApp account connection")

User said "PROCEED" then "KEEP GOING, finalize the whole frontend, then
before UI/UX we do testing" — built the last two deferred modules in one
pass, which closes out every backend-complete/frontend-missing module
tracked in this file since the first frontend session.

- `types/index.ts`: `UsageLimitName`, `UsageLimit`, `UsageSummary`,
  `InvoiceStatus`, `Invoice`, `GenerateInvoicePayload`,
  `WhatsAppAccountStatus`, `WhatsAppAccount` (deliberately has no
  `access_token` field — the API never returns it, so the read type
  doesn't pretend it exists), `CreateWhatsAppAccountPayload`.
- `lib/api.ts`: `getUsageSummary`, `listInvoices`, `generateInvoice`
  (super admin), `listWhatsAppAccounts`, `createWhatsAppAccount`,
  `updateWhatsAppAccount` (also how reconnecting with a fresh token works
  — same endpoint, `access_token` is just one more writable field).
- New `components/Meter.tsx`: a used-vs-capacity track, deliberately
  separate from `BarList` — a Plan limit is one quantity against its own
  ceiling (color = proximity to the limit: emerald/amber/red), not a
  categorical comparison, so it earns its own small component rather than
  overloading `BarList` with a mode flag.
- New page `app/dashboard/billing/page.tsx`: Plan Usage (staff+, a `Meter`
  per limit — team members, WhatsApp accounts, customers, AI messages/mo,
  campaign sends/mo) and Invoices (manager+, matches the backend's own
  per-view permission split). States "no payment gateway is connected"
  plainly rather than implying invoices are ever auto-charged.
- New page `app/dashboard/whatsapp/page.tsx` (manager+ only, staff see a
  notice — matches `IsManagerOrAbove` on both endpoints): connected-number
  cards with a status badge and last-error surfaced, a connect form, and
  a per-account "Reconnect" flow (submits a fresh `access_token` via the
  same `PATCH` the create path uses). Explicitly tells the user the token
  is never shown again after saving, matching the backend's actual
  contract (write-only, never serialized back, per `docs/security.md`).
- `app/admin/page.tsx`: added a "Generate Invoice" action per tenant row
  next to the existing Suspend/Activate button (super admin only,
  idempotent per calendar month on the backend, so a double-click is
  harmless) — disabled with an explanatory title when a tenant has no
  plan assigned, since the backend rejects that with a clean 400.
- "WhatsApp" and "Billing" added to the shared nav array on all nine
  dashboard pages now (the full set: Overview, Products & Orders, Inbox,
  AI Assistant, Knowledge Base, Campaigns, WhatsApp, Billing, Analytics).
- **Verified live against the real running dev server and real seeded
  data**, including both real write paths:
  - All four new endpoints confirmed live-routed and `401`
    unauthenticated.
  - Directly computed `usage_summary()` and serialized a real seeded
    `Invoice` and `WhatsAppAccount` — every field matches the new
    TypeScript types exactly, and confirmed `access_token` is genuinely
    absent from the real serialized output (not just documented as such).
  - **The WhatsApp connect path**: used DRF's `APIClient` with
    `force_authenticate` as the real seeded Mambo Fashion owner (chosen
    specifically because it had zero existing accounts, so the real
    `max_whatsapp_accounts=1` Plan limit wasn't tripped) and posted the
    exact field set `createWhatsAppAccount()` sends. Got a real `201`
    with `status: "connected"` (the model's real optimistic-connect
    behavior — no live Meta handshake happens) and confirmed
    `access_token` was absent from the response body itself, not just
    from a hand-read of the serializer source. Test account deleted
    immediately after.
- **Known limitation, stated honestly** (same as every frontend session so
  far): no browser-automation tool available, so the Meter's color
  thresholds, the account cards, and the reconnect flow weren't clicked
  through by me visually.

**This closes out the frontend module list.** Every backend phase this
project has built (Phases 1–15 + the security hardening pass) now has a
working frontend surface. Remaining `docs/ROADMAP.md` gaps are backend-only
work (business settings UI polish, Docker/deployment) or things flagged as
deliberately out of scope (see "Known gaps flagged honestly" below) — not
missing frontend modules.

## Done (this session — "Frontend testing: Vitest + Playwright")

User asked to finalize the frontend (see above) then, explicitly, "before
jumping to design the UI/UX we do the testing" — this closes the gap every
frontend session in this file has flagged: no browser-automation tool was
ever available to actually click through a page. Full detail in the new
`docs/testing.md`; this is the roadmap-level summary.

- **Vitest + React Testing Library** (`npm run test`, `vitest.config.ts`):
  component/unit tests, no server needed. 24 tests across `BarList`,
  `Meter` (new — see below), `StatTile`, `Alert`, `Field`, `Sparkline`,
  and one page-level test (`app/dashboard/ai`) proving the manager+ role
  gate actually renders different content per role with a mocked API.
  **Two real bugs found and fixed while writing these, before Playwright
  even ran**: (1) `components/Field.tsx` — reused by nearly every form in
  this app — never associated its `<label>` with its `<input>` (no
  `htmlFor`/`id`, just adjacent siblings); fixed with `useId()`, a real
  accessibility fix, not just a test-friendliness one. (2)
  `Sparkline.tsx`'s `aria-label` hardcoded "tenants" (always plural) while
  its visible caption correctly singularized — the accessible name and
  the visible text disagreed; fixed to share the same logic.
- **Playwright** (`npm run test:e2e`, `playwright.config.ts`): a real
  Chromium browser against the real running frontend **and** real running
  backend. Two projects: `unauthenticated` (login form, wrong-credentials
  error, route-guard redirects off `/dashboard` and `/admin`) and
  `authenticated` (one smoke test per dashboard page — all nine plus
  Sessions plus logout — reusing a saved session instead of logging in
  per spec).
- **New backend management command** `provision_e2e_user` — creates (or
  idempotently resets) one fixed, dedicated-tenant Business Owner account
  with MFA **already enrolled against a known TOTP secret**, since this
  platform's mandatory MFA (`docs/mfa.md`) means there's no way to test
  the real login flow without a real, already-enrolled account. The
  email/password/secret are fixed dev-only values living in exactly two
  places that must stay in sync (`provision_e2e_user.py` and the new
  `frontend/e2e/testUser.ts`) — same "documented dev-only credential"
  pattern as `SUPERADMIN_EMAIL`/`PASSWORD`, not a real secret.
  `e2e/global-setup.ts` drives the **real** `/login` → `/login/mfa-verify`
  UI flow once per run (typing the password, computing a valid 6-digit
  TOTP code from the known secret via the `otpauth` npm package, typing
  that too — not a localStorage shortcut) and saves the resulting session
  via Playwright's `storageState` for every other spec to reuse.
- **A real bug caught on the very first real Playwright run** — not
  contrived, this happened live while building the suite:
  `POST /api/v1/auth/logout/` returns `205 Reset Content` with an empty
  body; `apiFetch()` only special-cased `204` before calling `res.json()`,
  so logout crashed on "Unexpected end of JSON input" with no `try/catch`
  above it to swallow it — the session *was* cleared client-side (a
  `finally` block), but `router.push("/login")` never ran, silently
  stranding the user on `/dashboard` after clicking Log out. Every
  `tsc`/`eslint`/`next build`/Vitest run across every prior session missed
  this, because a mocked API response is never accidentally body-less
  unless you think to simulate one — this is exactly the class of bug
  real end-to-end testing exists to catch. Fixed in both `apiFetch` and
  `pendingTokenFetch` (`lib/api.ts`) by reading the response as text first
  and only `JSON.parse`-ing it if non-empty, rather than assuming every
  non-204 response has a JSON body. Playwright re-run afterward: 15/15
  passing, including the logout spec.
- `scripts/test.ps1` now also runs `npm run test` (Vitest) — Playwright is
  deliberately NOT wired into this script, since it needs both the
  backend and frontend dev servers running live, unlike everything else
  the script runs standalone; documented as a separate manual step in
  `docs/testing.md`.
- New `docs/testing.md` (test-layer breakdown, running instructions, the
  E2E account, the logout bug writeup, what each layer deliberately
  doesn't cover); README's "Running tests" section and documentation
  index both updated.
- Final state: 24/24 Vitest tests passing, 15/15 Playwright tests passing
  (4 unauthenticated + 11 authenticated), `npx tsc --noEmit`/
  `npm run lint`/`npm run build` all clean.

## Done (this session — "Public marketing/landing page")

User asked for "the best UI/UX ... something which can convince
customers." The app previously had no public marketing page at all — `/`
was a bare client-side redirect straight to `/login` or the dashboard, so
a prospective customer had nothing to see before signing in.

- **New backend endpoint**: `GET /api/v1/tenants/plans/public/`
  (`PublicPlanListView`, `AllowAny`, no auth) — a slim `PublicPlanSerializer`
  (name/description/price/currency/limits, deliberately excluding
  `is_active`/`is_default`/`max_storage_mb` — the last one isn't actually
  enforced anywhere yet, see `docs/billing.md`, so advertising it publicly
  would overpromise). Exists so the pricing section reads real, live Plan
  data instead of numbers hardcoded in the frontend that could silently
  drift from what's actually configured. Added to `audit_permissions`'s
  `KNOWN_PLATFORM_WIDE_VIEWS` allowlist (same reasoning as the existing
  `PlanListCreateView` entry — `Plan` isn't tenant data). Verified live:
  real seeded `Starter`/`Growth` plans returned correctly; `manage.py
  audit_permissions` and the full 246-test `pytest` suite both still clean.
- **New marketing page** at `/` (`components/marketing/*`: `MarketingNav`
  with a working mobile menu, `Hero` with a hand-built illustrative chat
  mockup — not a real customer's conversation — demonstrating the actual
  AI-then-handoff behavior this platform runs, `FeatureGrid` (8 cards, one
  per real shipped module), `HowItWorks`, `SecuritySection`, `Pricing`
  (fetches the new public endpoint live), `FinalCTA`, `MarketingFooter`).
  `app/page.tsx` now renders this for anyone without a session and
  redirects only an already-logged-in visitor to their dashboard — the
  reverse of before.
- **Deliberately honest about what this platform actually is**: no
  self-serve signup exists (onboarding is super-admin-driven via
  `/admin` — see the README) — so every CTA says "Get in touch" /
  "Talk to us" and opens a `mailto:` link, never a fake signup form that
  would pretend to create an account on submit. No fabricated customer
  testimonials, logos, or user counts — the trust/security section states
  only controls that are actually built and tested (MFA, encryption,
  audited tenant isolation, audit logging, rate limiting), each
  cross-checked against `docs/security.md`/`docs/mfa.md` while writing it.
- **Visually verified with real screenshots**, not just build/typecheck —
  the first real payoff of having Playwright installed: full-page
  Chromium screenshots at desktop (1440px) and mobile (390px), both light
  and dark. Caught and fixed a real gap this way: the nav's link row was
  `hidden md:flex` with **no mobile fallback at all** — a mobile visitor
  had no way to reach `#features`/`#pricing`/etc. except scrolling. Added
  a proper hamburger menu with a slide-down panel; re-screenshotted to
  confirm.
- **New Playwright specs** (`e2e/login.unauth.spec.ts`, unauthenticated
  project): the marketing page renders instead of redirecting for an
  anonymous visitor (the mirror image of the existing
  redirect-off-`/dashboard` tests), the pricing section actually round-trips
  real data from the new public endpoint (`Growth` / `USD 49`, not just
  that a loading state renders), and the mobile menu opens and its Login
  link navigates correctly.
- Final state: 18/18 Playwright, 24/24 Vitest, 246/246 backend pytest,
  clean `tsc`/`eslint`/`next build`/`audit_permissions`.

## Done (this session — "App shell redesign + CI fix")

User flagged two things: the dashboard app itself "looks very local" (plain
top nav, no footer) even after the marketing page got real design
attention, and a real GitHub Actions failure pasted directly from CI.

- **CI fix (real, reproduced locally before fixing)**: `Cannot find name
  'LayoutProps'`. `app/layout.tsx` uses Next.js 16's generated
  `LayoutProps<"/">` ambient type, written to `.next/types/` — which only
  exists after `next dev`/`next build` has run once. The workflow ran
  `npx tsc --noEmit` *before* `npm run build`, so a fresh checkout has no
  `.next/types/` yet and typecheck fails — passed locally every time this
  session only because `.next` already existed from repeated manual
  builds. Reproduced by deleting `.next` and re-running `tsc --noEmit`
  locally (confirmed the exact CI error), fixed by adding a `next typegen`
  step (generates just the types, no full build) before Typecheck, and
  verified the corrected order end-to-end locally. Also bumped
  `setup-node` from Node 20 (deprecated on GitHub-hosted runners, and
  already inconsistent with the README's documented "Node 22+"
  requirement) to 22, and added the Vitest suite as its own CI step —
  it existed but was never wired into CI until now.
- **`DashboardShell` rebuilt as a sidebar layout** — the actual reason the
  top nav looked cramped: it had grown to 9 items (Overview through
  Analytics) squeezed into one horizontal row with no overflow handling.
  Now: a persistent left sidebar (desktop) with icons per section (a new
  shared `components/Icons.tsx` — promoted from `components/marketing/`
  since both the app and the marketing site now draw from the same icon
  set), active-route highlighting, a user card with initials avatar and a
  one-click logout icon button, and a slide-out drawer with backdrop on
  mobile (same interaction pattern as the marketing nav's mobile menu).
  Every existing page's `{label, href}[]` nav prop works unchanged — icons
  are looked up by href, falling back to a generic icon for anything not
  in the map, so no page needed editing for this.
- **New app footer** on every dashboard page (in `DashboardShell`, not
  per-page) — copyright line + a link back to the new marketing homepage.
- **A real, live-verified bug fix along the way**: while screenshotting
  the new sidebar on mobile, tables (Team roster, Products, Orders,
  Campaigns, Invoices, Sessions, tenants list — 8 pages, 11 tables) were
  clipped instead of scrollable — their wrapper used `overflow-hidden`
  (for rounded corners) with no horizontal-scroll fallback, so the
  rightmost column (often "Actions") was simply unreachable on a narrow
  screen. Switched those wrappers to `overflow-x-auto`; verified via
  Playwright's `page.evaluate()` that the container is actually
  scrollable (`scrollWidth > clientWidth`, `overflowX: "auto"`) and that
  scrolling it reveals the previously-unreachable column — not just that
  it "looks fine" in a static screenshot, which alone can't show
  scrollability.
- **Visually verified with real screenshots** (light/dark, desktop/mobile,
  drawer open) before calling this done, same discipline as the marketing
  page — this is what caught the table-overflow issue above; it wasn't
  visible in the first round of desktop-only screenshots.
- Final state: 18/18 Playwright, 24/24 Vitest, 246/246 backend pytest,
  clean `tsc`/`eslint`/`next build`, and the exact CI failure the user
  pasted reproduced and fixed locally, not just guessed at.

## Done (this session — "Premium enterprise frontend transformation")

User's brief (after a first draft that described entities this app
doesn't have — students, HR, library, transport, tenant switching —
which was flagged and corrected before starting) was explicit: transform
the frontend into something that reads as a serious commercial SaaS
product, built strictly on this app's real modules, with hard guardrails
against fabricating functionality, weakening security, or introducing a
tenant switcher (this platform's single-tenant isolation is a deliberate,
audited feature, not a gap). Full detail in the new
`docs/frontend-design-system.md`; this is the roadmap-level summary.

**Foundation**
- New semantic design-token layer in `app/globals.css` (`--color-primary`,
  `-success/-warning/-danger/-info`, `-page/-surface/-surface-elevated`,
  `-border/-divider`, `-ink/-ink-secondary/-ink-muted/-ink-disabled`,
  `-chart-1..5`, plus a shadow scale) — explicit light **and** dark value
  for every role, layered over (not replacing) the existing zinc/emerald
  utility classes.
- **A real, validator-confirmed accessibility bug fixed**: the message-
  sender-type chart reused one fixed hex per category across both color
  modes. Running it through the dataviz skill's actual palette validator
  (not eyeballing it) found "System" (zinc-400) failed the chroma floor —
  it read as gray, not a color — and "Campaign" (amber-500) failed the
  dark-mode lightness band. Replaced with a 5-hue set that validates as
  one set in both modes (`--chart-1..5`), confirmed by re-running the
  validator, not assumed.
- `lib/navigation.ts`: one canonical `DASHBOARD_NAV` (with icons attached
  per item) replacing an identical `{label, href}[]` array that had been
  copy-pasted into 9 separate page files, plus the separate href-keyed
  icon lookup table `DashboardShell` used to maintain independently.
- `lib/errors.ts`: `getErrorMessage(err, fallback)` replacing the
  `err instanceof ApiError ? err.message : "..."` pattern repeated 49
  times across every page's catch blocks — same behavior, one place to
  get it right.

**App shell**
- `DashboardShell` rewired onto the new nav/token system, plus a real
  **Ctrl/Cmd+K command palette** (`CommandPalette.tsx`) — navigates to
  real routes only (sourced from the same `DASHBOARD_NAV` the sidebar
  uses) plus Log out; deliberately does **not** fake a search across
  records, since no backend search endpoint exists for it to call.
  Keyboard-navigable, closes on Escape/backdrop, returns focus on close.

**New shared components**: `Button` (primary/secondary/ghost/danger
hierarchy), `EmptyState` (title+description+action, wired into the
WhatsApp page's connected-numbers panel), `Skeleton` and `PageLoading`
(the latter replacing 11 identical copies of plain "Loading…" text — the
full-page auth-gate state every dashboard/admin page shows before
`useRequireAuth()` resolves).

**Campaigns refactor**: `app/dashboard/campaigns/page.tsx` was 862 lines
managing three entities (templates/segments/campaigns) in one file.
Refactored into 6 focused presentational components
(`components/campaigns/{Templates,Segments,Campaigns}Section.tsx` +
their matching `*Form.tsx`) plus a `shared.ts` for common style constants
and lookups — the page itself is now ~340 lines and is purely the
composition/state/data-fetching layer, same route, same functionality.
Verified pixel-identical via screenshot comparison before/after.

**New backend-side testing infrastructure**: `provision_e2e_user` now
provisions **two** fixed accounts (a business owner, and new this pass, a
dedicated super admin — `e2e-admin@wabaai.local`, separate from the real
`SUPERADMIN_EMAIL` account) so authenticated e2e/visual-QA coverage can
reach `/admin`, which the business-owner account correctly cannot.

**New tests**: `DashboardShell.test.tsx` (nav rendering, active-route
highlighting, the `initials()` helper across one-word/multi-word/empty
names, mobile drawer open/close-on-nav/close-on-backdrop, logout) — this
component had zero dedicated test coverage before, despite being the most
complex shared component in the app.

**A real, live-verified bug fixed along the way**: `Inbox`'s two-pane
layout (fixed `w-80` list + `flex-1` thread, `overflow-hidden` container)
never adapted below `lg` — on a 390px phone the message thread was
squeezed to ~70px and clipped, not readable. No page-level horizontal
overflow occurred (confirmed via `document.body.scrollWidth` — the
container's own `overflow-hidden` silently clipped instead), so this
wasn't the same class of bug as the earlier table-overflow fix. Fixed
with the standard mobile master-detail pattern: below `lg`, show exactly
one pane at a time (list, or thread with a Back control) instead of both
fighting for ~390px combined. Verified against a real seeded conversation
in both directions (list → thread → back), and confirmed desktop is
completely unaffected.

**Manual visual QA — screenshots actually read, not just asserted
against** — caught two more real bugs neither Vitest nor Playwright's
existing assertions were checking for: a pluralization bug
("`replyies`" instead of "`replies`" in the Analytics avg-response-time
stat tile), and stale placeholder copy on the dashboard overview page
("the AI settings and knowledge base modules land in the next build
phases") left over from a session before those modules existed. Both
fixed; full writeup of why this category of bug needs a human pass, not
just automated coverage, is in the new "Manual visual QA" section of
`docs/testing.md`.

**Validation, run for real, not just described**: `tsc --noEmit`,
`eslint`, `next build`, 35/35 Vitest (24 previous + 11 new
`DashboardShell` tests), 18/18 Playwright (including a real e2e-text-copy
fix caught by the suite itself — the WhatsApp empty-state assertion still
expected the old literal string after the `EmptyState` copy change), and
246/246 backend `pytest` (untouched this pass, confirmed still green) —
run repeatedly through the session, not once at the end.

**Explicitly not built, stated honestly** (per the brief's own "do not
fabricate" guardrails): a notification center, a global-search backend,
and an audit-log viewer UI — none have a real backend endpoint to call
yet, and building frontend for them would mean either fabricating data or
building real backend features that weren't asked for as part of this
pass. `Button` and `EmptyState` are built and demonstrated but not
retrofit onto every existing page — see `docs/frontend-design-system.md`'s
"Known gaps" section for the full, honest list of what this pass
deliberately left alone and why.

## Not built yet — placeholder app directories only

`backend/apps/{notifications,audit}/` exist as empty Python packages
(just `__init__.py`), not registered in `INSTALLED_APPS`, no
models/views. They map to the spec's remaining phases:

| Phase | Spec # | Builds |
|---|---|---|
| 4 (remainder) | Business management | Business settings UI (opening hours, branding, etc.) — staff invites are done, see above |
| 14 | Frontend polish | WhatsApp-style inbox, onboarding wizard, full dashboard pages |
| 16 | Docker/deployment | Production Dockerfiles, CI, real deployment target |

Also not yet started: `docs/deployment.md`, `docs/troubleshooting.md` —
write these when their corresponding phase lands, not before (a doc for
code that doesn't exist yet just goes stale).

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
- Rate limiting is designed for (`MAX_UPLOAD_SIZE_MB` etc. in settings)
  but not implemented — see `docs/security.md`. File upload validation
  was resolved in Phase 9 (`apps.knowledge`'s extension whitelist).
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
