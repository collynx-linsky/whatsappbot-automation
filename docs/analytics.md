# Analytics

`apps.analytics` — the per-tenant dashboard and platform-wide stats from
spec section 17. **No new persisted models this phase** — every number is
computed live from existing data (`Customer`, `Conversation`, `Message`,
`Order`, `AuditLog`), not a materialized snapshot. See
[Scaling note](#scaling-note-live-computation-not-a-snapshot-store) below
for what that trade-off means in practice.

## Scoped by tenant, not Business

`Conversation`, `Message`, and `Order` only carry a `tenant` FK, not a
`business` FK (see `docs/database.md`) — `Business` is FK'd to `Tenant`,
not the other way round. Since onboarding currently creates exactly one
`Business` per `Tenant`, every metric here is effectively per-business in
practice, but it's *implemented* as per-tenant, matching how every other
view in this codebase scopes data (`request.user.tenant`). If a tenant
ever legitimately has more than one business, this dashboard would show
combined numbers for all of them — flagged here rather than silently
wrong.

## What's computed

`apps.analytics.services.business_dashboard(tenant, start=None, end=None)`
— one function per metric, all independently callable and independently
tested:

- **`customer_funnel`** — count of customers per lead-pipeline stage
  (`new → contacted → qualified → proposal → converted → lost`), spec
  section 17's funnel.
- **`conversation_counts`** — count per `Conversation.status`
  (`open|pending|resolved|closed`) plus `total`.
- **`message_counts`** — total messages and a breakdown by
  `Message.sender_type` (`customer|staff|ai|system|campaign`).
- **`order_revenue`** — order count per status, and revenue **grouped by
  currency**, not summed into one number. A tenant's orders aren't
  guaranteed to share a currency (multi-currency support exists at the
  `Order`/`Product` level), and silently adding `TZS` and `KES` together
  would be a real lie, not just an approximation — see
  `apps.analytics.services.REVENUE_STATUSES` for which order statuses
  actually count as revenue (`confirmed|processing|ready|delivered` —
  never `pending` or `cancelled`).
- **`ai_performance`** — count of AI-authored replies
  (`Message.sender_type=ai`) vs. handoffs to a human
  (`AuditLog.action=AI_HANDOFF`, written by `apps.ai.services._hand_off`
  — see `docs/ai.md`).
- **`average_response_time`** — see below.
- **`top_customer_questions`** — see below.

Every function accepts optional `start`/`end` datetime bounds, applied to
`created_at`.

## Response time: a real single-pass algorithm, not a placeholder

`average_response_time` measures, for every run of consecutive inbound
customer messages in a conversation, the time until the *next* outbound
message (staff, AI, or campaign) — not just "time to first reply ever" on
a conversation, but every wait the customer actually experienced across
its whole lifetime. Implemented as one ordered pass over
`(conversation_id, direction, created_at)` tuples (no N+1 queries, no
per-conversation subqueries): a pending-since timestamp is recorded on
the *first* unanswered inbound message and only cleared once an outbound
message answers it — a second, third, etc. consecutive inbound message
before that reply doesn't reset the clock (test-verified:
`tests/test_analytics.py::TestAverageResponseTime::test_consecutive_inbound_messages_count_as_one_wait`).

## Top questions: only genuinely repeated ones

`top_customer_questions` groups inbound customer messages by normalized
text (trimmed, whitespace-collapsed, lowercased) and returns the most
frequent, **displayed in their original casing** — but only messages
asked **more than once**. A list of every unique thing a single customer
ever asked isn't a "most common questions" list, it's just a transcript;
excluding count-1 entries is what makes the result actually mean
something. No NLP/semantic clustering — "What time do you open?" and
"When are you open?" are counted as two different questions, not merged.
A future phase could improve this using the embeddings already built in
`apps.knowledge` (cluster by cosine similarity instead of exact-text
match) — not built now to keep this phase's scope to what spec section 17
actually asks for.

## Platform-wide stats (super admin only)

`apps.analytics.platform_services` — deliberately a **separate module**
from `services.py`, not just a separate function, because every query
here reads across *every* tenant; keeping tenant-scoped and
platform-wide aggregation in the same file would make it too easy to
call the wrong one from a tenant-scoped view by mistake.
`platform_dashboard()` returns tenant counts by status, user counts by
role, total businesses/conversations/messages/orders, platform-wide
revenue (same currency-grouped honesty as the per-tenant version), and a
30-day new-tenant signup trend (`TruncDate` + `Count`, not a forecast —
just what actually happened).

## API

See `docs/api.md` for the full endpoint table. Summary:
`GET /api/v1/analytics/dashboard/` (staff+, the caller's own tenant,
optional `?start=&end=` ISO 8601 datetime bounds — an unparseable value
returns a clean `400`, not a silent no-op), `GET /api/v1/analytics/platform/`
(super admin only).

## Testing

`tests/test_analytics.py` covers every metric function directly against
real database data (no HTTP/provider mocking needed — this phase touches
no external service at all), the response-time single-pass algorithm's
correctness (including the consecutive-inbound edge case), the
top-questions repeated-only filter and text normalization, platform-wide
aggregation, and the API surface (tenant isolation, RBAC for both
endpoints, invalid date-bound rejection).

**Also verified live**: `GET /api/v1/analytics/dashboard/` against a
running dev server returned real counts matching the actual seeded data
for ABC Electronics (funnel, conversations, messages, currency-grouped
revenue); `GET /api/v1/analytics/platform/` as the real seeded super
admin returned accurate platform-wide totals across all 3 seeded tenants,
correctly grouped revenue across 3 different currencies (`KES`/`TZS`/`UGX`);
a business owner got a real `403` attempting the platform endpoint; an
unparseable `?start=` value returned a real `400`; a future `?start=`
date correctly zeroed out every funnel count.

## Scaling note: live computation, not a snapshot store

Every metric here is computed on every request, directly against the
live tables — appropriate at this project's MVP data volume, and
deliberately simpler than building a periodic aggregation job or
snapshot table this phase didn't need yet. This stops being appropriate
once a tenant's message/order volume is large enough that scanning it on
every dashboard load is slow. The natural next step, when that happens,
is a periodic (`celery beat`) job that computes and stores daily/hourly
snapshots — nothing in this module's public function signatures would
need to change, only their implementation (read from a snapshot table
instead of aggregating live).

## Limitations / not built

- No CSV/export endpoint — the dashboard is JSON only, no download.
- No caching — a `Redis`-backed short-TTL cache on `business_dashboard`
  would be a cheap win before reaching for the snapshot-table approach
  above, if live computation ever becomes noticeably slow before that's
  built.
- No campaign-specific analytics endpoint yet — `Campaign.sent_count`/
  `failed_count`/`skipped_count` already exist per-campaign
  (`docs/campaigns.md`) but aren't rolled up into this dashboard.
- No per-staff-member performance breakdown (response time by agent,
  conversations handled per agent) — everything here is tenant-wide.
