# Billing

`apps.billing` — actually enforces `tenants.Plan` limits (spec section 24,
25) instead of leaving them as unread integers, tracks usage, and
generates invoice records. **No real payment gateway was available while
building this** (no Stripe/Flutterwave/etc. credentials — same
category of constraint as OpenAI/Anthropic/Meta all session) — `Invoice`
is a real, correctly-modeled billing record, but nothing in this codebase
charges a card. See [What "generating an invoice" means here](#what-generating-an-invoice-means-here-and-what-it-doesnt)
below.

## No separate `Subscription` model — a deliberate decision

The spec names `Subscription` alongside `UsageRecord`/`Invoice`. This
project doesn't build one: `tenants.Tenant` already carries `plan` (FK),
`status` (`trial|active|suspended|cancelled`), `trial_ends_at`, and
`subscription_ends_at` (see `docs/database.md`) — everything a
`Subscription` model would add. Building a second model duplicating that
state risks two disagreeing sources of truth (imagine `Tenant.status=
"active"` next to a hypothetical `Subscription.status="past_due"`) for no
real benefit at this project's stage, where there's no payment gateway
webhook that would ever need to update a *separate* subscription
lifecycle independently of the tenant record. `UsageRecord` and `Invoice`
are built because they add something genuinely new: usage that
accumulates over a period, and a historical billing record — see below.

## Plan limits: which are enforced, and how

`tenants.Plan` has six `max_*` fields; `0` means unlimited (per the
field's own help text, unchanged from the Foundation phase). Two
different enforcement strategies, matched to what each limit actually
measures:

| Limit | Measured as | Enforced at |
|---|---|---|
| `max_users` | Live count of active `User` rows for the tenant | `POST /api/v1/staff/` |
| `max_whatsapp_accounts` | Live count of `WhatsAppAccount` rows | `POST /api/v1/whatsapp/accounts/` |
| `max_customers` | Live count of `Customer` rows | `POST /api/v1/customers/` **only** — see below |
| `max_ai_messages_per_month` | `UsageRecord` count for the current calendar month | `apps.ai.services.generate_ai_reply`, right before the real provider call |
| `max_campaigns_per_month` | `UsageRecord` count for the current calendar month | `POST /api/v1/campaigns/{id}/send/`, before the send is even queued |
| `max_storage_mb` | **Not enforced** | — no file-size tracking exists across every upload type (`KnowledgeDocument.file`, `MessageAttachment.file`, `Business.logo`, `Product.image`) to sum against; flagged honestly rather than half-built against just one of them |

`max_users`/`max_whatsapp_accounts`/`max_customers` are **live counts**,
re-derived from the actual tables on every check — always correct, no
drift possible, no separate bookkeeping to keep in sync.
`max_ai_messages_per_month`/`max_campaigns_per_month` are genuinely
**period usage** (the Plan field names say "per month"), so they're
backed by `billing.UsageRecord` — one row per `(tenant, metric, period)`,
`period` always the first day of a calendar month, incremented via
`apps.billing.services.increment_usage`.

## Customer creation: enforced on the API, not on the WhatsApp webhook

`POST /api/v1/customers/` (a staff member manually adding a customer) is
limit-checked. A **real inbound WhatsApp message from a new customer**
(`apps.whatsapp.services._process_single_event`'s `Customer.objects
.get_or_create`) is **never** blocked by this limit — dropping a genuine
customer inquiry because a business happened to exceed its plan's
customer quota would be a materially worse outcome than letting the
business briefly go over. This is a deliberate product decision, not an
oversight: manually-initiated actions through this codebase's own API
surface are gated; the WhatsApp inbound pipeline (the primary, real-world
way customers actually get created) is not.

## AI replies and campaign sends: real, metered costs — enforced

Unlike `customers` (just a database row, no incremental cost),
`ai_messages` and `campaign_sends` both correspond to a real external API
call that would cost real money once credentials are configured. Both
are hard-enforced, but differently, matching where each one runs:

- **Campaign sends** (`POST /api/v1/campaigns/{id}/send/`) run from an
  HTTP request — `apps.billing.services.check_limit` raises
  `PlanLimitExceeded` (see below), and the campaign is never even queued
  if the tenant is already at its monthly limit.
- **AI replies** (`apps.ai.services.generate_ai_reply`) run from a Celery
  task with no HTTP request to return an error to — raising there would
  go nowhere. Instead, `apps.billing.services.is_over_limit` is checked
  right before the real provider call, and an over-limit tenant is
  handled exactly like "no API key configured" already is (see
  `docs/ai.md`): hand off to a human if enabled, otherwise log and send
  nothing. Usage only increments *after* the provider call is actually
  attempted (success or failure) — a call that never happened (blocked
  by the limit, or short-circuited by a handoff keyword before any
  provider call) never counts against the quota.

## `PlanLimitExceeded`: 402, not 403 or 400

`apps.billing.exceptions.PlanLimitExceeded` is a small `APIException`
subclass with `status_code = 402` (Payment Required) — deliberately not
403 (this isn't a permissions problem; the same manager could do this
tomorrow on a different plan) or 400 (the request itself is perfectly
valid). Flows through the same `core.exceptions.custom_exception_handler`
envelope as every other error in this API — verified live returning a
real `402` with a clear message (`docs/billing.md`'s own live-verification
section below).

## What "generating an invoice" means here, and what it doesn't

`Invoice` is a real, correctly-modeled billing-period record: an
`invoice_number` deterministically built from the tenant's slug and
period (`INV-<SLUG>-<YYYYMM>`, so generating it twice for the same period
is naturally idempotent — no separate duplicate-check needed), a
snapshot of the plan's name/price at generation time (so a later price
change never rewrites a historical invoice — same pattern as
`OrderItem.product_name`/`unit_price`), and a `status` lifecycle
(`draft → issued → paid/overdue/void`, though nothing currently
transitions it past `issued` — no payment webhook exists to mark one
`paid`). **What doesn't happen**: no card is charged, no email is sent,
no payment link is generated. `python manage.py generate_invoices` (new
this phase) batch-creates one invoice per active/trial tenant with a plan
for the current month — in a real deployment this is the kind of thing a
`celery beat` schedule would run on the 1st of each month, but nothing
schedules it here, since there's no payment gateway for the resulting
invoices to actually be acted on by.

## API

See `docs/api.md` for the full endpoint table. Summary:
`GET /api/v1/billing/usage/` (staff+, own tenant — usage vs. every
enforced limit), `GET /api/v1/billing/invoices/` / `GET .../{id}/`
(manager+, own tenant), `POST /api/v1/billing/invoices/generate/` (super
admin only — manually trigger one tenant's invoice, e.g. for support).

## Testing

`tests/test_billing.py` covers `check_limit`/`is_over_limit` directly
(under limit, at limit, no plan, no tenant, `0`-means-unlimited),
`increment_usage`'s period-scoping, `generate_invoice`'s snapshotting and
idempotency, the API surface (tenant isolation, RBAC), and — the part
that actually matters — **enforcement wired into the real views**:
staff creation, WhatsApp account connection, customer creation, and
campaign sending all tested hitting a real `402` against a
purpose-built low-limit `Plan`, plus the AI-reply degradation path
(mocked provider never called once over the monthly limit). All 25 tests
passed on the first run.

**Also verified live** against a running dev server and the real seeded
ABC Electronics tenant: `GET /api/v1/billing/usage/` returned real counts
matching actual seeded data (2 users, 2 customers, 0 of 1 WhatsApp
accounts used); `python manage.py generate_invoices` created 3 real
invoices (one per seeded tenant) and was confirmed idempotent on a second
run; connecting a WhatsApp account succeeded once (bringing the tenant to
its `max_whatsapp_accounts=1` limit) and a second connection attempt
returned a genuine `HTTP 402` with the expected envelope and message.

## Limitations / not built

- `max_storage_mb` is not enforced (see the table above).
- No payment gateway integration — no card charges, no webhooks, no
  automatic `paid`/`overdue` transitions on `Invoice.status`.
- No plan upgrade/downgrade flow — `Tenant.plan` can be changed via the
  super-admin tenant endpoints from earlier phases, but there's no
  dedicated "upgrade your plan" UI/endpoint prompted by a `402`.
- No proration — an invoice is always the plan's full `price_monthly`
  for the period, regardless of when in the month a plan changed.
- `generate_invoices` isn't scheduled anywhere (no `celery beat` entry) —
  see above for why.
- No dunning/grace-period logic for an overdue invoice affecting
  `Tenant.status` — the two aren't currently linked at all.
