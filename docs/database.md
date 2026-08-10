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

**Staff management** (`/api/v1/staff/`, spec section 6's "Business Owner can manage
staff") adds no new model — it's CRUD on `accounts.User` scoped to the
caller's own tenant, restricted to creating/editing `manager`/`staff`
roles only. Rules enforced server-side, not just at the serializer layer:
a business owner can never create another `business_owner` or
`super_admin` this way; `PATCH` can't target the business owner record
itself or the caller's own account (no self-service role change, no
self-lockout); a super admin (`tenant=None`) is rejected with a clear 400
on create rather than hitting the `super_admin_has_no_tenant`-adjacent
`NOT NULL` on `tenant` for the new user.

### `common.AuditLog`
Platform-wide audit trail (spec section 19): `tenant`, `user`, `action`
(free-text code, e.g. `USER_CREATED`, `BUSINESS_ONBOARDED`,
`TENANT_SUSPENDED`), a generic FK to the affected object, `metadata` (JSON),
`ip_address`, `created_at`. `AuditLog.log(...)` is the write helper —
services in later phases call it rather than writing `AuditLog.objects.create(...)`
directly.

### `customers.Customer`
CRM contact per spec sections 7/15: `name`, `phone`, `email`, `location`,
`tags` (JSON list of strings — not a normalized Tag model, see
`docs/ROADMAP.md`), `source`, `status` (lead pipeline:
`new|contacted|qualified|proposal|converted|lost`), `notes`,
`last_interaction_at`. `(tenant, phone)` is a unique constraint — the same
phone number can exist across different tenants, never twice within one.
`marketing_opt_in` (default `False` — opt-in, not opt-out, per WhatsApp
Business policy) + `marketing_opt_in_at` (stamped by the serializer
whenever the flag is set `True`, real consent-timing evidence rather than
just a boolean) added in Phase 11; see `docs/campaigns.md`. Inherits
`core.models.BaseModel`.

### `conversations.Conversation` / `ConversationAssignment`
`Conversation` per spec section 8, scoped down for this phase: exactly one
`customer` and at most one `assigned_to` staff member (sufficient for 1:1
WhatsApp chat) rather than a full `ConversationParticipant` model —
see `docs/ROADMAP.md`. Fields: `channel` (`whatsapp` only for now),
`status` (`open|pending|resolved|closed`), `ai_enabled`, `tags` (JSON list),
`last_message_preview`/`last_message_at`/`unread_count` (denormalized,
updated by `Conversation.record_message()`). `ConversationAssignment` is a
separate *history* log (who was assigned when) written by
`Conversation.assign_to()` — not exposed for direct write via the API.
Both inherit `core.models.BaseModel`.

### `messaging.Message` / `MessageAttachment`
Note the app label is `messaging`, not `messages` — `apps.messages`'s
directory name matches the spec, but its `AppConfig.label` had to be
distinct from `django.contrib.messages` (already installed) or Django's
app registry would crash on startup. Fields per spec section 8:
`sender_type` (`customer|staff|ai|system`), `sender_user` (FK, staff only),
`direction` (`inbound|outbound`), `message_type`, `content`, `status`,
`external_message_id` (WhatsApp's `wamid.*`, populated by the webhook for
inbound / by the send task for outbound, unique per tenant when set). Both
inherit `core.models.BaseModel`.

**Note on message creation via the API**: `POST /api/v1/messages/` only
accepts `sender_type=staff` — customer messages arrive via the WhatsApp
webhook (`apps.whatsapp`), not this endpoint. `direction` and `sender_user`
are always server-derived, never client input.

### `whatsapp.WhatsAppAccount` / `MessageEvent`
Per-business WhatsApp Cloud API connection (spec section 7):
`business` (FK), `phone_number`, `phone_number_id` (unique — Meta's ID,
used to resolve inbound webhooks to a tenant), `business_account_id`,
`access_token_encrypted` (Fernet/AES via `core.crypto`, accessed only
through the `.access_token` property, never serialized), `status`
(`pending|connected|disconnected|error`), `connected_at`, `last_sync_at`,
`last_error`. `MessageEvent` is the webhook idempotency log deferred from
the Customer CRM phase — one row per `(whatsapp_account, external_event_id)`
actually processed; Meta redelivers webhooks on timeout, and without this
a retry would create a duplicate `Message`. Both inherit
`core.models.BaseModel`. See `docs/whatsapp.md` for the full flow.

### `ai.AISettings`
One row per `Business` (`OneToOneField`), created lazily on first
`GET /api/v1/ai/settings/` rather than at business-creation time, so a
business's AI stays fully configured with sane defaults even if nobody
ever visits an "AI settings" screen. Fields per spec section 11: `mode`
(`ai|human|hybrid`), `ai_enabled`, `human_handoff_enabled`,
`confidence_threshold` (float, default `0.6` — below this the reply is
treated as unreliable and handed off), `handoff_keywords` (JSON list,
case-insensitive substring match against the inbound message),
`assistant_name`, `system_prompt` (blank = built from the business's own
profile at reply time, never invented), `tone`, `welcome_message`,
`fallback_message` (shown to the customer on handoff — the handoff itself
is otherwise invisible to them), `max_response_length`, `provider`
(`openai|anthropic`), `model_name` (blank = provider's own default model).
Inherits `core.models.BaseModel`. See `docs/ai.md` for the full reply/
handoff flow.

### `knowledge.KnowledgeDocument` / `KnowledgeChunk`
RAG knowledge base (spec section 9). `KnowledgeDocument`: `business` (FK),
`uploaded_by`, `title`, `source_type` (`upload|text`), `file` (single
`.txt`/`.pdf`, validated), `raw_text` (pasted content, or text extracted
from `file` once processed), `status` (`pending|processing|ready|failed`),
`error_message`, `chunk_count`, `embedded_chunk_count` (how many chunks
got a real embedding vs. fell back to keyword-only — see `docs/rag.md`).
`KnowledgeChunk`: `document` (FK), `chunk_index`, `content`, `embedding`
(`JSONField`, a plain float list — **no pgvector extension on this
project's Postgres instance**, so retrieval does pure-Python cosine
similarity rather than a vector index; see `docs/rag.md` for the
documented upgrade path), `embedding_model` (blank if never embedded).
Unique `(document, chunk_index)`. Both inherit `core.models.BaseModel`.

### `campaigns.MessageTemplate` / `Segment` / `Campaign` / `CampaignRecipient`
Marketing campaigns (spec sections 12, 26) — see `docs/campaigns.md` for
the full compliance model. `MessageTemplate`: `business`, `name`,
`whatsapp_template_name` (blank until submitted to Meta), `category`
(`marketing|utility|authentication`), `language_code`, `body_text`
(`{{1}}`-style placeholders), `status`
(`draft|pending_approval|approved|rejected` — **set manually**, no real
Meta Template API access this session), `rejection_reason`;
`variable_count` is a computed property, not a stored field. `Segment`:
`business`, `name`, `description`, `filters` (JSON — `statuses`/`sources`/
`tags`, any-match lists; empty matches every opted-in customer).
`Campaign`: `business`, `segment` (FK, `PROTECT`), `template` (FK,
`PROTECT`), `template_variables` (JSON list, applied to every recipient —
no per-recipient personalization yet), `status`
(`draft|scheduled|sending|sent|failed|cancelled`), `scheduled_at`,
`started_at`, `completed_at`, `error_message`,
`recipient_count`/`sent_count`/`failed_count`/`skipped_count`.
`CampaignRecipient`: `campaign` (FK), `customer` (FK), `message`
(`OneToOneField` to `messaging.Message`, nullable), `status`
(`pending|sent|failed|skipped`), `skip_reason`, `error_message`,
`sent_at`; unique `(campaign, customer)`. All four inherit
`core.models.BaseModel`.

### `products.Product`
Fields per spec section 13: `name`, `sku` (optional — `(tenant, sku)`
unique only when set, same conditional-constraint pattern as
`Message.external_message_id`), `description`, `category` (free text, not
a fixed enum — unlike `Business.category`, product categories are too
business-specific for a platform-wide choice list), `price`/`currency`,
`stock`, `is_available` (manual override — can be marked unavailable even
with stock), `status` (`draft|active|archived`), `image` (single
`ImageField`, matching the `Business.logo` pattern — not a gallery; no
multi-image upload infrastructure exists yet). `is_orderable` is a
computed property (`is_available and status == active and stock > 0`),
not a stored field. Inherits `core.models.BaseModel`.

**Serializer quirk worth knowing**: `sku`'s conditional `UniqueConstraint`
(`condition=~Q(sku="")`) confuses DRF's automatic field generation into
marking it `required=True` even though the model has `blank=True` —
`ProductSerializer` declares `sku` explicitly to override this. If a
future field hits the same "required when it shouldn't be" surprise,
suspect a conditional `UniqueConstraint` first.

### `orders.Order` / `OrderItem`
Fields per spec section 14. `status` uses a proper state machine
(`Order.ALLOWED_TRANSITIONS`, forward-only: `pending → confirmed →
processing → ready → delivered`, `cancelled` reachable from any
non-terminal state) rather than a free-text field anyone can set to
anything — this is what actually implements the spec's "require
appropriate confirmation before finalizing an order." Only
`POST /api/v1/orders/{id}/status/` can change `status`; a plain `PATCH`
on the order only touches `notes`. Moving to `confirmed` stamps
`confirmed_by`/`confirmed_at`.

`OrderItem` **snapshots** `product_name`/`unit_price` from the `Product`
at order-creation time — a later price change on the product must never
retroactively alter a historical order's total (test-verified:
`tests/test_orders.py::test_price_snapshot_survives_later_product_price_change`).
`Order.total_amount` is denormalized and recalculated via
`Order.recalculate_total()` after items change. `Order.customer` and
`Order.conversation` (nullable — set when an order originates from a
WhatsApp conversation) both inherit the cross-tenant-FK validation
pattern from `docs/multi-tenancy.md`. Both models inherit
`core.models.BaseModel`.

**Known gap, flagged honestly**: creating an order does **not** decrement
`Product.stock` — inventory management is manual for now (see
`docs/ROADMAP.md`); `tests/test_orders.py::test_stock_is_independent_of_order_creation`
documents this on purpose so a future change to the behavior fails a test.

## Base model layer (`backend/core/models.py`)

Every tenant-scoped domain model (customers, conversations, products,
orders, ...) inherits `core.models.BaseModel`, which combines:

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
own auth-specific base classes). `Customer`, `Conversation`,
`ConversationAssignment`, `Message`, and `MessageAttachment` all do.

## Reusable view mixins (`backend/core/mixins.py`)

`TenantScopedQuerysetMixin` (filters a DRF generic view's queryset to
`request.user.tenant_id`, bypassed for `is_superuser`) and
`TenantScopedCreateMixin` (injects `tenant` on create from
`request.user.tenant`, rejecting with a clean 400 if the caller is a
super admin with no tenant of their own) are used by every tenant-scoped
list/create view — see `apps/customers/views.py`,
`apps/conversations/views.py`, `apps/businesses/views.py`. When a
client-supplied FK could reference an object in *another* tenant (e.g.
`Conversation.customer`, `Message.conversation`), the serializer validates
that FK's tenant explicitly (`validate_<field>`) — the create-mixin alone
only protects the object being created, not objects it points to.

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
- `Customer`: unique `(tenant, phone)`; composite indexes on
  `(tenant, status)` and `(tenant, phone)`
- `Conversation`: composite indexes on `(tenant, status)` and
  `(tenant, assigned_to)`
- `Message`: composite index on `(tenant, conversation, created_at)`;
  unique `(tenant, external_message_id)` when `external_message_id` is set
- `WhatsAppAccount`: unique `phone_number_id`; composite index on
  `(tenant, status)`
- `MessageEvent`: unique `(whatsapp_account, external_event_id)` — the
  webhook idempotency guard

## Local database credentials (this machine)

Native PostgreSQL 18, database `whatsapp_business_ai`, role `waba_user`
(created via `scripts\create-db.ps1`, which prompts for the `postgres`
superuser password — never stored in any file). Actual credentials for
this checkout live only in the untracked `.env`.
